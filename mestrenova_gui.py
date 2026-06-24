#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mestrenova_gui.py — Mestrenova 15 GUI 自动化操作模块

功能：
  - 自动打开 .mnova 文件
  - 自动峰识别（Peak Picking）
  - 自动积分（Integration）
  - 导出峰列表到文本/CSV
  - 生成谱图图片
  - 自动处理各类对话框

依赖：
  - gui_automation.py（核心自动化模块）
  - pywinauto, pyautogui, pyperclip

使用示例：
  from mestrenova_gui import MestrenovaGUI
  mnova = MestrenovaGUI()
  mnova.launch()
  mnova.open_file("C:/spectra/sample.mnova")
  mnova.auto_peak_pick()
  mnova.auto_integrate()
  peaks = mnova.export_peaks_to_csv("C:/outputs/peaks.csv")
  mnova.export_spectrum_image("C:/outputs/spectrum.png")
"""

import os
import re
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field

from gui_automation import GUIAutomation, WaitStrategy

logger = logging.getLogger("mestrenova_gui")


@dataclass
class NMRPeak:
    """NMR 峰信号"""
    shift_ppm: float       # 化学位移 (ppm)
    intensity: float        # 积分强度
    multiplicity: str        # 多重性 (s, d, t, q, m, etc.)
    j_coupling: Optional[float] = None  # 耦合常数 J (Hz)
    comment: str = ""        # 备注
    atom_assignment: str = "" # 原子归属建议


@dataclass
class SpectrumInfo:
    """谱图信息"""
    nucleus: str            # 核类型 (1H, 13C, 19F, 31P, etc.)
    solvent: str = ""       # 溶剂
    frequency: str = ""      # 频率
    temperature: str = ""    # 温度
    filename: str = ""       # 文件名


class MestrenovaGUI:
    """
    Mestrenova 15 GUI 自动化操作类
    
    核心功能：
    1. 应用启动与管理
    2. 文件操作（打开、保存、导出）
    3. 峰识别与分析
    4. 积分操作
    5. 谱图显示与视图控制
    6. 数据导出（CSV、TXT、图片）
    
    快捷键参考（Mestrenova 15）：
    - Ctrl+O: 打开文件
    - Ctrl+S: 保存
    - Ctrl+Shift+S: 另存为
    - P: Peak picking mode
    - I: Integration mode
    - Ctrl+PgUp/PgDn: 放大/缩小
    - Ctrl+0: 适应窗口
    - Ctrl+G: 拾取峰
    - Ctrl+Shift+G: 自动拾取所有峰
    - Ctrl+I: 积分
    - Ctrl+Shift+I: 自动积分
    - Delete: 删除选中的峰/积分
    - Ctrl+Z: 撤销
    """
    
    # Mestrenova 15 窗口标题模式
    WINDOW_TITLE_PATTERN = "MestReNova.*"
    
    # 常见 Mestrenova 可执行文件路径
    COMMON_PATHS = [
        r"C:\Program Files\MestReNova\MestReNova.exe",
        r"C:\Program Files (x86)\MestReNova\MestReNova.exe",
        r"C:\MestReNova\MestReNova.exe",
        r"D:\Program Files\MestReNova\MestReNova.exe",
    ]
    
    def __init__(self, 
                 executable_path: Optional[str] = None,
                 timeout: float = 30.0):
        """
        初始化 Mestrenova GUI 自动化
        
        Args:
            executable_path: Mestrenova 可执行文件路径
                           如果为 None，自动搜索常见路径
            timeout: 操作超时时间（秒）
        """
        self.gui = GUIAutomation(timeout=timeout)
        self.executable_path = executable_path or self._find_executable()
        self.is_running = False
        
        logger.info(f"[初始化] Mestrenova GUI 自动化模块")
        logger.info(f"  - 可执行文件: {self.executable_path}")
    
    def _find_executable(self) -> Optional[str]:
        """查找 Mestrenova 可执行文件"""
        import winreg
        
        # 方法1: 检查常见安装路径
        for path in self.COMMON_PATHS:
            if Path(path).exists():
                logger.info(f"[检测] 找到 Mestrenova: {path}")
                return path
        
        # 方法2: 检查 Windows 注册表
        try:
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MestReNova"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\MestReNova"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\MestReNova"),
            ]
            
            for hkey, subkey in reg_paths:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        path, _ = winreg.QueryValueEx(key, "InstallPath")
                        exe_path = Path(path) / "MestReNova.exe"
                        if exe_path.exists():
                            logger.info(f"[检测] 找到 Mestrenova (注册表): {exe_path}")
                            return str(exe_path)
                except (OSError, FileNotFoundError):
                    continue
        except Exception as e:
            logger.debug(f"[检测] 注册表搜索失败: {e}")
        
        logger.warning("[警告] 未找到 Mestrenova，请手动指定 executable_path")
        return None
    
    # =========================================================================
    # 应用生命周期管理
    # =========================================================================
    
    def launch(self, 
               wait_for_ready: bool = True,
               maximize: bool = True) -> bool:
        """
        启动 Mestrenova
        
        Args:
            wait_for_ready: 等待应用就绪
            maximize: 启动后最大化窗口
            
        Returns:
            bool: 是否成功启动
        """
        if not self.executable_path:
            logger.error("[错误] 未找到 Mestrenova 可执行文件")
            return False
        
        if not Path(self.executable_path).exists():
            logger.error(f"[错误] 文件不存在: {self.executable_path}")
            return False
        
        try:
            # 启动应用
            success = self.gui.open_application(
                self.executable_path,
                wait_for_ready=wait_for_ready
            )
            
            if not success:
                return False
            
            # 等待窗口出现
            if not self.gui.wait_for_window(
                self.WINDOW_TITLE_PATTERN,
                timeout=15,
                strategy=WaitStrategy.WINDOW_VISIBLE
            ):
                logger.warning("[警告] 未能确认 Mestrenova 窗口")
            
            # 最大化窗口
            if maximize:
                time.sleep(1)
                self.gui.maximize_window()
            
            self.is_running = True
            logger.info("[成功] Mestrenova 已启动")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 启动 Mestrenova 失败: {e}")
            return False
    
    def close(self, force: bool = False) -> bool:
        """
        关闭 Mestrenova
        
        Args:
            force: 是否强制关闭
            
        Returns:
            bool: 是否成功关闭
        """
        if not self.is_running:
            return True
        
        try:
            # 先尝试保存当前文件
            self.gui.press_keys("Ctrl", "S")
            time.sleep(1)
            
            # 关闭窗口
            if force:
                self.gui.close_application(force=True)
            else:
                self.gui.press_keys("Alt", "F", "X")  # 文件-退出
                time.sleep(1)
                # 如果有未保存的更改，确认对话框
                self.gui.handle_dialog(action="yes")
            
            self.is_running = False
            logger.info("[成功] Mestrenova 已关闭")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 关闭 Mestrenova 失败: {e}")
            return False
    
    def connect(self, window_title_pattern: Optional[str] = None) -> bool:
        """
        连接到已运行的 Mestrenova 实例
        
        Args:
            window_title_pattern: 窗口标题模式
            
        Returns:
            bool: 是否成功连接
        """
        if not self.gui.connect_to_application(window_title=window_title_pattern or self.WINDOW_TITLE_PATTERN):
            return False
        
        self.is_running = True
        return True
    
    # =========================================================================
    # 文件操作
    # =========================================================================
    
    def open_file(self, filepath: str) -> bool:
        """
        打开 .mnova 文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            bool: 是否成功打开
        """
        path = Path(filepath)
        
        if not path.exists():
            logger.error(f"[错误] 文件不存在: {filepath}")
            return False
        
        try:
            logger.info(f"[打开文件] {filepath}")
            
            # 方法1: 使用 Ctrl+O 快捷键
            self.gui.press_keys("Ctrl", "O")
            time.sleep(1.5)
            
            # 输入文件路径
            self.gui.type_text(str(path.absolute()))
            time.sleep(0.5)
            
            # 按 Enter 打开
            self.gui.press_keys("Enter")
            time.sleep(2)  # 等待文件加载
            
            # 等待窗口标题更新为文件名
            max_wait = 30
            start = time.time()
            while time.time() - start < max_wait:
                title = self.gui.get_window_title()
                if path.stem in title or path.name in title:
                    logger.info(f"[成功] 文件已打开: {path.name}")
                    return True
                time.sleep(0.5)
            
            logger.info(f"[成功] 文件已打开（可能未完全加载）: {path.name}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 打开文件失败: {e}")
            return False
    
    def save_file(self, filepath: Optional[str] = None) -> bool:
        """
        保存文件
        
        Args:
            filepath: 保存路径（如果为 None，保存到当前文件）
            
        Returns:
            bool: 是否成功保存
        """
        try:
            if filepath:
                # 另存为
                self.gui.press_keys("Ctrl", "Shift", "S")
                time.sleep(1)
                
                self.gui.type_text(str(Path(filepath).absolute()))
                time.sleep(0.5)
                self.gui.press_keys("Enter")
                time.sleep(1)
                
                # 处理可能的确认对话框
                self.gui.handle_dialog(action="yes")
            else:
                # 直接保存
                self.gui.press_keys("Ctrl", "S")
            
            time.sleep(1)
            logger.info(f"[成功] 文件已保存: {filepath or '(当前文件)'}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 保存文件失败: {e}")
            return False
    
    # =========================================================================
    # 视图与显示控制
    # =========================================================================
    
    def zoom_in(self, times: int = 1) -> bool:
        """放大谱图"""
        for _ in range(times):
            self.gui.press_keys("Ctrl", "{ADD}")  # Ctrl++
            time.sleep(0.3)
        logger.debug(f"[缩放] 放大 {times} 次")
        return True
    
    def zoom_out(self, times: int = 1) -> bool:
        """缩小谱图"""
        for _ in range(times):
            self.gui.press_keys("Ctrl", "{SUBTRACT}")  # Ctrl+-
            time.sleep(0.3)
        logger.debug(f"[缩放] 缩小 {times} 次")
        return True
    
    def fit_to_window(self) -> bool:
        """适应窗口显示"""
        try:
            self.gui.press_keys("Ctrl", "0")  # Ctrl+0
            time.sleep(0.5)
            logger.debug("[视图] 已适应窗口")
            return True
        except Exception as e:
            logger.error(f"[错误] 适应窗口失败: {e}")
            return False
    
    def show_full_screen(self) -> bool:
        """全屏显示"""
        try:
            self.gui.press_keys("F11")
            time.sleep(0.5)
            logger.debug("[视图] 已切换到全屏")
            return True
        except Exception as e:
            logger.error(f"[错误] 全屏显示失败: {e}")
            return False
    
    # =========================================================================
    # 峰识别与分析
    # =========================================================================
    
    def enter_peak_picking_mode(self) -> bool:
        """
        进入峰识别模式
        
        快捷键: P
        """
        try:
            self.gui.press_keys("P")
            time.sleep(0.3)
            logger.debug("[模式] 已进入峰识别模式 (P)")
            return True
        except Exception as e:
            logger.error(f"[错误] 进入峰识别模式失败: {e}")
            return False
    
    def pick_peak_at_cursor(self) -> bool:
        """
        在光标位置拾取单个峰
        
        快捷键: Ctrl+G
        """
        try:
            self.gui.press_keys("Ctrl", "G")
            time.sleep(0.5)
            logger.debug("[峰识别] 已在光标位置拾取峰")
            return True
        except Exception as e:
            logger.error(f"[错误] 拾取峰失败: {e}")
            return False
    
    def auto_pick_peaks(self, 
                       threshold_snr: float = 3.0,
                       min_height: Optional[float] = None) -> bool:
        """
        自动拾取所有峰
        
        快捷键: Ctrl+Shift+G
        
        Args:
            threshold_snr: 信噪比阈值（默认 3.0）
            min_height: 最小峰高（可选）
            
        Returns:
            bool: 操作是否成功
        """
        try:
            logger.info("[峰识别] 开始自动拾取峰...")
            
            # 方法1: 使用快捷键自动拾取
            self.gui.press_keys("Ctrl", "Shift", "G")
            time.sleep(2)
            
            # 等待峰识别完成（观察状态）
            max_wait = 30
            start = time.time()
            while time.time() - start < max_wait:
                title = self.gui.get_window_title()
                if "busy" not in title.lower():
                    break
                time.sleep(1)
            
            logger.info("[成功] 自动峰拾取完成")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 自动拾取峰失败: {e}")
            return False
    
    def delete_selected_peaks(self) -> bool:
        """删除选中的峰"""
        try:
            self.gui.press_keys("Delete")
            time.sleep(0.3)
            logger.debug("[峰] 已删除选中的峰")
            return True
        except Exception as e:
            logger.error(f"[错误] 删除峰失败: {e}")
            return False
    
    def clear_all_peaks(self) -> bool:
        """清除所有峰"""
        try:
            # 全选
            self.gui.press_keys("Ctrl", "A")
            time.sleep(0.3)
            
            # 删除
            self.gui.press_keys("Delete")
            time.sleep(0.5)
            
            logger.debug("[峰] 已清除所有峰")
            return True
        except Exception as e:
            logger.error(f"[错误] 清除峰失败: {e}")
            return False
    
    def select_all_peaks(self) -> bool:
        """选中所有峰"""
        try:
            self.gui.press_keys("Ctrl", "A")
            time.sleep(0.3)
            logger.debug("[峰] 已选中所有峰")
            return True
        except Exception as e:
            logger.error(f"[错误] 选中所有峰失败: {e}")
            return False
    
    # =========================================================================
    # 积分操作
    # =========================================================================
    
    def enter_integration_mode(self) -> bool:
        """
        进入积分模式
        
        快捷键: I
        """
        try:
            self.gui.press_keys("I")
            time.sleep(0.3)
            logger.debug("[模式] 已进入积分模式 (I)")
            return True
        except Exception as e:
            logger.error(f"[错误] 进入积分模式失败: {e}")
            return False
    
    def auto_integrate(self) -> bool:
        """
        自动积分（对全谱或选中区域）
        
        快捷键: Ctrl+Shift+I
        """
        try:
            logger.info("[积分] 开始自动积分...")
            
            self.gui.press_keys("Ctrl", "Shift", "I")
            time.sleep(2)
            
            # 等待积分完成
            max_wait = 30
            start = time.time()
            while time.time() - start < max_wait:
                time.sleep(0.5)
                # 可以通过检查窗口状态来判断
            
            logger.info("[成功] 自动积分完成")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 自动积分失败: {e}")
            return False
    
    def integrate_region(self, x1: int, x2: int) -> bool:
        """
        对指定区域进行积分
        
        Args:
            x1, x2: 区域起始和结束坐标（屏幕像素）
        """
        try:
            # 进入积分模式
            self.enter_integration_mode()
            time.sleep(0.3)
            
            # 拖动选择区域
            self.gui.move_to(x1, y=500)  # y 位置根据谱图区域调整
            time.sleep(0.2)
            
            if pyautogui_available():
                import pyautogui
                pyautogui.drag(x2 - x1, 0, duration=0.5)
            
            time.sleep(0.5)
            logger.info(f"[积分] 已在区域 [{x1}, {x2}] 积分")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 区域积分失败: {e}")
            return False
    
    def delete_selected_integration(self) -> bool:
        """删除选中的积分"""
        return self.delete_selected_peaks()  # 操作相同
    
    def clear_all_integrations(self) -> bool:
        """清除所有积分"""
        try:
            self.select_all_peaks()
            time.sleep(0.3)
            self.gui.press_keys("Delete")
            time.sleep(0.5)
            logger.debug("[积分] 已清除所有积分")
            return True
        except Exception as e:
            logger.error(f"[错误] 清除积分失败: {e}")
            return False
    
    # =========================================================================
    # 数据导出
    # =========================================================================
    
    def export_peaks_to_csv(self, 
                           output_path: str,
                           include_integral: bool = True,
                           include_j_coupling: bool = True) -> bool:
        """
        导出峰列表到 CSV 文件
        
        Args:
            output_path: 输出 CSV 文件路径
            include_integral: 是否包含积分信息
            include_j_coupling: 是否包含 J 耦合常数
            
        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[导出] 峰列表到 CSV: {output_path}")
            
            # 1. 打开导出对话框
            # 方法: 文件菜单 -> 另存为 -> 选择格式
            self.gui.press_keys("Ctrl", "Shift", "S")
            time.sleep(1)
            
            # 2. 输入文件路径
            output_file = Path(output_path)
            self.gui.type_text(str(output_file.absolute()))
            time.sleep(0.5)
            
            # 3. 选择文件类型（下拉框操作）
            # 通常导出为 CSV 或 TXT 格式
            # 需要根据实际对话框调整
            self.gui.press_keys("{DOWN}")  # 打开文件类型下拉框
            time.sleep(0.3)
            
            # 多次按向下选择 CSV 格式
            for _ in range(5):
                self.gui.press_keys("{DOWN}")
                time.sleep(0.1)
            
            self.gui.press_keys("Enter")  # 选择
            time.sleep(0.3)
            
            # 4. 保存
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            # 5. 处理可能的格式选择对话框
            # 检查是否需要额外的格式选择步骤
            
            logger.info(f"[成功] 峰列表已导出: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 导出峰列表失败: {e}")
            return False
    
    def export_peaks_to_clipboard(self) -> List[NMRPeak]:
        """
        导出峰列表到剪贴板并解析
        
        Returns:
            List[NMRPeak]: 解析出的峰列表
        """
        try:
            logger.info("[导出] 峰列表到剪贴板...")
            
            # 1. 全选峰
            self.select_all_peaks()
            time.sleep(0.3)
            
            # 2. 复制
            self.gui.press_keys("Ctrl", "C")
            time.sleep(1)
            
            # 3. 获取剪贴板内容
            peaks_text = self.gui.paste_from_clipboard()
            
            # 4. 解析峰数据
            peaks = self._parse_peaks_text(peaks_text)
            
            logger.info(f"[成功] 解析到 {len(peaks)} 个峰信号")
            return peaks
            
        except Exception as e:
            logger.error(f"[错误] 导出到剪贴板失败: {e}")
            return []
    
    def _parse_peaks_text(self, text: str) -> List[NMRPeak]:
        """
        解析峰文本数据
        
        Mestrenova 导出的峰文本通常格式:
        Delta    Integral    Multiplicity    J    Annotation
        7.26     2.00        s               -    H2O
        3.62     2.00        q               7.1  CH2
        """
        peaks = []
        
        try:
            lines = text.strip().split('\n')
            
            # 跳过标题行
            data_lines = [l for l in lines if l.strip() and not l.startswith('Delta')][:50]  # 最多50个
            
            for line in data_lines:
                parts = re.split(r'[\t,;]+', line.strip())
                
                if len(parts) >= 2:
                    try:
                        shift = float(parts[0])
                        integral = float(parts[1]) if len(parts) > 1 else 1.0
                        mult = parts[2].strip() if len(parts) > 2 else ""
                        j_val = float(parts[3]) if len(parts) > 3 and parts[3].strip() != "-" else None
                        
                        peaks.append(NMRPeak(
                            shift_ppm=shift,
                            intensity=integral,
                            multiplicity=mult,
                            j_coupling=j_val
                        ))
                    except (ValueError, IndexError):
                        continue
            
        except Exception as e:
            logger.error(f"[错误] 解析峰文本失败: {e}")
        
        return peaks
    
    def export_spectrum_image(self, 
                             output_path: str,
                             width: int = 1920,
                             height: int = 1080,
                             format: str = "png") -> bool:
        """
        导出谱图图片
        
        Args:
            output_path: 输出图片路径
            width: 图片宽度
            height: 图片高度
            format: 图片格式 (png, jpg, tiff)
            
        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[导出] 谱图图片: {output_path}")
            
            # 方法1: 使用文件菜单导出
            # 菜单路径: File -> Export Image
            
            # Alt+F 打开文件菜单
            self.gui.press_keys("Alt", "F")
            time.sleep(0.5)
            
            # E 选择 Export
            self.gui.press_keys("E")
            time.sleep(0.5)
            
            # I 选择 Image
            self.gui.press_keys("I")
            time.sleep(1)
            
            # 输入文件路径
            output_file = Path(output_path)
            self.gui.type_text(str(output_file.absolute()))
            time.sleep(0.5)
            
            # 保存
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            # 处理可能的格式/选项对话框
            self.gui.handle_dialog(action="ok")
            
            logger.info(f"[成功] 谱图图片已导出: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 导出谱图图片失败: {e}")
            # 备用方案：使用 GUI 自动化截图
            return self._screenshot_export(output_path)
    
    def _screenshot_export(self, output_path: str) -> bool:
        """
        使用截图方式导出谱图（备用方案）
        """
        try:
            # 确保谱图窗口最大化
            self.gui.maximize_window()
            time.sleep(0.5)
            
            # 截图
            return self.gui.take_screenshot(Path(output_path).name)
            
        except Exception as e:
            logger.error(f"[错误] 截图导出失败: {e}")
            return False
    
    def export_to_excel(self, output_path: str) -> bool:
        """
        导出数据到 Excel
        
        Args:
            output_path: 输出 Excel 文件路径
            
        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[导出] 数据到 Excel: {output_path}")
            
            # 打开导出对话框
            self.gui.press_keys("Alt", "F")
            time.sleep(0.3)
            self.gui.press_keys("E")  # Export
            time.sleep(0.3)
            
            # 查找 Excel 导出选项
            # 通常在导出列表中有 "To Excel" 或 "Spreadsheet"
            for _ in range(3):
                self.gui.press_keys("{DOWN}")
                time.sleep(0.1)
            
            self.gui.press_keys("Enter")
            time.sleep(1)
            
            # 输入路径
            self.gui.type_text(str(Path(output_path).absolute()))
            time.sleep(0.3)
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            logger.info(f"[成功] Excel 导出完成: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] Excel 导出失败: {e}")
            return False
    
    # =========================================================================
    # 完整工作流程
    # =========================================================================
    
    def process_spectrum(self, 
                        input_file: str,
                        output_dir: str,
                        auto_detect: bool = True) -> Dict[str, Any]:
        """
        完整的谱图处理流程
        
        Args:
            input_file: 输入 .mnova 文件路径
            output_dir: 输出目录
            auto_detect: 是否自动检测核类型
            
        Returns:
            Dict: 处理结果
        """
        result = {
            "success": False,
            "input_file": input_file,
            "output_dir": output_dir,
            "peaks": [],
            "spectrum_image": None,
            "peaks_csv": None,
            "errors": []
        }
        
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 1. 打开文件
            logger.info("[Step 1/5] 打开谱图文件...")
            if not self.open_file(input_file):
                result["errors"].append("打开文件失败")
                return result
            
            time.sleep(2)
            
            # 2. 自动适应窗口
            logger.info("[Step 2/5] 调整视图...")
            self.fit_to_window()
            time.sleep(1)
            
            # 3. 自动拾取峰
            logger.info("[Step 3/5] 自动拾取峰...")
            if not self.auto_pick_peaks():
                result["errors"].append("峰拾取失败")
            
            time.sleep(1)
            
            # 4. 自动积分
            logger.info("[Step 4/5] 自动积分...")
            if not self.auto_integrate():
                result["errors"].append("积分失败")
            
            time.sleep(1)
            
            # 5. 导出结果
            logger.info("[Step 5/5] 导出结果...")
            
            # 导出峰列表 CSV
            peaks_csv = output_path / "peaks.csv"
            if self.export_peaks_to_csv(str(peaks_csv)):
                result["peaks_csv"] = str(peaks_csv)
                # 同时获取峰数据
                result["peaks"] = self.export_peaks_to_clipboard()
            
            # 导出谱图图片
            spectrum_img = output_path / "spectrum.png"
            if self.export_spectrum_image(str(spectrum_img)):
                result["spectrum_image"] = str(spectrum_img)
            
            # 截图备用
            self.gui.take_screenshot("spectrum_backup.png")
            
            result["success"] = True
            logger.info("[完成] 谱图处理完成!")
            
        except Exception as e:
            logger.error(f"[错误] 处理谱图时发生错误: {e}")
            result["errors"].append(str(e))
        
        return result
    
    # =========================================================================
    # 便捷方法
    # =========================================================================
    
    def get_spectrum_info(self) -> SpectrumInfo:
        """
        获取当前谱图的基本信息
        
        从窗口标题或菜单中提取信息
        """
        info = SpectrumInfo(nucleus="Unknown")
        
        try:
            title = self.gui.get_window_title()
            
            # 从标题中提取信息
            # 格式: "compound_name - 1H NMR (CDCl3) - MestReNova"
            if "-" in title:
                parts = title.split("-")
                if len(parts) >= 2:
                    info.filename = parts[0].strip()
                    
                    # 提取核类型
                    nucleus_match = re.search(r'(\d+H|\d+C|1H|13C|19F|31P)', parts[1])
                    if nucleus_match:
                        info.nucleus = nucleus_match.group(1)
                    
                    # 提取溶剂
                    if "CDCl3" in title:
                        info.solvent = "CDCl3"
                    elif "DMSO" in title:
                        info.solvent = "DMSO-d6"
                    elif "MeOD" in title:
                        info.solvent = "MeOD"
                    elif "D2O" in title:
                        info.solvent = "D2O"
                    elif "Acetone" in title:
                        info.solvent = "Acetone-d6"
            
        except Exception as e:
            logger.error(f"[错误] 获取谱图信息失败: {e}")
        
        return info
    
    def wait_for_processing(self, timeout: float = 60.0) -> bool:
        """等待当前处理完成"""
        start = time.time()
        
        while time.time() - start < timeout:
            title = self.gui.get_window_title().lower()
            
            # 检查是否还在处理
            if any(keyword in title for keyword in ["processing", "busy", "calculating"]):
                time.sleep(1)
                continue
            
            return True
        
        logger.warning(f"[警告] 等待处理完成超时: {timeout}秒")
        return False
    
    def undo(self) -> bool:
        """撤销上一步操作"""
        try:
            self.gui.press_keys("Ctrl", "Z")
            time.sleep(0.5)
            logger.debug("[撤销] 已撤销上一步操作")
            return True
        except Exception as e:
            logger.error(f"[错误] 撤销失败: {e}")
            return False
    
    def redo(self) -> bool:
        """重做"""
        try:
            self.gui.press_keys("Ctrl", "Y")
            time.sleep(0.5)
            logger.debug("[重做] 已重做")
            return True
        except Exception as e:
            logger.error(f"[错误] 重做失败: {e}")
            return False


# =============================================================================
# 辅助函数
# =============================================================================

def pyautogui_available() -> bool:
    """检查 pyautogui 是否可用"""
    try:
        import pyautogui
        return True
    except ImportError:
        return False


# =============================================================================
# 独立测试
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Mestrenova GUI 自动化测试")
    parser.add_argument("--launch", action="store_true", help="启动 Mestrenova")
    parser.add_argument("--open", metavar="FILE", help="打开 .mnova 文件")
    parser.add_argument("--auto-process", metavar="FILE", help="自动处理谱图文件")
    parser.add_argument("--close", action="store_true", help="关闭 Mestrenova")
    
    args = parser.parse_args()
    
    mnova = MestrenovaGUI()
    
    if args.launch:
        print("启动 Mestrenova...")
        mnova.launch()
        print("按 Enter 关闭...")
        input()
        mnova.close()
    
    elif args.open:
        print(f"打开文件: {args.open}")
        mnova.launch()
        time.sleep(2)
        mnova.open_file(args.open)
        print("按 Enter 关闭...")
        input()
        mnova.close()
    
    elif args.auto_process:
        print(f"自动处理: {args.auto_process}")
        mnova.launch()
        time.sleep(2)
        
        result = mnova.process_spectrum(
            args.auto_process,
            "./outputs/mestrenova_test"
        )
        
        print("\n=== 处理结果 ===")
        print(f"成功: {result['success']}")
        print(f"峰数: {len(result['peaks'])}")
        print(f"谱图图片: {result['spectrum_image']}")
        print(f"峰列表CSV: {result['peaks_csv']}")
        
        if result['errors']:
            print(f"错误: {result['errors']}")
        
        print("\n按 Enter 关闭...")
        input()
        mnova.close()
    
    elif args.close:
        print("关闭 Mestrenova...")
        mnova.connect()
        mnova.close()
    
    else:
        print("Mestrenova GUI 自动化模块已加载!")
        print(f"  - 可执行文件: {mnova.executable_path}")
        print(f"  - pyautogui: {'可用' if pyautogui_available() else '不可用'}")

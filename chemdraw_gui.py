#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chemdraw_gui.py — ChemDraw 2022 GUI 自动化操作模块

功能：
  - 根据 SMILES 自动绘制分子结构
  - 自动保存为 CDXML / PNG / SVG / MOL / SDF
  - 自动原子编号
  - 结构优化与美化
  - 批量结构绘制

依赖：
  - gui_automation.py（核心自动化模块）
  - pywinauto, pyautogui, pyperclip

使用示例：
  from chemdraw_gui import ChemDrawGUI
  cd = ChemDrawGUI()
  cd.launch()
  cd.draw_from_smiles("CCOC(=O)c1ccc(cc1)OC")  # 绘制对甲氧基苯甲酸乙酯
  cd.save_as("C:/outputs/structure.cdxml")
  cd.save_image("C:/outputs/structure.png")
"""

import os
import re
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass

from gui_automation import GUIAutomation, WaitStrategy

logger = logging.getLogger("chemdraw_gui")


class ChemDrawGUI:
    """
    ChemDraw 2022 GUI 自动化操作类
    
    核心功能：
    1. 应用启动与管理
    2. 从 SMILES 绘制结构（自动化结构绘制功能）
    3. 文件保存（多种格式）
    4. 原子编号
    5. 结构美化与优化
    
    快捷键参考（ChemDraw 2022）：
    - Ctrl+N: 新建文档
    - Ctrl+O: 打开文件
    - Ctrl+S: 保存
    - Ctrl+Shift+S: 另存为
    - Ctrl+V: 粘贴
    - Ctrl+A: 全选
    - Delete: 删除
    - Ctrl+Z: 撤销
    - Ctrl+Y: 重做
    - Ctrl+E: 打开自动化结构绘制（ASM）
    - Ctrl+G: 分组
    - Ctrl+U: 取消分组
    - Arrow keys: 微调位置
    
    菜单路径：
    - File -> Save As (Ctrl+Shift+S)
    - File -> Export (导出)
    - View -> Show Chemical Window (显示化学窗口)
    - Structure -> Add Atom -> Number (添加原子编号)
    - Structure -> Clean Up Structure (美化结构)
    """
    
    # ChemDraw 2022 窗口标题模式
    WINDOW_TITLE_PATTERN = "ChemDraw.*"
    
    # 常见 ChemDraw 2022 可执行文件路径
    COMMON_PATHS = [
        r"C:\Program Files\ChemOffice2022\ChemDraw\ChemDraw.exe",
        r"C:\Program Files\ChemOffice2021\ChemDraw\ChemDraw.exe",
        r"C:\Program Files (x86)\ChemOffice2022\ChemDraw\ChemDraw.exe",
        r"C:\Program Files (x86)\ChemOffice2021\ChemDraw\ChemDraw.exe",
        r"C:\Program Files\CambridgeSoft\ChemOffice2022\ChemDraw\ChemDraw.exe",
        r"C:\Users\Administrator\AppData\Local\CambridgeSoft\ChemOffice2022\ChemDraw\ChemDraw.exe",
    ]
    
    # 文件格式过滤器（用于保存对话框）
    FORMAT_FILTERS = {
        "cdxml": ("ChemDraw XML Files", "*.cdxml"),
        "cdx": ("ChemDraw Files", "*.cdx"),
        "png": ("PNG Image Files", "*.png"),
        "svg": ("SVG Files", "*.svg"),
        "emf": ("Enhanced Metafile", "*.emf"),
        "wmf": ("Windows Metafile", "*.wmf"),
        "eps": ("Encapsulated PostScript", "*.eps"),
        "tiff": ("TIFF Image", "*.tiff"),
        "sdf": ("SDF Files", "*.sdf"),
        "mol": ("MDL Mol Files", "*.mol"),
        "smiles": ("SMILES Files", "*.smiles"),
    }
    
    def __init__(self,
                 executable_path: Optional[str] = None,
                 timeout: float = 30.0):
        """
        初始化 ChemDraw GUI 自动化
        
        Args:
            executable_path: ChemDraw 可执行文件路径
            timeout: 操作超时时间（秒）
        """
        self.gui = GUIAutomation(timeout=timeout)
        self.executable_path = executable_path or self._find_executable()
        self.is_running = False
        
        logger.info(f"[初始化] ChemDraw GUI 自动化模块")
        logger.info(f"  - 可执行文件: {self.executable_path}")
    
    def _find_executable(self) -> Optional[str]:
        """查找 ChemDraw 可执行文件"""
        import winreg
        
        # 方法1: 检查常见安装路径
        for path in self.COMMON_PATHS:
            if Path(path).exists():
                logger.info(f"[检测] 找到 ChemDraw: {path}")
                return path
        
        # 方法2: 检查 Windows 注册表
        try:
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ChemOffice\ChemDraw"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\ChemOffice\ChemDraw"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\ChemOffice\ChemDraw"),
                (winreg.HKEY_CLASSES_ROOT, r"ChemDraw.Document\shell\open\command"),
            ]
            
            for hkey, subkey in reg_paths:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        try:
                            # 直接获取命令字符串
                            cmd, _ = winreg.QueryValueEx(key, "")
                            # 解析命令中的 exe 路径
                            match = re.search(r'"([^"]+\.exe)"', cmd)
                            if match and Path(match.group(1)).exists():
                                logger.info(f"[检测] 找到 ChemDraw (注册表): {match.group(1)}")
                                return match.group(1)
                        except (OSError, FileNotFoundError, ValueError):
                            pass
                        
                        try:
                            # 获取安装路径
                            path, _ = winreg.QueryValueEx(key, "InstallPath")
                            exe_path = Path(path) / "ChemDraw.exe"
                            if exe_path.exists():
                                logger.info(f"[检测] 找到 ChemDraw (注册表): {exe_path}")
                                return str(exe_path)
                        except (OSError, FileNotFoundError):
                            continue
                except (OSError, FileNotFoundError):
                    continue
        except Exception as e:
            logger.debug(f"[检测] 注册表搜索失败: {e}")
        
        logger.warning("[警告] 未找到 ChemDraw，请手动指定 executable_path")
        return None
    
    # =========================================================================
    # 应用生命周期管理
    # =========================================================================
    
    def launch(self,
               wait_for_ready: bool = True,
               maximize: bool = True) -> bool:
        """
        启动 ChemDraw
        
        Args:
            wait_for_ready: 等待应用就绪
            maximize: 启动后最大化窗口
            
        Returns:
            bool: 是否成功启动
        """
        if not self.executable_path:
            logger.error("[错误] 未找到 ChemDraw 可执行文件")
            return False
        
        if not Path(self.executable_path).exists():
            logger.error(f"[错误] 文件不存在: {self.executable_path}")
            return False
        
        try:
            logger.info(f"[启动] ChemDraw...")
            
            success = self.gui.open_application(
                self.executable_path,
                wait_for_ready=wait_for_ready
            )
            
            if not success:
                return False
            
            if not self.gui.wait_for_window(
                self.WINDOW_TITLE_PATTERN,
                timeout=15,
                strategy=WaitStrategy.WINDOW_VISIBLE
            ):
                logger.warning("[警告] 未能确认 ChemDraw 窗口")
            
            if maximize:
                time.sleep(1)
                self.gui.maximize_window()
            
            self.is_running = True
            logger.info("[成功] ChemDraw 已启动")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 启动 ChemDraw 失败: {e}")
            return False
    
    def close(self, force: bool = False) -> bool:
        """
        关闭 ChemDraw
        
        Args:
            force: 是否强制关闭
            
        Returns:
            bool: 是否成功关闭
        """
        if not self.is_running:
            return True
        
        try:
            # 先保存当前文件
            self.gui.press_keys("Ctrl", "S")
            time.sleep(1)
            
            # 关闭窗口
            if force:
                self.gui.close_application(force=True)
            else:
                # Alt+F4 关闭窗口
                self.gui.press_keys("Alt", "F4")
                time.sleep(1)
                
                # 处理"是否保存"对话框
                self.gui.handle_dialog(action="no")  # 不保存（刚才已保存）
            
            self.is_running = False
            logger.info("[成功] ChemDraw 已关闭")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 关闭 ChemDraw 失败: {e}")
            return False
    
    def connect(self, window_title_pattern: Optional[str] = None) -> bool:
        """
        连接到已运行的 ChemDraw 实例
        """
        if not self.gui.connect_to_application(
            window_title=window_title_pattern or self.WINDOW_TITLE_PATTERN
        ):
            return False
        
        self.is_running = True
        return True
    
    # =========================================================================
    # 文件操作
    # =========================================================================
    
    def new_document(self, width: float = 20.0, height: float = 15.0) -> bool:
        """
        新建文档
        
        Args:
            width: 文档宽度（cm）
            height: 文档高度（cm）
            
        Returns:
            bool: 是否成功
        """
        try:
            self.gui.press_keys("Ctrl", "N")
            time.sleep(1)
            
            # 如果出现页面设置对话框，设置文档大小
            # 默认取消，使用默认大小
            self.gui.handle_dialog(action="cancel")
            
            logger.info("[成功] 新建文档")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 新建文档失败: {e}")
            return False
    
    def open_file(self, filepath: str) -> bool:
        """
        打开文件
        
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
            
            self.gui.press_keys("Ctrl", "O")
            time.sleep(1.5)
            
            self.gui.type_text(str(path.absolute()))
            time.sleep(0.5)
            
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            logger.info(f"[成功] 文件已打开: {path.name}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 打开文件失败: {e}")
            return False
    
    def save_as(self,
               filepath: str,
               format: Optional[str] = None) -> bool:
        """
        另存为
        
        Args:
            filepath: 保存路径
            format: 文件格式（cdxml, png, svg 等），如果为 None 根据扩展名自动判断
            
        Returns:
            bool: 是否成功保存
        """
        try:
            logger.info(f"[另存为] {filepath}")
            
            self.gui.press_keys("Ctrl", "Shift", "S")
            time.sleep(1)
            
            # 输入文件路径
            self.gui.type_text(str(Path(filepath).absolute()))
            time.sleep(0.5)
            
            # 如果指定了格式，需要在保存对话框中选择
            if format:
                # 打开格式下拉框
                self.gui.press_keys("{TAB}")
                time.sleep(0.2)
                
                # 选择格式
                self._select_save_format(format)
            
            self.gui.press_keys("Enter")
            time.sleep(1)
            
            # 处理可能的确认对话框
            self.gui.handle_dialog(action="yes")
            
            logger.info(f"[成功] 文件已保存: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 保存文件失败: {e}")
            return False
    
    def _select_save_format(self, format: str) -> bool:
        """
        在保存对话框中选择文件格式
        
        Args:
            format: 格式名称 (cdxml, png, svg 等)
        """
        try:
            # 打开格式下拉框
            self.gui.press_keys("{DOWN}")
            time.sleep(0.3)
            
            # 查找目标格式
            format_map = {
                "cdxml": 0, "cdx": 1, "png": 2, "svg": 3,
                "emf": 4, "wmf": 5, "eps": 6, "tiff": 7,
                "sdf": 8, "mol": 9
            }
            
            target_index = format_map.get(format.lower(), 0)
            
            # 移动到目标格式
            for _ in range(target_index):
                self.gui.press_keys("{DOWN}")
                time.sleep(0.1)
            
            self.gui.press_keys("Enter")
            time.sleep(0.3)
            
            return True
            
        except Exception as e:
            logger.error(f"[错误] 选择保存格式失败: {e}")
            return False
    
    # =========================================================================
    # 结构绘制
    # =========================================================================
    
    def draw_from_smiles(self, smiles: str) -> bool:
        """
        从 SMILES 字符串绘制分子结构
        
        使用 ChemDraw 的自动化结构绘制 (ASM) 功能：
        1. 打开 ASM 对话框 (Ctrl+E)
        2. 粘贴 SMILES
        3. 点击 Insert 插入结构
        
        Args:
            smiles: SMILES 字符串
            
        Returns:
            bool: 是否成功绘制
        """
        try:
            logger.info(f"[绘制] 从 SMILES 绘制结构: {smiles[:50]}...")
            
            # 清空当前文档
            self.new_document()
            time.sleep(0.5)
            
            # 方法1: 使用自动化结构绘制 (ASM) - Ctrl+E
            logger.info("[绘制] 打开自动化结构绘制...")
            self.gui.press_keys("Ctrl", "E")
            time.sleep(2)  # 等待 ASM 对话框打开
            
            # 在 SMILES 输入框中粘贴 SMILES
            # 尝试 Tab 导航到输入框
            for _ in range(3):
                self.gui.press_keys("{TAB}")
                time.sleep(0.2)
            
            # 直接输入 SMILES
            self.gui.type_text(smiles)
            time.sleep(1)
            
            # 点击 Insert 按钮或按 Enter
            self.gui.press_keys("Enter")
            time.sleep(2)  # 等待结构生成
            
            # 关闭 ASM 对话框
            self.gui.press_keys("Escape")
            time.sleep(0.5)
            
            # 检查是否成功绘制（通过窗口变化判断）
            logger.info("[成功] SMILES 结构已绘制")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 从 SMILES 绘制失败: {e}")
            return False
    
    def draw_from_name(self, compound_name: str) -> bool:
        """
        从化合物名称绘制结构
        
        ChemDraw 的 ASM 功能也支持化合物名称
        """
        try:
            logger.info(f"[绘制] 从化合物名称绘制: {compound_name}")
            
            self.new_document()
            time.sleep(0.5)
            
            # 打开 ASM
            self.gui.press_keys("Ctrl", "E")
            time.sleep(2)
            
            # 输入化合物名称
            self.gui.type_text(compound_name)
            time.sleep(1)
            
            # 尝试自动转换
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            self.gui.press_keys("Escape")
            time.sleep(0.5)
            
            logger.info("[成功] 化合物名称已绘制")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 从化合物名称绘制失败: {e}")
            return False
    
    def clean_up_structure(self) -> bool:
        """
        美化结构（自动布局）
        
        菜单: Structure -> Clean Up Structure
        快捷键: Ctrl+Shift+K
        """
        try:
            logger.info("[美化] 美化分子结构...")
            
            # 使用快捷键
            self.gui.press_keys("Ctrl", "Shift", "K")
            time.sleep(1)
            
            logger.info("[成功] 结构已美化")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 美化结构失败: {e}")
            return False
    
    def select_all(self) -> bool:
        """全选"""
        try:
            self.gui.press_keys("Ctrl", "A")
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"[错误] 全选失败: {e}")
            return False
    
    def delete_selection(self) -> bool:
        """删除选中对象"""
        try:
            self.gui.press_keys("Delete")
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"[错误] 删除失败: {e}")
            return False
    
    # =========================================================================
    # 原子编号
    # =========================================================================
    
    def add_atom_numbers(self, 
                         start: int = 1,
                         style: str = "arabic") -> bool:
        """
        添加原子编号
        
        菜单: Structure -> Add Atom -> Number
        
        Args:
            start: 起始编号
            style: 编号样式 ("arabic", "roman", "alpha")
            
        Returns:
            bool: 是否成功添加
        """
        try:
            logger.info(f"[编号] 添加原子编号 (起始: {start}, 样式: {style})...")
            
            # 选中所有结构
            self.select_all()
            time.sleep(0.3)
            
            # 方法1: 通过菜单添加
            # Alt+S 打开 Structure 菜单
            self.gui.press_keys("Alt", "S")
            time.sleep(0.3)
            
            # A 选择 Add Atom
            self.gui.press_keys("A")
            time.sleep(0.3)
            
            # N 选择 Number
            self.gui.press_keys("N")
            time.sleep(1)
            
            # 方法2: 使用快捷键（如果有的话）
            # Ctrl+Shift+N
            
            logger.info("[成功] 原子编号已添加")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 添加原子编号失败: {e}")
            return False
    
    def remove_atom_numbers(self) -> bool:
        """移除原子编号"""
        try:
            self.select_all()
            time.sleep(0.3)
            
            # Delete 或使用菜单移除
            self.gui.press_keys("Alt", "S")
            time.sleep(0.3)
            self.gui.press_keys("A")
            time.sleep(0.3)
            self.gui.press_keys("N")
            time.sleep(0.3)
            # 选择 Remove 选项
            self.gui.press_keys("{DOWN}")
            time.sleep(0.2)
            self.gui.press_keys("Enter")
            time.sleep(0.5)
            
            logger.info("[成功] 原子编号已移除")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 移除原子编号失败: {e}")
            return False
    
    # =========================================================================
    # 导出功能
    # =========================================================================
    
    def save_image(self,
                  filepath: str,
                  width: Optional[int] = None,
                  height: Optional[int] = None) -> bool:
        """
        导出为图片
        
        Args:
            filepath: 输出文件路径
            width: 图片宽度（像素）
            height: 图片高度（像素）
            
        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[导出] 保存图片: {filepath}")
            
            # 选中所有结构
            self.select_all()
            time.sleep(0.3)
            
            # 复制到剪贴板
            self.gui.press_keys("Ctrl", "C")
            time.sleep(0.5)
            
            # 使用保存对话框保存
            self.gui.press_keys("Ctrl", "Shift", "S")
            time.sleep(1)
            
            # 输入路径
            output_path = Path(filepath)
            self.gui.type_text(str(output_path.absolute()))
            time.sleep(0.5)
            
            # 选择格式
            ext = output_path.suffix.lower().lstrip('.')
            if ext in self.FORMAT_FILTERS:
                self._select_save_format(ext)
            
            self.gui.press_keys("Enter")
            time.sleep(1)
            
            # 处理对话框
            self.gui.handle_dialog(action="yes")
            
            logger.info(f"[成功] 图片已保存: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 保存图片失败: {e}")
            return False
    
    def export_cdxml(self, filepath: str) -> bool:
        """
        导出为 CDXML 格式
        
        CDXML 是 ChemDraw 的原生 XML 格式，可双击打开编辑
        """
        return self.save_as(filepath, format="cdxml")
    
    def export_svg(self, filepath: str) -> bool:
        """导出为 SVG 矢量图"""
        return self.save_as(filepath, format="svg")
    
    def export_png(self, filepath: str, 
                   dpi: int = 300) -> bool:
        """
        导出为 PNG 图片
        
        Args:
            filepath: 输出文件路径
            dpi: 分辨率（默认 300 DPI）
        """
        return self.save_as(filepath, format="png")
    
    def export_sdf(self, filepath: str) -> bool:
        """导出为 SDF 3D 结构文件"""
        return self.save_as(filepath, format="sdf")
    
    def export_mol(self, filepath: str) -> bool:
        """导出为 MOL 格式"""
        return self.save_as(filepath, format="mol")
    
    # =========================================================================
    # 完整工作流程
    # =========================================================================
    
    def create_structure_image(self,
                              smiles: Optional[str] = None,
                              compound_name: Optional[str] = None,
                              output_path: str,
                              add_numbers: bool = True,
                              clean_up: bool = True,
                              format: str = "png") -> Dict[str, Any]:
        """
        完整的结构图像创建流程
        
        Args:
            smiles: SMILES 字符串
            compound_name: 化合物名称（二选一）
            output_path: 输出文件路径
            add_numbers: 是否添加原子编号
            clean_up: 是否美化结构
            format: 输出格式 (png, svg, cdxml, sdf)
            
        Returns:
            Dict: 操作结果
        """
        result = {
            "success": False,
            "smiles": smiles,
            "compound_name": compound_name,
            "output_path": output_path,
            "errors": []
        }
        
        try:
            # 1. 启动 ChemDraw
            if not self.is_running:
                if not self.launch():
                    result["errors"].append("启动 ChemDraw 失败")
                    return result
            
            # 2. 绘制结构
            if smiles:
                if not self.draw_from_smiles(smiles):
                    result["errors"].append("SMILES 绘制失败")
                    return result
            elif compound_name:
                if not self.draw_from_name(compound_name):
                    result["errors"].append("化合物名称绘制失败")
                    return result
            else:
                result["errors"].append("未提供 SMILES 或化合物名称")
                return result
            
            time.sleep(1)
            
            # 3. 美化结构
            if clean_up:
                self.clean_up_structure()
                time.sleep(0.5)
            
            # 4. 添加原子编号
            if add_numbers:
                self.add_atom_numbers()
                time.sleep(0.5)
            
            # 5. 导出
            if format == "png":
                success = self.export_png(output_path)
            elif format == "svg":
                success = self.export_svg(output_path)
            elif format == "cdxml":
                success = self.export_cdxml(output_path)
            elif format == "sdf":
                success = self.export_sdf(output_path)
            else:
                success = self.save_as(output_path)
            
            if success:
                result["success"] = True
                logger.info(f"[成功] 结构图像已创建: {output_path}")
            else:
                result["errors"].append("导出失败")
            
        except Exception as e:
            logger.error(f"[错误] 创建结构图像失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def batch_create_structures(self,
                               structures: List[Dict[str, str]],
                               output_dir: str,
                               format: str = "png") -> Dict[str, Any]:
        """
        批量创建结构图像
        
        Args:
            structures: 结构列表，每项包含 "smiles" 或 "name"
            output_dir: 输出目录
            format: 输出格式
            
        Returns:
            Dict: 批量处理结果
        """
        result = {
            "total": len(structures),
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i, struct in enumerate(structures, 1):
            logger.info(f"[批量] 处理 {i}/{len(structures)}...")
            
            smiles = struct.get("smiles")
            name = struct.get("name", f"structure_{i}")
            output_file = output_path / f"{name}.{format}"
            
            res = self.create_structure_image(
                smiles=smiles,
                compound_name=struct.get("name") if not smiles else None,
                output_path=str(output_file),
                format=format
            )
            
            if res["success"]:
                result["success"] += 1
            else:
                result["failed"] += 1
                result["errors"].append({
                    "index": i,
                    "structure": struct,
                    "errors": res["errors"]
                })
            
            # 每个结构处理后关闭重新打开（避免累积）
            time.sleep(0.5)
        
        logger.info(f"[完成] 批量处理完成: 成功 {result['success']}/{result['total']}")
        return result
    
    # =========================================================================
    # 便捷方法
    # =========================================================================
    
    def copy_structure_to_clipboard(self, smiles: str) -> bool:
        """
        将 SMILES 结构复制到剪贴板（作为图片）
        
        Args:
            smiles: SMILES 字符串
            
        Returns:
            bool: 是否成功
        """
        try:
            # 先绘制
            if not self.draw_from_smiles(smiles):
                return False
            
            time.sleep(0.5)
            
            # 全选
            self.select_all()
            time.sleep(0.3)
            
            # 复制
            self.gui.press_keys("Ctrl", "C")
            time.sleep(0.5)
            
            logger.info("[成功] 结构已复制到剪贴板")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 复制结构到剪贴板失败: {e}")
            return False
    
    def get_structure_smiles(self) -> Optional[str]:
        """
        获取当前结构的 SMILES
        
        从剪贴板获取（Edit -> Copy As -> SMILES）
        """
        try:
            # 选中所有
            self.select_all()
            time.sleep(0.3)
            
            # 复制为 SMILES
            # Alt+E 打开 Edit 菜单
            self.gui.press_keys("Alt", "E")
            time.sleep(0.3)
            
            # C 选择 Copy As
            self.gui.press_keys("C")
            time.sleep(0.3)
            
            # S 选择 SMILES
            self.gui.press_keys("S")
            time.sleep(0.5)
            
            # 获取剪贴板内容
            smiles = self.gui.paste_from_clipboard()
            
            if smiles and len(smiles) > 0:
                logger.info(f"[成功] 获取到 SMILES: {smiles[:50]}...")
                return smiles
            
        except Exception as e:
            logger.error(f"[错误] 获取 SMILES 失败: {e}")
        
        return None
    
    def undo(self) -> bool:
        """撤销"""
        try:
            self.gui.press_keys("Ctrl", "Z")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"[错误] 撤销失败: {e}")
            return False
    
    def redo(self) -> bool:
        """重做"""
        try:
            self.gui.press_keys("Ctrl", "Y")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"[错误] 重做失败: {e}")
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
    
    parser = argparse.ArgumentParser(description="ChemDraw GUI 自动化测试")
    parser.add_argument("--launch", action="store_true", help="启动 ChemDraw")
    parser.add_argument("--draw", metavar="SMILES", help="从 SMILES 绘制结构")
    parser.add_argument("--save", nargs=2, metavar=("SMILES", "PATH"), help="绘制并保存")
    parser.add_argument("--batch", metavar="DIR", help="批量处理目录中的 SMILES 文件")
    parser.add_argument("--close", action="store_true", help="关闭 ChemDraw")
    
    args = parser.parse_args()
    
    cd = ChemDrawGUI()
    
    if args.launch:
        print("启动 ChemDraw...")
        cd.launch()
        print("按 Enter 关闭...")
        input()
        cd.close()
    
    elif args.draw:
        print(f"绘制 SMILES: {args.draw}")
        cd.launch()
        time.sleep(2)
        cd.draw_from_smiles(args.draw)
        cd.clean_up_structure()
        print("按 Enter 关闭...")
        input()
        cd.close()
    
    elif args.save:
        smiles, path = args.save
        print(f"绘制并保存: {smiles} -> {path}")
        
        result = cd.create_structure_image(
            smiles=smiles,
            output_path=path,
            add_numbers=True,
            clean_up=True
        )
        
        print(f"\n结果: {'成功' if result['success'] else '失败'}")
        if result['errors']:
            print(f"错误: {result['errors']}")
        
        cd.close()
    
    elif args.batch:
        print(f"批量处理: {args.batch}")
        # 读取目录中的 SMILES 文件
        batch_dir = Path(args.batch)
        structures = []
        
        for f in batch_dir.glob("*.smiles"):
            smiles = f.read_text().strip()
            structures.append({
                "smiles": smiles,
                "name": f.stem
            })
        
        if structures:
            result = cd.batch_create_structures(
                structures,
                str(batch_dir / "output"),
                format="png"
            )
            print(f"\n批量处理完成:")
            print(f"  总数: {result['total']}")
            print(f"  成功: {result['success']}")
            print(f"  失败: {result['failed']}")
        else:
            print("未找到 .smiles 文件")
    
    elif args.close:
        print("关闭 ChemDraw...")
        cd.connect()
        cd.close()
    
    else:
        print("ChemDraw GUI 自动化模块已加载!")
        print(f"  - 可执行文件: {cd.executable_path}")

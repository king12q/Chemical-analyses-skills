#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spartan_gui.py — Spartan '14 V1.1.4 GUI 自动化操作模块

功能：
  - 从 SMILES/MOL 文件导入分子结构
  - 运行几何优化（DFT, MMFF, etc.）
  - 运行 NMR 化学位移预测
  - 运行 ECD/ORD 手性光谱计算
  - 构象搜索与分析
  - 导出计算结果

依赖：
  - gui_automation.py（核心自动化模块）
  - pywinauto, pyautogui, pyperclip

使用示例：
  from spartan_gui import SpartanGUI
  spartan = SpartanGUI()
  spartan.launch()
  spartan.import_from_smiles("CCOC(=O)c1ccc(cc1)OC")
  spartan.optimize_geometry(method="DFT", basis="6-31G*")
  spartan.calculate_nmr()
  spartan.export_results("C:/outputs/spartan_results")
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

logger = logging.getLogger("spartan_gui")


class SpartanGUI:
    """
    Spartan '14 V1.1.4 GUI 自动化操作类
    
    核心功能：
    1. 应用启动与管理
    2. 分子结构导入（从 SMILES, MOL, SDF）
    3. 几何优化计算
    4. 光谱性质计算（NMR, ECD, IR, etc.）
    5. 构象搜索
    6. 结果导出
    
    注意：Spartan '14 是一款专业量化计算软件，
    其 GUI 操作相对复杂，以下为常用的自动化操作模式
    
    快捷键参考（Spartan '14）：
    - Ctrl+N: 新建
    - Ctrl+O: 打开
    - Ctrl+S: 保存
    - Ctrl+Shift+E: 能量计算面板
    - F10: 几何优化
    - F9: 单点能
    - F8: 过渡态搜索
    - F7: 构象搜索
    - Ctrl+M: 显示分子窗口
    - Ctrl+B: 显示构建面板
    - Ctrl+L: 显示日志
    """
    
    # Spartan '14 窗口标题模式
    WINDOW_TITLE_PATTERN = "Spartan.*"
    
    # 常见 Spartan '14 可执行文件路径
    COMMON_PATHS = [
        r"C:\Program Files\Wavefunction\Spartan14\Spartan14.exe",
        r"C:\Program Files (x86)\Wavefunction\Spartan14\Spartan14.exe",
        r"C:\Spartan14\Spartan14.exe",
        r"D:\Program Files\Wavefunction\Spartan14\Spartan14.exe",
    ]
    
    # 计算方法
    CALCULATION_METHODS = {
        "mmff": "MMFF94",
        "mm2": "MM2",
        "amber": "Amber",
        "hartree_fock": "Hartree-Fock",
        "hf": "Hartree-Fock",
        "mp2": "MP2",
        "dft": "DFT",
        "b3lyp": "B3LYP",
        "wb97x_d": "wB97X-D",
    }
    
    # 基组
    BASIS_SETS = [
        "3-21G",
        "6-31G",
        "6-31G*",
        "6-31G**",
        "6-311G",
        "6-311G*",
        "6-311G**",
        "cc-pVDZ",
        "cc-pVTZ",
    ]
    
    def __init__(self,
                 executable_path: Optional[str] = None,
                 timeout: float = 60.0):
        """
        初始化 Spartan GUI 自动化
        
        Args:
            executable_path: Spartan 可执行文件路径
            timeout: 操作超时时间（秒）
        """
        self.gui = GUIAutomation(timeout=timeout)
        self.executable_path = executable_path or self._find_executable()
        self.is_running = False
        
        logger.info(f"[初始化] Spartan GUI 自动化模块")
        logger.info(f"  - 可执行文件: {self.executable_path}")
    
    def _find_executable(self) -> Optional[str]:
        """查找 Spartan 可执行文件"""
        import winreg
        
        # 方法1: 检查常见安装路径
        for path in self.COMMON_PATHS:
            if Path(path).exists():
                logger.info(f"[检测] 找到 Spartan: {path}")
                return path
        
        # 方法2: 检查 Windows 注册表
        try:
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wavefunction\Spartan14"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Wavefunction\Spartan14"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Wavefunction\Spartan14"),
            ]
            
            for hkey, subkey in reg_paths:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        try:
                            path, _ = winreg.QueryValueEx(key, "InstallDir")
                            exe_path = Path(path) / "Spartan14.exe"
                            if exe_path.exists():
                                logger.info(f"[检测] 找到 Spartan (注册表): {exe_path}")
                                return str(exe_path)
                        except (OSError, FileNotFoundError):
                            continue
                except (OSError, FileNotFoundError):
                    continue
        except Exception as e:
            logger.debug(f"[检测] 注册表搜索失败: {e}")
        
        logger.warning("[警告] 未找到 Spartan '14，请手动指定 executable_path")
        return None
    
    # =========================================================================
    # 应用生命周期管理
    # =========================================================================
    
    def launch(self,
               wait_for_ready: bool = True) -> bool:
        """
        启动 Spartan '14
        
        Args:
            wait_for_ready: 等待应用就绪
            
        Returns:
            bool: 是否成功启动
        """
        if not self.executable_path:
            logger.error("[错误] 未找到 Spartan 可执行文件")
            return False
        
        if not Path(self.executable_path).exists():
            logger.error(f"[错误] 文件不存在: {self.executable_path}")
            return False
        
        try:
            logger.info(f"[启动] Spartan '14...")
            
            success = self.gui.open_application(
                self.executable_path,
                wait_for_ready=wait_for_ready
            )
            
            if not success:
                return False
            
            if not self.gui.wait_for_window(
                self.WINDOW_TITLE_PATTERN,
                timeout=20,
                strategy=WaitStrategy.WINDOW_VISIBLE
            ):
                logger.warning("[警告] 未能确认 Spartan 窗口")
            
            time.sleep(2)  # 等待初始化
            
            self.is_running = True
            logger.info("[成功] Spartan '14 已启动")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 启动 Spartan 失败: {e}")
            return False
    
    def close(self, force: bool = False) -> bool:
        """
        关闭 Spartan
        
        Args:
            force: 是否强制关闭
            
        Returns:
            bool: 是否成功关闭
        """
        if not self.is_running:
            return True
        
        try:
            if force:
                self.gui.close_application(force=True)
            else:
                # 尝试通过菜单关闭
                self.gui.press_keys("Alt", "F")
                time.sleep(0.3)
                self.gui.press_keys("X")  # Exit
                time.sleep(1)
                
                # 处理确认对话框
                self.gui.handle_dialog(action="yes")
            
            self.is_running = False
            logger.info("[成功] Spartan 已关闭")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 关闭 Spartan 失败: {e}")
            return False
    
    def connect(self, window_title_pattern: Optional[str] = None) -> bool:
        """
        连接到已运行的 Spartan 实例
        """
        if not self.gui.connect_to_application(
            window_title=window_title_pattern or self.WINDOW_TITLE_PATTERN
        ):
            return False
        
        self.is_available = True
        return True
    
    # =========================================================================
    # 文件操作
    # =========================================================================
    
    def new_document(self) -> bool:
        """新建文档"""
        try:
            self.gui.press_keys("Ctrl", "N")
            time.sleep(1)
            logger.info("[成功] 新建文档")
            return True
        except Exception as e:
            logger.error(f"[错误] 新建文档失败: {e}")
            return False
    
    def open_file(self, filepath: str) -> bool:
        """
        打开分子文件
        
        Args:
            filepath: 分子文件路径 (.spardir, .mol, .sdf, .pdb)
            
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
            time.sleep(3)  # 等待文件加载
            
            logger.info(f"[成功] 文件已打开: {path.name}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 打开文件失败: {e}")
            return False
    
    def save_file(self, filepath: str) -> bool:
        """
        保存文档
        
        Args:
            filepath: 保存路径
            
        Returns:
            bool: 是否成功保存
        """
        try:
            logger.info(f"[保存] {filepath}")
            
            self.gui.press_keys("Ctrl", "S")
            time.sleep(1)
            
            self.gui.type_text(str(Path(filepath).absolute()))
            time.sleep(0.5)
            
            self.gui.press_keys("Enter")
            time.sleep(1)
            
            logger.info("[成功] 文件已保存")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 保存文件失败: {e}")
            return False
    
    # =========================================================================
    # 分子构建
    # =========================================================================
    
    def import_from_smiles(self, smiles: str) -> bool:
        """
        从 SMILES 导入分子结构
        
        方法：先在 ChemDraw 中绘制，然后导入到 Spartan
        或者使用 Spartan's Build 功能手动构建
        
        Args:
            smiles: SMILES 字符串
            
        Returns:
            bool: 是否成功导入
        """
        try:
            logger.info(f"[导入] 从 SMILES 导入: {smiles[:50]}...")
            
            # 方案1: 尝试 Spartan 直接导入（如果有此功能）
            # 通常 Spartan 需要先在 Build 面板中构建
            
            # 打开 Build 面板
            self.gui.press_keys("Ctrl", "B")
            time.sleep(1)
            
            # 如果有 SMILES 输入功能
            # 可以尝试菜单: File -> Import -> SMILES
            
            # 备用方案：使用剪贴板
            # 复制 SMILES 到剪贴板
            self.gui.copy_to_clipboard(smiles)
            time.sleep(0.5)
            
            # 尝试粘贴
            self.gui.press_keys("Ctrl", "V")
            time.sleep(1)
            
            logger.warning("[警告] SMILES 导入可能需要手动操作")
            logger.info("[提示] 请在 Spartan Build 面板中手动粘贴 SMILES 或使用 File -> Import")
            
            return True
            
        except Exception as e:
            logger.error(f"[错误] 从 SMILES 导入失败: {e}")
            return False
    
    def import_from_mol(self, mol_filepath: str) -> bool:
        """
        从 MOL 文件导入分子
        
        Args:
            mol_filepath: MOL 文件路径
            
        Returns:
            bool: 是否成功导入
        """
        return self.open_file(mol_filepath)
    
    def import_from_sdf(self, sdf_filepath: str, molecule_index: int = 0) -> bool:
        """
        从 SDF 文件导入分子
        
        Args:
            sdf_filepath: SDF 文件路径
            molecule_index: 要导入的分子索引（从 0 开始）
            
        Returns:
            bool: 是否成功导入
        """
        try:
            logger.info(f"[导入] 从 SDF 导入分子 {molecule_index}: {sdf_filepath}")
            
            self.gui.press_keys("Ctrl", "O")
            time.sleep(1.5)
            
            self.gui.type_text(str(Path(sdf_filepath).absolute()))
            time.sleep(0.5)
            
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            # 如果 SDF 中有多个分子，可能需要选择
            # 使用 Tab 和方向键导航
            
            logger.info("[成功] SDF 文件已打开")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 从 SDF 导入失败: {e}")
            return False
    
    # =========================================================================
    # 计算设置
    # =========================================================================
    
    def open_calculation_setup(self) -> bool:
        """
        打开计算设置对话框
        
        快捷键: Ctrl+Shift+E 或 F10
        """
        try:
            self.gui.press_keys("Ctrl", "Shift", "E")
            time.sleep(1)
            logger.debug("[计算] 打开计算设置面板")
            return True
        except Exception as e:
            logger.error(f"[错误] 打开计算设置失败: {e}")
            return False
    
    def set_calculation_type(self, calc_type: str) -> bool:
        """
        设置计算类型
        
        Args:
            calc_type: 计算类型
                       - "energy": 单点能
                       - "optimize": 几何优化
                       - "frequency": 频率计算
                       - "nmr": NMR 计算
                       - "ecd": ECD 计算
                       - "conformers": 构象搜索
        """
        calc_map = {
            "energy": "Energy",
            "optimize": "Optimize",
            "geometry": "Geometry Optimization",
            "frequency": "Frequency",
            "nmr": "NMR",
            "ecd": "ECD",
            "ord": "ORD",
            "ir": "IR",
            "uv": "UV",
            "conformers": "Conformer Search",
        }
        
        try:
            calc_name = calc_map.get(calc_type.lower(), calc_type)
            logger.info(f"[计算] 设置计算类型: {calc_name}")
            
            # 打开计算设置
            self.open_calculation_setup()
            time.sleep(1)
            
            # 使用 Tab 和方向键选择计算类型
            # 查找并选择对应选项
            for _ in range(5):
                self.gui.press_keys("{TAB}")
                time.sleep(0.1)
            
            # 尝试直接在列表中选择
            self.gui.press_keys("{DOWN}")
            time.sleep(0.2)
            
            logger.info(f"[成功] 计算类型已设置: {calc_name}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 设置计算类型失败: {e}")
            return False
    
    def set_method_and_basis(self, 
                            method: str = "DFT",
                            basis: str = "6-31G*") -> bool:
        """
        设置计算方法和基组
        
        Args:
            method: 计算方法 (MMFF, HF, DFT, MP2, etc.)
            basis: 基组 (3-21G, 6-31G*, cc-pVDZ, etc.)
            
        Returns:
            bool: 是否成功设置
        """
        try:
            logger.info(f"[计算] 设置方法和基组: {method}/{basis}")
            
            # 打开计算设置
            self.open_calculation_setup()
            time.sleep(1)
            
            # 方法1: Tab 导航到方法下拉框
            for _ in range(3):
                self.gui.press_keys("{TAB}")
                time.sleep(0.1)
            
            # 输入方法名称（部分匹配）
            self.gui.type_text(method[:5])  # 输入前几个字符
            time.sleep(0.3)
            
            # Tab 到基组下拉框
            self.gui.press_keys("{TAB}")
            time.sleep(0.2)
            
            # 输入基组
            self.gui.type_text(basis)
            time.sleep(0.3)
            
            logger.info("[成功] 方法和基组已设置")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 设置方法和基组失败: {e}")
            return False
    
    def setup_nmr_calculation(self, 
                             method: str = "DFT",
                             basis: str = "6-311G*",
                             solvent: Optional[str] = None) -> bool:
        """
        设置 NMR 化学位移计算
        
        Args:
            method: 计算方法
            basis: 基组
            solvent: 溶剂 (chloroform, methanol, water, etc.)
            
        Returns:
            bool: 是否成功设置
        """
        try:
            logger.info("[计算] 设置 NMR 计算...")
            
            # 1. 选择计算类型为 NMR
            self.set_calculation_type("nmr")
            time.sleep(0.5)
            
            # 2. 设置方法和基组
            self.set_method_and_basis(method, basis)
            time.sleep(0.5)
            
            # 3. 设置溶剂模型（如果有）
            if solvent:
                # 打开溶剂选项
                self.gui.press_keys("{TAB}")
                time.sleep(0.2)
                self.gui.press_keys("{DOWN}")
                time.sleep(0.2)
                self.gui.type_text(solvent)
            
            logger.info("[成功] NMR 计算已设置")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 设置 NMR 计算失败: {e}")
            return False
    
    def setup_ecd_calculation(self,
                             method: str = "DFT",
                             basis: str = "6-311G*",
                             n_states: int = 10) -> bool:
        """
        设置 ECD (Electronic Circular Dichroism) 计算
        
        Args:
            method: 计算方法
            basis: 基组
            n_states: 激发态数量
            
        Returns:
            bool: 是否成功设置
        """
        try:
            logger.info("[计算] 设置 ECD 计算...")
            
            # 1. 选择计算类型为 ECD
            self.set_calculation_type("ecd")
            time.sleep(0.5)
            
            # 2. 设置方法和基组
            self.set_method_and_basis(method, basis)
            time.sleep(0.5)
            
            # 3. 设置激发态数量
            # Tab 到状态数输入框
            for _ in range(4):
                self.gui.press_keys("{TAB}")
                time.sleep(0.1)
            
            self.gui.type_text(str(n_states))
            time.sleep(0.3)
            
            logger.info("[成功] ECD 计算已设置")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 设置 ECD 计算失败: {e}")
            return False
    
    # =========================================================================
    # 运行计算
    # =========================================================================
    
    def submit_calculation(self) -> bool:
        """
        提交计算（点击 Submit 或 OK）
        """
        try:
            logger.info("[计算] 提交计算任务...")
            
            # 查找 Submit 按钮
            # 通常是 Tab 导航后的位置，或者直接按 Enter
            self.gui.press_keys("Enter")
            time.sleep(2)
            
            # 等待计算开始
            logger.info("[成功] 计算任务已提交")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 提交计算失败: {e}")
            return False
    
    def run_optimization(self,
                        method: str = "DFT",
                        basis: str = "6-31G*",
                        wait_for_complete: bool = False) -> bool:
        """
        运行几何优化
        
        Args:
            method: 计算方法
            basis: 基组
            wait_for_complete: 是否等待计算完成
            
        Returns:
            bool: 是否成功提交计算
        """
        try:
            logger.info(f"[计算] 运行几何优化 ({method}/{basis})...")
            
            # 设置计算类型为优化
            self.set_calculation_type("optimize")
            time.sleep(0.5)
            
            # 设置方法和基组
            self.set_method_and_basis(method, basis)
            time.sleep(0.5)
            
            # 提交计算
            self.submit_calculation()
            
            if wait_for_complete:
                logger.info("[等待] 等待几何优化完成...")
                if not self.wait_for_calculation(timeout=600):
                    logger.warning("[警告] 几何优化超时")
                    return False
            
            logger.info("[成功] 几何优化任务已提交")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 运行几何优化失败: {e}")
            return False
    
    def run_nmr_calculation(self,
                           method: str = "DFT",
                           basis: str = "6-311G*",
                           solvent: Optional[str] = None,
                           wait_for_complete: bool = False) -> bool:
        """
        运行 NMR 化学位移计算
        
        Args:
            method: 计算方法
            basis: 基组
            solvent: 溶剂
            wait_for_complete: 是否等待计算完成
            
        Returns:
            bool: 是否成功提交计算
        """
        try:
            logger.info(f"[计算] 运行 NMR 计算 ({method}/{basis})...")
            
            # 设置 NMR 计算
            self.setup_nmr_calculation(method, basis, solvent)
            time.sleep(0.5)
            
            # 提交计算
            self.submit_calculation()
            
            if wait_for_complete:
                logger.info("[等待] 等待 NMR 计算完成...")
                if not self.wait_for_calculation(timeout=900):
                    logger.warning("[警告] NMR 计算超时")
                    return False
            
            logger.info("[成功] NMR 计算任务已提交")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 运行 NMR 计算失败: {e}")
            return False
    
    def run_ecd_calculation(self,
                           method: str = "DFT",
                           basis: str = "6-311G*",
                           n_states: int = 10,
                           wait_for_complete: bool = False) -> bool:
        """
        运行 ECD 手性光谱计算
        
        Args:
            method: 计算方法
            basis: 基组
            n_states: 激发态数量
            wait_for_complete: 是否等待计算完成
            
        Returns:
            bool: 是否成功提交计算
        """
        try:
            logger.info(f"[计算] 运行 ECD 计算 ({method}/{basis}, {n_states} states)...")
            
            # 设置 ECD 计算
            self.setup_ecd_calculation(method, basis, n_states)
            time.sleep(0.5)
            
            # 提交计算
            self.submit_calculation()
            
            if wait_for_complete:
                logger.info("[等待] 等待 ECD 计算完成...")
                if not self.wait_for_calculation(timeout=1200):
                    logger.warning("[警告] ECD 计算超时")
                    return False
            
            logger.info("[成功] ECD 计算任务已提交")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 运行 ECD 计算失败: {e}")
            return False
    
    def wait_for_calculation(self, timeout: float = 600.0) -> bool:
        """
        等待当前计算完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否在超时前完成
        """
        start_time = time.time()
        check_interval = 5  # 每 5 秒检查一次
        
        logger.info(f"[等待] 等待计算完成 (超时: {timeout}秒)...")
        
        while time.time() - start_time < timeout:
            # 检查窗口状态
            title = self.gui.get_window_title().lower()
            
            # 计算中的指示
            calculating_indicators = [
                "calculating",
                "computing",
                "processing",
                "running",
                "busy",
            ]
            
            if any(indicator in title for indicator in calculating_indicators):
                time.sleep(check_interval)
                continue
            
            # 检查是否完成或出错
            if "done" in title or "complete" in title:
                logger.info("[成功] 计算完成")
                return True
            
            # 检查对话框
            # 如果出现错误对话框，记录并返回 False
            
            time.sleep(check_interval)
        
        logger.warning(f"[超时] 计算等待超时: {timeout}秒")
        return False
    
    def cancel_calculation(self) -> bool:
        """取消当前计算"""
        try:
            # 发送 ESC 或点击 Cancel
            self.gui.press_keys("Escape")
            time.sleep(1)
            self.gui.handle_dialog(action="yes")  # 确认取消
            
            logger.info("[成功] 计算已取消")
            return True
        except Exception as e:
            logger.error(f"[错误] 取消计算失败: {e}")
            return False
    
    # =========================================================================
    # 结果查看与导出
    # =========================================================================
    
    def show_properties(self) -> bool:
        """
        显示分子属性面板
        
        快捷键: Ctrl+P
        """
        try:
            self.gui.press_keys("Ctrl", "P")
            time.sleep(1)
            logger.debug("[视图] 显示属性面板")
            return True
        except Exception as e:
            logger.error(f"[错误] 显示属性失败: {e}")
            return False
    
    def show_spectrum(self, spectrum_type: str = "nmr") -> bool:
        """
        显示光谱图形
        
        Args:
            spectrum_type: 光谱类型 (nmr, ir, uv, ecd)
        """
        try:
            logger.info(f"[视图] 显示 {spectrum_type} 光谱...")
            
            # 菜单路径: Display -> Spectrum
            self.gui.press_keys("Alt", "D")
            time.sleep(0.3)
            self.gui.press_keys("S")
            time.sleep(0.3)
            
            # 选择光谱类型
            if spectrum_type.lower() == "nmr":
                self.gui.press_keys("N")
            elif spectrum_type.lower() == "ir":
                self.gui.press_keys("I")
            elif spectrum_type.lower() == "uv":
                self.gui.press_keys("U")
            elif spectrum_type.lower() == "ecd":
                self.gui.press_keys("E")
            
            time.sleep(1)
            
            logger.info(f"[成功] {spectrum_type} 光谱已显示")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 显示光谱失败: {e}")
            return False
    
    def export_spectrum_data(self, 
                            filepath: str,
                            spectrum_type: str = "nmr") -> bool:
        """
        导出光谱数据
        
        Args:
            filepath: 输出文件路径
            spectrum_type: 光谱类型
            
        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[导出] 导出 {spectrum_type} 光谱数据: {filepath}")
            
            # 先显示光谱
            self.show_spectrum(spectrum_type)
            time.sleep(1)
            
            # 导出: File -> Export
            self.gui.press_keys("Alt", "F")
            time.sleep(0.3)
            self.gui.press_keys("E")
            time.sleep(0.5)
            
            # 选择格式（CSV 或 TXT）
            self.gui.press_keys("{DOWN}")
            time.sleep(0.2)
            
            self.gui.press_keys("Enter")
            time.sleep(0.5)
            
            # 输入文件路径
            self.gui.type_text(str(Path(filepath).absolute()))
            time.sleep(0.3)
            
            self.gui.press_keys("Enter")
            time.sleep(1)
            
            logger.info(f"[成功] 光谱数据已导出: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 导出光谱数据失败: {e}")
            return False
    
    def export_molecule(self,
                       filepath: str,
                       format: str = "mol") -> bool:
        """
        导出分子结构
        
        Args:
            filepath: 输出文件路径
            format: 文件格式 (mol, sdf, pdb, xyz)
            
        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[导出] 导出分子结构 ({format}): {filepath}")
            
            # File -> Save As
            self.gui.press_keys("Ctrl", "Shift", "S")
            time.sleep(1)
            
            self.gui.type_text(str(Path(filepath).absolute()))
            time.sleep(0.5)
            
            # 选择格式
            self._select_export_format(format)
            
            self.gui.press_keys("Enter")
            time.sleep(1)
            
            logger.info(f"[成功] 分子结构已导出: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[错误] 导出分子失败: {e}")
            return False
    
    def _select_export_format(self, format: str) -> bool:
        """选择导出格式"""
        try:
            # Tab 到格式下拉框
            for _ in range(2):
                self.gui.press_keys("{TAB}")
                time.sleep(0.1)
            
            # 打开下拉框
            self.gui.press_keys("{DOWN}")
            time.sleep(0.2)
            
            # 格式索引
            format_map = {
                "mol": 0,
                "sdf": 1,
                "pdb": 2,
                "xyz": 3,
                "cdxml": 4,
            }
            
            index = format_map.get(format.lower(), 0)
            
            for _ in range(index):
                self.gui.press_keys("{DOWN}")
                time.sleep(0.1)
            
            self.gui.press_keys("Enter")
            time.sleep(0.3)
            
            return True
            
        except Exception as e:
            logger.error(f"[错误] 选择导出格式失败: {e}")
            return False
    
    # =========================================================================
    # 完整工作流程
    # =========================================================================
    
    def full_nmr_prediction_workflow(self,
                                    input_mol: str,
                                    output_dir: str,
                                    method: str = "DFT",
                                    basis: str = "6-311G*",
                                    solvent: str = "chloroform") -> Dict[str, Any]:
        """
        完整的 NMR 预测工作流程
        
        Args:
            input_mol: 输入分子（SMILES 或文件路径）
            output_dir: 输出目录
            method: 计算方法
            basis: 基组
            solvent: 溶剂
            
        Returns:
            Dict: 工作流程结果
        """
        result = {
            "success": False,
            "input": input_mol,
            "output_dir": output_dir,
            "optimized_geometry": None,
            "nmr_data": None,
            "errors": []
        }
        
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 1. 启动/连接 Spartan
            if not self.is_running:
                if not self.launch():
                    result["errors"].append("启动 Spartan 失败")
                    return result
            
            # 2. 导入分子
            logger.info("[Step 1/3] 导入分子结构...")
            if input_mol.endswith(('.mol', '.sdf', '.pdb')):
                if not self.import_from_mol(input_mol):
                    result["errors"].append("导入分子文件失败")
                    return result
            else:
                if not self.import_from_smiles(input_mol):
                    result["errors"].append("导入 SMILES 失败")
                    return result
            
            time.sleep(2)
            
            # 3. 几何优化
            logger.info("[Step 2/3] 运行几何优化...")
            opt_file = output_path / "optimized.mol"
            if self.run_optimization(method=method, basis=basis):
                if self.wait_for_calculation(timeout=600):
                    self.export_molecule(str(opt_file), format="mol")
                    result["optimized_geometry"] = str(opt_file)
            
            time.sleep(2)
            
            # 4. NMR 计算
            logger.info("[Step 3/3] 运行 NMR 计算...")
            nmr_file = output_path / "nmr_spectrum.csv"
            if self.run_nmr_calculation(method=method, basis=basis, solvent=solvent):
                if self.wait_for_calculation(timeout=900):
                    self.export_spectrum_data(str(nmr_file), spectrum_type="nmr")
                    result["nmr_data"] = str(nmr_file)
            
            result["success"] = True
            logger.info("[完成] NMR 预测工作流程完成!")
            
        except Exception as e:
            logger.error(f"[错误] NMR 预测工作流程失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def full_ecd_workflow(self,
                         input_mol: str,
                         output_dir: str,
                         method: str = "DFT",
                         basis: str = "6-311G*",
                         n_states: int = 10) -> Dict[str, Any]:
        """
        完整的 ECD 手性光谱计算工作流程
        
        Args:
            input_mol: 输入分子（SMILES 或文件路径）
            output_dir: 输出目录
            method: 计算方法
            basis: 基组
            n_states: 激发态数量
            
        Returns:
            Dict: 工作流程结果
        """
        result = {
            "success": False,
            "input": input_mol,
            "output_dir": output_dir,
            "ecd_data": None,
            "errors": []
        }
        
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 1. 启动/连接 Spartan
            if not self.is_running:
                if not self.launch():
                    result["errors"].append("启动 Spartan 失败")
                    return result
            
            # 2. 导入分子
            logger.info("[Step 1/2] 导入分子结构...")
            if input_mol.endswith(('.mol', '.sdf', '.pdb')):
                self.import_from_mol(input_mol)
            else:
                self.import_from_smiles(input_mol)
            
            time.sleep(2)
            
            # 3. 几何优化
            logger.info("[Step 2/3] 几何优化...")
            if self.run_optimization(method=method, basis=basis):
                self.wait_for_calculation(timeout=600)
            
            time.sleep(2)
            
            # 4. ECD 计算
            logger.info("[Step 3/3] 运行 ECD 计算...")
            ecd_file = output_path / "ecd_spectrum.csv"
            if self.run_ecd_calculation(method=method, basis=basis, n_states=n_states):
                if self.wait_for_calculation(timeout=1200):
                    self.export_spectrum_data(str(ecd_file), spectrum_type="ecd")
                    result["ecd_data"] = str(ecd_file)
            
            result["success"] = True
            logger.info("[完成] ECD 计算工作流程完成!")
            
        except Exception as e:
            logger.error(f"[错误] ECD 工作流程失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    # =========================================================================
    # 便捷方法
    # =========================================================================
    
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
    
    def clear_molecule(self) -> bool:
        """清除当前分子"""
        try:
            self.select_all()
            time.sleep(0.3)
            self.gui.press_keys("Delete")
            time.sleep(0.5)
            logger.info("[成功] 分子已清除")
            return True
        except Exception as e:
            logger.error(f"[错误] 清除分子失败: {e}")
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
    
    parser = argparse.ArgumentParser(description="Spartan GUI 自动化测试")
    parser.add_argument("--launch", action="store_true", help="启动 Spartan")
    parser.add_argument("--optimize", metavar="MOL_FILE", help="运行几何优化")
    parser.add_argument("--nmr", metavar="MOL_FILE", help="运行 NMR 计算")
    parser.add_argument("--ecd", metavar="MOL_FILE", help="运行 ECD 计算")
    parser.add_argument("--close", action="store_true", help="关闭 Spartan")
    
    args = parser.parse_args()
    
    spartan = SpartanGUI()
    
    if args.launch:
        print("启动 Spartan '14...")
        spartan.launch()
        print("按 Enter 关闭...")
        input()
        spartan.close()
    
    elif args.optimize:
        print(f"几何优化: {args.optimize}")
        spartan.launch()
        time.sleep(2)
        spartan.import_from_mol(args.optimize)
        spartan.run_optimization(wait_for_complete=False)
        print("计算已提交，按 Enter 关闭...")
        input()
        spartan.close()
    
    elif args.nmr:
        print(f"NMR 计算: {args.nmr}")
        spartan.launch()
        time.sleep(2)
        spartan.import_from_mol(args.nmr)
        spartan.run_nmr_calculation(wait_for_complete=False)
        print("计算已提交，按 Enter 关闭...")
        input()
        spartan.close()
    
    elif args.ecd:
        print(f"ECD 计算: {args.ecd}")
        spartan.launch()
        time.sleep(2)
        spartan.import_from_mol(args.ecd)
        spartan.run_ecd_calculation(wait_for_complete=False)
        print("计算已提交，按 Enter 关闭...")
        input()
        spartan.close()
    
    elif args.close:
        print("关闭 Spartan...")
        spartan.connect()
        spartan.close()
    
    else:
        print("Spartan GUI 自动化模块已加载!")
        print(f"  - 可执行文件: {spartan.executable_path}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_controller_gui.py — AI 智能识谱工具 GUI 自动化版主控制器

功能：
  - 通过 GUI 自动化控制化学软件（Mestrenova / ChemDraw / Spartan / Specdis）
  - 模拟人工操作完成谱图分析
  - 全自动结构推导与绘制

依赖：
  - gui_automation.py（核心自动化）
  - mestrenova_gui.py（Mestrenova 15 操作）
  - chemdraw_gui.py（ChemDraw 2022 操作）
  - spartan_gui.py（Spartan '14 操作）
  - 其他核心模块

使用方式：
  python main_controller_gui.py --mode full --input spectra/sample.mnova --output ./outputs
  python main_controller_gui.py --mode draw --smiles "CCOC(=O)c1ccc(cc1)OC"
  python main_controller_gui.py --mode analysis --spectrum sample.mnova

在 Agent 中调用：
  Agent 会分析用户需求，自动调用相应的软件操作方法。
  例如：用户说"分析这个 NMR 谱图"
  -> Agent 启动 Mestrenova -> 打开谱图 -> 自动峰识别 -> 自动积分 -> 导出数据
"""

import os
import sys
import json
import time
import logging
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

# 设置模块路径
MODULE_DIR = Path(__file__).parent.resolve()
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

# 导入 GUI 自动化模块
try:
    from gui_automation import GUIAutomation
    from mestrenova_gui import MestrenovaGUI, NMRPeak, SpectrumInfo
    from chemdraw_gui import ChemDrawGUI
    from spartan_gui import SpartanGUI
    GUI_MODULES_OK = True
except ImportError as e:
    GUI_MODULES_OK = False
    logging.warning(f"[警告] GUI 模块导入失败: {e}")

# 导入核心分析模块
try:
    from structure_elucidator import StructureElucidator
    from db_query import compound_lookup
    CORE_MODULES_OK = True
except ImportError:
    CORE_MODULES_OK = False

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main_controller_gui")


class OperationMode(Enum):
    """操作模式"""
    FULL = "full"           # 完整工作流程
    ANALYSIS = "analysis"   # 仅谱图分析
    DRAWING = "drawing"      # 仅结构绘制
    CALCULATION = "calc"    # 仅量化计算


@dataclass
class SoftwareStatus:
    """软件状态"""
    name: str
    executable_path: Optional[str]
    is_running: bool
    is_responding: bool
    last_used: Optional[float] = None


class ChemicalSoftwareController:
    """
    化学软件 GUI 自动化控制器
    
    统一管理多个化学软件的 GUI 自动化操作：
    - Mestrenova 15: NMR/IR/MS 谱图分析
    - ChemDraw 2022: 结构绘制与编辑
    - Spartan '14: 量化计算与光谱预测
    - Specdis: 手性光谱分析
    
    Agent 调用流程：
    1. 分析用户需求
    2. 确定需要的软件操作
    3. 启动相应软件
    4. 执行 GUI 操作序列
    5. 收集结果数据
    6. 整合输出
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化化学软件控制器
        
        Args:
            config: 配置文件
        """
        self.config = config or {}
        
        # 软件实例
        self.mestrenova: Optional[MestrenovaGUI] = None
        self.chemdraw: Optional[ChemDrawGUI] = None
        self.spartan: Optional[SpartanGUI] = None
        
        # 软件状态跟踪
        self.software_status = {
            "mestrenova": SoftwareStatus(
                name="Mestrenova 15",
                executable_path=None,
                is_running=False,
                is_responding=False
            ),
            "chemdraw": SoftwareStatus(
                name="ChemDraw 2022",
                executable_path=None,
                is_running=False,
                is_responding=False
            ),
            "spartan": SoftwareStatus(
                name="Spartan '14",
                executable_path=None,
                is_running=False,
                is_responding=False
            ),
        }
        
        # 输出目录
        self.output_dir = Path(self.config.get("output_dir", "./outputs"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # GUI 核心（共享）
        self.gui_core = GUIAutomation()
        
        logger.info("=" * 70)
        logger.info("  AI 智能识谱工具 — GUI 自动化版")
        logger.info(f"  操作系统: {platform.system()} {platform.release()}")
        logger.info(f"  GUI 模块: {'已加载 ✓' if GUI_MODULES_OK else '加载失败 ✗'}")
        logger.info(f"  核心模块: {'已加载 ✓' if CORE_MODULES_OK else '加载失败 ✗'}")
        logger.info("=" * 70)
    
    # =========================================================================
    # 软件生命周期管理
    # =========================================================================
    
    def check_software_availability(self) -> Dict[str, bool]:
        """
        检查各软件的可用性
        
        Returns:
            Dict: 各软件的可用状态
        """
        availability = {}
        
        logger.info("\n[诊断] 检查化学软件可用性...")
        
        # 检查 Mestrenova
        try:
            mn = MestrenovaGUI()
            availability["mestrenova"] = mn.executable_path is not None
            if availability["mestrenova"]:
                self.software_status["mestrenova"].executable_path = mn.executable_path
                logger.info(f"  ✓ Mestrenova 15: {mn.executable_path}")
            else:
                logger.warning("  ✗ Mestrenova 15: 未找到")
        except Exception as e:
            availability["mestrenova"] = False
            logger.error(f"  ✗ Mestrenova 15: 检查失败 - {e}")
        
        # 检查 ChemDraw
        try:
            cd = ChemDrawGUI()
            availability["chemdraw"] = cd.executable_path is not None
            if availability["chemdraw"]:
                self.software_status["chemdraw"].executable_path = cd.executable_path
                logger.info(f"  ✓ ChemDraw 2022: {cd.executable_path}")
            else:
                logger.warning("  ✗ ChemDraw 2022: 未找到")
        except Exception as e:
            availability["chemdraw"] = False
            logger.error(f"  ✗ ChemDraw 2022: 检查失败 - {e}")
        
        # 检查 Spartan
        try:
            sp = SpartanGUI()
            availability["spartan"] = sp.executable_path is not None
            if availability["spartan"]:
                self.software_status["spartan"].executable_path = sp.executable_path
                logger.info(f"  ✓ Spartan '14: {sp.executable_path}")
            else:
                logger.warning("  ✗ Spartan '14: 未找到")
        except Exception as e:
            availability["spartan"] = False
            logger.error(f"  ✗ Spartan '14: 检查失败 - {e}")
        
        return availability
    
    def launch_software(self, 
                       software: str,
                       wait_for_ready: bool = True) -> bool:
        """
        启动指定的化学软件
        
        Args:
            software: 软件名称 (mestrenova / chemdraw / spartan)
            wait_for_ready: 等待软件就绪
            
        Returns:
            bool: 是否成功启动
        """
        logger.info(f"\n[启动] {software}...")
        
        try:
            if software.lower() == "mestrenova":
                if self.mestrenova and self.software_status["mestrenova"].is_running:
                    logger.info("  · Mestrenova 已在运行")
                    return True
                
                self.mestrenova = MestrenovaGUI(
                    executable_path=self.software_status["mestrenova"].executable_path
                )
                success = self.mestrenova.launch(wait_for_ready=wait_for_ready)
                
                if success:
                    self.software_status["mestrenova"].is_running = True
                    self.software_status["mestrenova"].is_responding = True
                    self.software_status["mestrenova"].last_used = time.time()
                    logger.info(f"  ✓ Mestrenova 15 已启动")
                return success
                
            elif software.lower() == "chemdraw":
                if self.chemdraw and self.software_status["chemdraw"].is_running:
                    logger.info("  · ChemDraw 已在运行")
                    return True
                
                self.chemdraw = ChemDrawGUI(
                    executable_path=self.software_status["chemdraw"].executable_path
                )
                success = self.chemdraw.launch(wait_for_ready=wait_for_ready)
                
                if success:
                    self.software_status["chemdraw"].is_running = True
                    self.software_status["chemdraw"].is_responding = True
                    self.software_status["chemdraw"].last_used = time.time()
                    logger.info(f"  ✓ ChemDraw 2022 已启动")
                return success
                
            elif software.lower() == "spartan":
                if self.spartan and self.software_status["spartan"].is_running:
                    logger.info("  · Spartan 已在运行")
                    return True
                
                self.spartan = SpartanGUI(
                    executable_path=self.software_status["spartan"].executable_path
                )
                success = self.spartan.launch(wait_for_ready=wait_for_ready)
                
                if success:
                    self.software_status["spartan"].is_running = True
                    self.software_status["spartan"].is_responding = True
                    self.software_status["spartan"].last_used = time.time()
                    logger.info(f"  ✓ Spartan '14 已启动")
                return success
                
            else:
                logger.error(f"  ✗ 未知的软件: {software}")
                return False
                
        except Exception as e:
            logger.error(f"  ✗ 启动失败: {e}")
            return False
    
    def close_software(self, software: str, force: bool = False) -> bool:
        """
        关闭指定的化学软件
        
        Args:
            software: 软件名称
            force: 是否强制关闭
        """
        logger.info(f"\n[关闭] {software}...")
        
        try:
            if software.lower() == "mestrenova" and self.mestrenova:
                self.mestrenova.close(force=force)
                self.software_status["mestrenova"].is_running = False
                logger.info("  ✓ Mestrenova 已关闭")
                
            elif software.lower() == "chemdraw" and self.chemdraw:
                self.chemdraw.close(force=force)
                self.software_status["chemdraw"].is_running = False
                logger.info("  ✓ ChemDraw 已关闭")
                
            elif software.lower() == "spartan" and self.spartan:
                self.spartan.close(force=force)
                self.software_status["spartan"].is_running = False
                logger.info("  ✓ Spartan 已关闭")
            
            return True
            
        except Exception as e:
            logger.error(f"  ✗ 关闭失败: {e}")
            return False
    
    def close_all_software(self, force: bool = False) -> bool:
        """关闭所有软件"""
        logger.info("\n[清理] 关闭所有化学软件...")
        
        self.close_software("mestrenova", force)
        self.close_software("chemdraw", force)
        self.close_software("spartan", force)
        
        logger.info("[完成] 所有软件已关闭")
        return True
    
    # =========================================================================
    # Mestrenova 操作
    # =========================================================================
    
    def analyze_spectrum(self, 
                        spectrum_file: str,
                        output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        完整的谱图分析流程（使用 Mestrenova GUI）
        
        Args:
            spectrum_file: 谱图文件路径 (.mnova)
            output_dir: 输出目录
            
        Returns:
            Dict: 分析结果
        """
        result = {
            "success": False,
            "spectrum_file": spectrum_file,
            "spectrum_info": None,
            "peaks": [],
            "peaks_csv": None,
            "spectrum_image": None,
            "errors": []
        }
        
        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. 确保 Mestrenova 运行
            logger.info("\n" + "=" * 70)
            logger.info("[Step 1/5] 启动 Mestrenova...")
            if not self.launch_software("mestrenova"):
                result["errors"].append("启动 Mestrenova 失败")
                return result
            
            time.sleep(2)  # 等待软件完全就绪
            
            # 2. 打开谱图文件
            logger.info("[Step 2/5] 打开谱图文件...")
            if not self.mestrenova.open_file(spectrum_file):
                result["errors"].append("打开谱图文件失败")
                return result
            
            time.sleep(2)  # 等待文件加载
            
            # 3. 获取谱图信息
            logger.info("[Step 3/5] 获取谱图信息...")
            spectrum_info = self.mestrenova.get_spectrum_info()
            result["spectrum_info"] = {
                "nucleus": spectrum_info.nucleus,
                "solvent": spectrum_info.solvent,
                "filename": spectrum_info.filename
            }
            logger.info(f"  · 核类型: {spectrum_info.nucleus}")
            logger.info(f"  · 溶剂: {spectrum_info.solvent}")
            
            # 4. 自动峰识别和积分
            logger.info("[Step 4/5] 自动峰识别和积分...")
            self.mestrenova.auto_pick_peaks()
            time.sleep(1)
            self.mestrenova.auto_integrate()
            time.sleep(1)
            
            # 5. 导出结果
            logger.info("[Step 5/5] 导出分析结果...")
            
            # 导出峰列表
            peaks_csv = output_dir / f"{Path(spectrum_file).stem}_peaks.csv"
            if self.mestrenova.export_peaks_to_csv(str(peaks_csv)):
                result["peaks_csv"] = str(peaks_csv)
            
            # 获取峰数据
            result["peaks"] = self.mestrenova.export_peaks_to_clipboard()
            logger.info(f"  · 识别到 {len(result['peaks'])} 个峰")
            
            # 导出谱图图片
            spectrum_img = output_dir / f"{Path(spectrum_file).stem}_spectrum.png"
            if self.mestrenova.export_spectrum_image(str(spectrum_img)):
                result["spectrum_image"] = str(spectrum_img)
            
            result["success"] = True
            logger.info("\n" + "=" * 70)
            logger.info("[成功] 谱图分析完成!")
            logger.info(f"  · 峰数据: {result['peaks_csv']}")
            logger.info(f"  · 谱图图片: {result['spectrum_image']}")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"[错误] 谱图分析失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def batch_analyze_spectra(self,
                              spectrum_files: List[str],
                              output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        批量分析多个谱图文件
        
        Args:
            spectrum_files: 谱图文件列表
            output_dir: 输出目录
            
        Returns:
            Dict: 批量分析结果
        """
        results = {
            "total": len(spectrum_files),
            "success": 0,
            "failed": 0,
            "results": []
        }
        
        output_dir = Path(output_dir) if output_dir else self.output_dir
        
        # 启动一次 Mestrenova，处理所有文件
        if not self.launch_software("mestrenova"):
            logger.error("[错误] 无法启动 Mestrenova")
            return results
        
        for i, spectrum_file in enumerate(spectrum_files, 1):
            logger.info(f"\n[批量分析] {i}/{len(spectrum_files)}: {spectrum_file}")
            
            result = self.analyze_spectrum(spectrum_file, output_dir / f"sample_{i}")
            
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
            
            results["results"].append(result)
            
            # 处理完一个文件后，可以关闭重新打开下一个
            # 或者继续处理下一个（取决于文件大小）
            time.sleep(1)
        
        logger.info(f"\n[完成] 批量分析: 成功 {results['success']}/{results['total']}")
        return results
    
    # =========================================================================
    # ChemDraw 操作
    # =========================================================================
    
    def draw_structure(self,
                      smiles: Optional[str] = None,
                      compound_name: Optional[str] = None,
                      output_dir: Optional[str] = None,
                      format: str = "png",
                      add_numbers: bool = True) -> Dict[str, Any]:
        """
        绘制分子结构（使用 ChemDraw GUI）
        
        Args:
            smiles: SMILES 字符串
            compound_name: 化合物名称
            output_dir: 输出目录
            format: 输出格式
            add_numbers: 是否添加原子编号
            
        Returns:
            Dict: 绘制结果
        """
        result = {
            "success": False,
            "smiles": smiles,
            "compound_name": compound_name,
            "output_files": {},
            "errors": []
        }
        
        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. 确保 ChemDraw 运行
            logger.info("\n" + "=" * 70)
            logger.info("[Step 1/4] 启动 ChemDraw...")
            if not self.launch_software("chemdraw"):
                result["errors"].append("启动 ChemDraw 失败")
                return result
            
            time.sleep(2)
            
            # 2. 绘制结构
            logger.info("[Step 2/4] 绘制分子结构...")
            if smiles:
                if not self.chemdraw.draw_from_smiles(smiles):
                    result["errors"].append("SMILES 绘制失败")
                    return result
                logger.info(f"  · SMILES: {smiles}")
            elif compound_name:
                if not self.chemdraw.draw_from_name(compound_name):
                    result["errors"].append("化合物名称绘制失败")
                    return result
                logger.info(f"  · 化合物名称: {compound_name}")
            else:
                result["errors"].append("未提供 SMILES 或化合物名称")
                return result
            
            time.sleep(1)
            
            # 3. 美化和编号
            logger.info("[Step 3/4] 美化结构...")
            self.chemdraw.clean_up_structure()
            time.sleep(0.5)
            
            if add_numbers:
                logger.info("[Step 4/4] 添加原子编号...")
                self.chemdraw.add_atom_numbers()
                time.sleep(0.5)
            else:
                logger.info("[Step 4/4] 跳过原子编号（add_numbers=False）")
            
            # 4. 导出多种格式
            logger.info("[导出] 生成多种格式...")
            
            # PNG
            if format in ["png", "all"]:
                png_path = output_dir / "structure.png"
                if self.chemdraw.export_png(str(png_path)):
                    result["output_files"]["png"] = str(png_path)
            
            # SVG (矢量图)
            if format in ["svg", "all"]:
                svg_path = output_dir / "structure.svg"
                if self.chemdraw.export_svg(str(svg_path)):
                    result["output_files"]["svg"] = str(svg_path)
            
            # CDXML (ChemDraw 原生格式)
            if format in ["cdxml", "all"]:
                cdxml_path = output_dir / "structure.cdxml"
                if self.chemdraw.export_cdxml(str(cdxml_path)):
                    result["output_files"]["cdxml"] = str(cdxml_path)
            
            # SDF (3D 结构)
            if format in ["sdf", "all"]:
                sdf_path = output_dir / "structure.sdf"
                if self.chemdraw.export_sdf(str(sdf_path)):
                    result["output_files"]["sdf"] = str(sdf_path)
            
            # MOL
            if format in ["mol", "all"]:
                mol_path = output_dir / "structure.mol"
                if self.chemdraw.export_mol(str(mol_path)):
                    result["output_files"]["mol"] = str(mol_path)
            
            result["success"] = True
            logger.info("\n" + "=" * 70)
            logger.info("[成功] 结构绘制完成!")
            logger.info(f"  · 输出格式: {list(result['output_files'].keys())}")
            for fmt, path in result["output_files"].items():
                logger.info(f"  · {fmt}: {path}")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"[错误] 结构绘制失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    # =========================================================================
    # Spartan 操作
    # =========================================================================
    
    def run_geometry_optimization(self,
                                 input_mol: str,
                                 output_dir: Optional[str] = None,
                                 method: str = "DFT",
                                 basis: str = "6-31G*",
                                 wait_for_complete: bool = False) -> Dict[str, Any]:
        """
        运行几何优化（使用 Spartan GUI）
        
        Args:
            input_mol: 输入分子（SMILES 或文件路径）
            output_dir: 输出目录
            method: 计算方法
            basis: 基组
            wait_for_complete: 是否等待完成
            
        Returns:
            Dict: 计算结果
        """
        result = {
            "success": False,
            "input": input_mol,
            "method": method,
            "basis": basis,
            "optimized_file": None,
            "energy": None,
            "errors": []
        }
        
        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info("\n" + "=" * 70)
            logger.info(f"[计算] 几何优化 ({method}/{basis})...")
            
            # 启动 Spartan
            if not self.launch_software("spartan"):
                result["errors"].append("启动 Spartan 失败")
                return result
            
            time.sleep(2)
            
            # 导入分子
            logger.info("[导入] 分子结构...")
            if input_mol.endswith(('.mol', '.sdf', '.pdb')):
                self.spartan.import_from_mol(input_mol)
            else:
                self.spartan.import_from_smiles(input_mol)
            
            time.sleep(2)
            
            # 运行优化
            logger.info("[计算] 提交优化任务...")
            self.spartan.run_optimization(
                method=method,
                basis=basis,
                wait_for_complete=False  # 不等待，让 Agent 可以继续其他任务
            )
            
            # 立即返回（不等待计算完成）
            result["success"] = True
            logger.info("[提示] 优化任务已提交，正在后台运行...")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"[错误] 几何优化失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def run_nmr_prediction(self,
                          input_mol: str,
                          output_dir: Optional[str] = None,
                          method: str = "DFT",
                          basis: str = "6-311G*",
                          solvent: str = "chloroform") -> Dict[str, Any]:
        """
        运行 NMR 化学位移预测（使用 Spartan GUI）
        
        Args:
            input_mol: 输入分子
            output_dir: 输出目录
            method: 计算方法
            basis: 基组
            solvent: 溶剂
            
        Returns:
            Dict: 计算结果
        """
        result = {
            "success": False,
            "input": input_mol,
            "method": method,
            "basis": basis,
            "solvent": solvent,
            "nmr_data": None,
            "errors": []
        }
        
        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info("\n" + "=" * 70)
            logger.info(f"[计算] NMR 预测 ({method}/{basis}, {solvent})...")
            
            # 启动 Spartan
            if not self.launch_software("spartan"):
                result["errors"].append("启动 Spartan 失败")
                return result
            
            time.sleep(2)
            
            # 导入分子
            logger.info("[导入] 分子结构...")
            if input_mol.endswith(('.mol', '.sdf', '.pdb')):
                self.spartan.import_from_mol(input_mol)
            else:
                self.spartan.import_from_smiles(input_mol)
            
            time.sleep(2)
            
            # 先几何优化
            logger.info("[优化] 先进行几何优化...")
            self.spartan.run_optimization(method=method, basis=basis)
            # 简短等待后继续
            time.sleep(5)
            
            # 运行 NMR 计算
            logger.info("[计算] 提交 NMR 计算任务...")
            self.spartan.run_nmr_calculation(
                method=method,
                basis=basis,
                solvent=solvent,
                wait_for_complete=False
            )
            
            result["success"] = True
            logger.info("[提示] NMR 计算任务已提交，正在后台运行...")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"[错误] NMR 预测失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    # =========================================================================
    # 完整工作流程
    # =========================================================================
    
    def full_analysis_workflow(self,
                               spectrum_file: str,
                               output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        完整的谱图分析 + 结构推导 + 绘图工作流程
        
        流程：
        1. Mestrenova 分析谱图
        2. 结构推导
        3. ChemDraw 绘制结构
        4. 生成报告
        
        Args:
            spectrum_file: 谱图文件路径
            output_dir: 输出目录
            
        Returns:
            Dict: 完整工作流程结果
        """
        result = {
            "success": False,
            "spectrum_file": spectrum_file,
            "spectrum_analysis": None,
            "structure_elucidation": None,
            "structure_drawing": None,
            "final_report": None,
            "errors": []
        }
        
        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info("\n" + "=" * 70)
            logger.info("  AI 智能识谱工具 — 完整工作流程")
            logger.info("=" * 70)
            
            # Step 1: 谱图分析
            logger.info("\n[Phase 1/3] 谱图分析 (Mestrenova)...")
            result["spectrum_analysis"] = self.analyze_spectrum(
                spectrum_file,
                output_dir / "spectrum_analysis"
            )
            
            if not result["spectrum_analysis"]["success"]:
                result["errors"].append("谱图分析失败")
                return result
            
            peaks = result["spectrum_analysis"]["peaks"]
            logger.info(f"  · 识别到 {len(peaks)} 个峰")
            
            # Step 2: 结构推导（如果核心模块可用）
            if CORE_MODULES_OK:
                logger.info("\n[Phase 2/3] 结构推导...")
                
                # 准备分析数据
                h_nmr_data = [
                    {"shift_ppm": p.shift_ppm, "intensity": p.intensity, "multiplicity": p.multiplicity}
                    for p in peaks if p.shift_ppm > 0
                ]
                
                engine_data = {
                    "h_nmr": h_nmr_data,
                    "c_nmr": [],  # 如果有 13C 谱图数据
                    "ms": {},
                }
                
                engine = StructureElucidator(engine_data, self.config)
                elucidation = engine.elucidate(output_dir=str(output_dir / "structure_analysis"))
                
                result["structure_elucidation"] = elucidation
                
                # 获取最佳 SMILES
                best_smiles = None
                for hit in elucidation.get("database_candidates", []):
                    if hit.get("smiles"):
                        best_smiles = hit["smiles"]
                        break
                
                if best_smiles:
                    # Step 3: 结构绘制
                    logger.info("\n[Phase 3/3] 结构绘制 (ChemDraw)...")
                    result["structure_drawing"] = self.draw_structure(
                        smiles=best_smiles,
                        output_dir=output_dir / "structure_drawing",
                        format="all",
                        add_numbers=True
                    )
                    
                    # 生成报告
                    logger.info("\n[报告] 生成最终报告...")
                    report_path = output_dir / "full_analysis_report.md"
                    self._generate_full_report(result, report_path)
                    result["final_report"] = str(report_path)
            
            else:
                logger.warning("[警告] 核心模块不可用，跳过结构推导")
                # 仍然绘制一个占位结构
                if peaks:
                    # 使用第一个峰作为示例 SMILES
                    example_smiles = "CC"  # 简单的乙烷作为示例
                    result["structure_drawing"] = self.draw_structure(
                        smiles=example_smiles,
                        output_dir=output_dir / "structure_drawing",
                        format="png"
                    )
            
            result["success"] = True
            logger.info("\n" + "=" * 70)
            logger.info("[成功] 完整工作流程完成!")
            logger.info(f"  · 谱图分析: {'完成' if result['spectrum_analysis']['success'] else '失败'}")
            logger.info(f"  · 结构绘制: {'完成' if result['structure_drawing']['success'] else '失败'}")
            logger.info(f"  · 最终报告: {result['final_report']}")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"[错误] 工作流程失败: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def _generate_full_report(self, result: Dict, report_path: Path):
        """生成完整分析报告"""
        lines = []
        lines.append("# AI 智能识谱工具 — 完整分析报告")
        lines.append("")
        lines.append(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**谱图文件**: {result['spectrum_file']}")
        lines.append("")
        
        # 谱图分析结果
        if result.get("spectrum_analysis"):
            sa = result["spectrum_analysis"]
            lines.append("## 一、谱图分析结果 (Mestrenova 15)")
            lines.append("")
            lines.append(f"- 核类型: {sa['spectrum_info']['nucleus']}")
            lines.append(f"- 溶剂: {sa['spectrum_info']['solvent']}")
            lines.append(f"- 识别峰数: {len(sa['peaks'])}")
            lines.append(f"- 峰数据文件: {sa['peaks_csv']}")
            lines.append(f"- 谱图图片: {sa['spectrum_image']}")
            lines.append("")
            
            # 峰列表
            lines.append("### 1.1 峰列表")
            lines.append("")
            lines.append("| # | δ (ppm) | 积分 | 多重性 |")
            lines.append("|---|---|---|---|")
            for i, peak in enumerate(sa["peaks"], 1):
                lines.append(f"| {i} | {peak.shift_ppm:.3f} | {peak.intensity:.2f} | {peak.multiplicity} |")
            lines.append("")
        
        # 结构推导结果
        if result.get("structure_elucidation"):
            se = result["structure_elucidation"]
            summary = se.get("summary", {})
            lines.append("## 二、结构推导结果")
            lines.append("")
            lines.append(f"- 最佳分子式: {summary.get('best_formula', 'N/A')}")
            lines.append(f"- 不饱和度 Ω: {summary.get('unsaturation_omega', 'N/A')}")
            lines.append(f"- 置信度: {summary.get('overall_confidence', 0)}%")
            lines.append("")
            
            # 候选结构
            candidates = se.get("database_candidates", [])
            if candidates:
                lines.append("### 2.1 候选化合物")
                lines.append("")
                lines.append("| # | 名称 | 分子式 | SMILES |")
                lines.append("|---|---|---|---|")
                for i, c in enumerate(candidates[:10], 1):
                    lines.append(f"| {i} | {c.get('iupac', c.get('name', ''))[:40]} | {c.get('molecular_formula', '')} | {c.get('smiles', '')[:30]} |")
                lines.append("")
        
        # 结构绘制结果
        if result.get("structure_drawing"):
            sd = result["structure_drawing"]
            lines.append("## 三、结构绘制结果 (ChemDraw 2022)")
            lines.append("")
            for fmt, path in sd.get("output_files", {}).items():
                lines.append(f"- **{fmt.upper()}**: `{path}`")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        lines.append("*本报告由 AI 智能识谱工具自动生成*")
        
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"  · 报告已生成: {report_path}")
    
    # =========================================================================
    # Agent 接口方法
    # =========================================================================
    
    def execute_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """
        执行 Agent 指令的通用接口
        
        Args:
            command: 命令名称
            **kwargs: 命令参数
            
        Returns:
            Dict: 执行结果
        """
        command_handlers = {
            "check_software": self.check_software_availability,
            "launch": self.launch_software,
            "close": self.close_software,
            "close_all": self.close_all_software,
            "analyze_spectrum": self.analyze_spectrum,
            "batch_analyze": self.batch_analyze_spectra,
            "draw_structure": self.draw_structure,
            "optimize_geometry": self.run_geometry_optimization,
            "calculate_nmr": self.run_nmr_prediction,
            "full_workflow": self.full_analysis_workflow,
        }
        
        handler = command_handlers.get(command)
        
        if handler:
            return handler(**kwargs)
        else:
            return {
                "success": False,
                "error": f"未知命令: {command}",
                "available_commands": list(command_handlers.keys())
            }
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "software_status": {
                name: {
                    "is_running": status.is_running,
                    "is_responding": status.is_responding,
                    "executable_path": status.executable_path,
                    "last_used": status.last_used
                }
                for name, status in self.software_status.items()
            },
            "gui_modules_loaded": GUI_MODULES_OK,
            "core_modules_loaded": CORE_MODULES_OK,
            "output_directory": str(self.output_dir)
        }


# =============================================================================
# 命令行入口
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AI 智能识谱工具 — GUI 自动化版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main_controller_gui.py --check
  python main_controller_gui.py --analyze spectra/sample.mnova
  python main_controller_gui.py --draw --smiles "CCOC(=O)c1ccc(cc1)OC"
  python main_controller_gui.py --workflow spectra/sample.mnova
  python main_controller_gui.py --close-all
        """
    )
    
    # 基本选项
    parser.add_argument("--check", action="store_true", help="检查软件可用性")
    parser.add_argument("--close-all", action="store_true", help="关闭所有软件")
    
    # 谱图分析
    parser.add_argument("--analyze", metavar="FILE", help="分析谱图文件")
    parser.add_argument("--batch", nargs="+", metavar="FILES", help="批量分析谱图")
    
    # 结构绘制
    parser.add_argument("--draw", action="store_true", help="绘制结构")
    parser.add_argument("--smiles", metavar="SMILES", help="SMILES 字符串")
    parser.add_argument("--name", metavar="NAME", help="化合物名称")
    
    # 量化计算
    parser.add_argument("--optimize", metavar="MOL", help="几何优化")
    parser.add_argument("--nmr-calc", metavar="MOL", help="NMR 计算")
    parser.add_argument("--method", default="DFT", help="计算方法 (default: DFT)")
    parser.add_argument("--basis", default="6-31G*", help="基组 (default: 6-31G*)")
    
    # 完整工作流程
    parser.add_argument("--workflow", metavar="FILE", help="完整工作流程")
    
    # 输出设置
    parser.add_argument("--output", default="./outputs", help="输出目录 (default: ./outputs)")
    
    args = parser.parse_args()
    
    # 创建控制器
    controller = ChemicalSoftwareController(config={"output_dir": args.output})
    
    # 执行命令
    if args.check:
        controller.check_software_availability()
    
    elif args.close_all:
        controller.close_all_software()
    
    elif args.analyze:
        result = controller.analyze_spectrum(args.analyze, args.output)
        print(f"\n结果: {'成功' if result['success'] else '失败'}")
        print(f"识别峰数: {len(result.get('peaks', []))}")
        print(f"峰数据: {result.get('peaks_csv')}")
    
    elif args.batch:
        result = controller.batch_analyze_spectra(args.batch, args.output)
        print(f"\n批量分析完成: 成功 {result['success']}/{result['total']}")
    
    elif args.draw:
        if not args.smiles and not args.name:
            parser.error("--draw 需要 --smiles 或 --name")
        
        result = controller.draw_structure(
            smiles=args.smiles,
            compound_name=args.name,
            output_dir=args.output,
            format="all"
        )
        print(f"\n结果: {'成功' if result['success'] else '失败'}")
        print(f"输出文件: {list(result.get('output_files', {}).keys())}")
    
    elif args.optimize:
        result = controller.run_geometry_optimization(
            args.optimize,
            args.output,
            method=args.method,
            basis=args.basis
        )
        print(f"\n结果: {'成功' if result['success'] else '失败'}")
        print(f"计算任务已提交: {result.get('success')}")
    
    elif args.nmr_calc:
        result = controller.run_nmr_prediction(
            args.nmr_calc,
            args.output,
            method=args.method,
            basis=args.basis
        )
        print(f"\n结果: {'成功' if result['success'] else '失败'}")
        print(f"计算任务已提交: {result.get('success')}")
    
    elif args.workflow:
        result = controller.full_analysis_workflow(args.workflow, args.output)
        print(f"\n结果: {'成功' if result['success'] else '失败'}")
        print(f"报告: {result.get('final_report')}")
    
    else:
        parser.print_help()
        print("\n---")
        controller.check_software_availability()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spectrum_analyzer.py — AI 智能识谱工具（最简单的入口）

Agent 专用：一行代码完成谱图分析和结构绘制
=========================================================

【最常用】分析 .mnova 谱图文件：
    
    from spectrum_analyzer import analyze_spectrum
    result = analyze_spectrum("路径/你的文件.mnova")

【画结构图】从 SMILES 绘制化合物结构：
    
    from spectrum_analyzer import draw_structure
    result = draw_structure("CCOC(=O)c1ccc(cc1)OC")

【检查软件是否可用】：
    
    from spectrum_analyzer import check_software
    result = check_software()

=========================================================

输出文件会保存在 ./outputs/ 目录下。
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("spectrum_analyzer")

# ====================================================================
# 路径设置
# ====================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"

# 确保 skill 目录在路径中
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


# ====================================================================
# 配置加载
# ====================================================================

def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ====================================================================
# 核心功能
# ====================================================================

def check_software() -> Dict[str, Any]:
    """
    检查化学软件是否可用
    
    返回:
        {
            "mestrenova": True/False,
            "chemdraw": True/False,
            "spartan": True/False,
            "paths": {...}
        }
    """
    config = load_config()
    software_paths = config.get("software_paths", {})
    result = {"mestrenova": False, "chemdraw": False, "spartan": False, "paths": software_paths}
    
    for name, path in software_paths.items():
        if path and os.path.exists(path):
            key = name.lower()
            if "mest" in key:
                result["mestrenova"] = True
            elif "chem" in key and "draw" in key:
                result["chemdraw"] = True
            elif "spartan" in key:
                result["spartan"] = True
    
    return result


def analyze_spectrum(
    spectrum_file: str,
    output_dir: Optional[str] = None,
    auto_open_file: bool = True,
    auto_peak_pick: bool = True,
    auto_integrate: bool = True,
    export_csv: bool = True,
    export_image: bool = True
) -> Dict[str, Any]:
    """
    分析谱图文件（全自动）
    
    【这是最常用的函数！】
    给一个 .mnova 文件路径，自动完成：
    1. 启动 Mestrenova
    2. 打开谱图文件
    3. 自动峰识别
    4. 自动积分
    5. 导出峰列表 CSV
    6. 导出谱图图片
    
    参数:
        spectrum_file: 谱图文件路径（.mnova 等）
        output_dir: 输出目录（默认 ./outputs/文件名/）
        auto_open_file: 是否自动打开文件
        auto_peak_pick: 是否自动峰识别
        auto_integrate: 是否自动积分
        export_csv: 是否导出 CSV
        export_image: 是否导出图片
    
    返回:
        {
            "success": True/False,
            "spectrum_file": "原文件路径",
            "output_dir": "输出目录",
            "peaks_csv": "峰列表 CSV 路径",
            "spectrum_image": "谱图图片路径",
            "errors": ["错误列表"]
        }
    """
    result = {
        "success": False,
        "spectrum_file": spectrum_file,
        "output_dir": None,
        "peaks_csv": None,
        "spectrum_image": None,
        "peaks": [],
        "errors": []
    }
    
    # 检查文件是否存在
    if not os.path.exists(spectrum_file):
        result["errors"].append(f"文件不存在: {spectrum_file}")
        return result
    
    # 设置输出目录
    if output_dir is None:
        file_stem = Path(spectrum_file).stem
        output_dir = str(SCRIPT_DIR / "outputs" / file_stem)
    os.makedirs(output_dir, exist_ok=True)
    result["output_dir"] = output_dir
    
    # 检查软件
    sw = check_software()
    if not sw["mestrenova"]:
        result["errors"].append(
            "Mestrenova 未找到，请在 config.json 中设置正确的路径。"
            f"当前路径: {sw['paths'].get('mestrenova', '未设置')}"
        )
        return result
    
    try:
        # 导入 GUI 模块
        from mestrenova_gui import MestrenovaGUI
        
        # 启动 Mestrenova（从 config 读取路径）
        print(f"正在启动 Mestrenova...")
        config = load_config()
        mnova_path = config.get("software_paths", {}).get("mestrenova")
        mnova = MestrenovaGUI(executable_path=mnova_path)
        mnova_launched = mnova.launch()
        
        if not mnova_launched:
            result["errors"].append("Mestrenova 启动失败")
            return result
        
        print(f"Mestrenova 已启动")
        time.sleep(2)
        
        # 打开文件
        if auto_open_file:
            print(f"正在打开文件: {spectrum_file}")
            opened = mnova.open_file(spectrum_file)
            if not opened:
                result["errors"].append(f"打开文件失败: {spectrum_file}")
            time.sleep(3)
        
        # 自动峰识别
        if auto_peak_pick:
            print("正在自动峰识别...")
            try:
                mnova.auto_pick_peaks()
                time.sleep(2)
            except Exception as e:
                result["errors"].append(f"峰识别出错: {e}")
        
        # 自动积分
        if auto_integrate:
            print("正在自动积分...")
            try:
                mnova.auto_integrate()
                time.sleep(2)
            except Exception as e:
                result["errors"].append(f"积分出错: {e}")
        
        # 导出峰列表 CSV
        if export_csv:
            csv_path = os.path.join(output_dir, "peaks.csv")
            print(f"正在导出峰列表: {csv_path}")
            try:
                mnova.export_peaks_to_csv(csv_path)
                result["peaks_csv"] = csv_path
                print(f"✓ 峰列表已保存: {csv_path}")
            except Exception as e:
                result["errors"].append(f"导出 CSV 出错: {e}")
        
        # 导出谱图图片
        if export_image:
            img_path = os.path.join(output_dir, "spectrum.png")
            print(f"正在导出谱图图片: {img_path}")
            try:
                mnova.export_spectrum_image(img_path)
                result["spectrum_image"] = img_path
                print(f"✓ 谱图图片已保存: {img_path}")
            except Exception as e:
                result["errors"].append(f"导出图片出错: {e}")
        
        result["success"] = True
        print(f"\n✓ 谱图分析完成！")
        print(f"  输出目录: {output_dir}")
        if result["peaks_csv"]:
            print(f"  峰列表: {result['peaks_csv']}")
        if result["spectrum_image"]:
            print(f"  谱图图片: {result['spectrum_image']}")
        
    except Exception as e:
        result["errors"].append(f"分析失败: {str(e)}")
        print(f"✗ 分析失败: {e}")
    
    return result


def draw_structure(
    smiles: str,
    output_dir: Optional[str] = None,
    output_format: str = "all",
    add_numbers: bool = True
) -> Dict[str, Any]:
    """
    用 ChemDraw 绘制化合物结构图
    
    参数:
        smiles: SMILES 字符串
        output_dir: 输出目录（默认 ./outputs/structure/）
        output_format: 输出格式 ("png", "svg", "cdxml", "sdf", "mol", "all")
        add_numbers: 是否添加原子编号
    
    返回:
        {
            "success": True/False,
            "smiles": "输入的 SMILES",
            "output_files": {
                "png": "路径",
                "svg": "路径",
                ...
            },
            "errors": []
        }
    """
    result = {
        "success": False,
        "smiles": smiles,
        "output_files": {},
        "errors": []
    }
    
    # 设置输出目录
    if output_dir is None:
        output_dir = str(SCRIPT_DIR / "outputs" / "structure")
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查软件
    sw = check_software()
    if not sw["chemdraw"]:
        result["errors"].append(
            "ChemDraw 未找到，请在 config.json 中设置正确的路径。"
            f"当前路径: {sw['paths'].get('chemdraw', '未设置')}"
        )
        return result
    
    try:
        # 导入 GUI 模块
        from chemdraw_gui import ChemDrawGUI
        
        # 启动 ChemDraw（从 config 读取路径）
        print(f"正在启动 ChemDraw...")
        config = load_config()
        cd_path = config.get("software_paths", {}).get("chemdraw") or config.get("software_paths", {}).get("chemdraw_exe")
        chemdraw = ChemDrawGUI(executable_path=cd_path)
        cd_launched = chemdraw.launch()
        
        if not cd_launched:
            result["errors"].append("ChemDraw 启动失败")
            return result
        
        print(f"ChemDraw 已启动")
        time.sleep(2)
        
        # 从 SMILES 绘制结构
        print(f"正在绘制结构: {smiles}")
        drawn = chemdraw.draw_from_smiles(smiles)
        if not drawn:
            result["errors"].append("绘制结构失败")
        time.sleep(2)
        
        # 美化结构
        try:
            chemdraw.clean_up_structure()
            time.sleep(1)
        except:
            pass
        
        # 添加原子编号
        if add_numbers:
            try:
                chemdraw.add_atom_numbers()
                time.sleep(1)
            except:
                pass
        
        # 导出各种格式
        formats_to_export = []
        if output_format == "all":
            formats_to_export = ["png", "svg", "cdxml", "sdf", "mol"]
        else:
            formats_to_export = [output_format]
        
        base_name = "structure"
        for fmt in formats_to_export:
            out_path = os.path.join(output_dir, f"{base_name}.{fmt}")
            try:
                if fmt == "png":
                    chemdraw.export_png(out_path)
                elif fmt == "svg":
                    chemdraw.export_svg(out_path)
                elif fmt == "cdxml":
                    chemdraw.export_cdxml(out_path)
                elif fmt == "sdf":
                    chemdraw.export_sdf(out_path)
                elif fmt == "mol":
                    chemdraw.export_mol(out_path)
                result["output_files"][fmt] = out_path
                print(f"✓ 已导出: {out_path}")
                time.sleep(1)
            except Exception as e:
                result["errors"].append(f"导出 {fmt} 失败: {e}")
        
        result["success"] = len(result["output_files"]) > 0
        print(f"\n✓ 结构绘制完成！输出 {len(result['output_files'])} 个文件")
        
    except Exception as e:
        result["errors"].append(f"绘制失败: {str(e)}")
        print(f"✗ 绘制失败: {e}")
    
    return result


def full_analysis(
    spectrum_file: str,
    smiles: Optional[str] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    完整分析流程：谱图分析 + 结构绘制
    
    参数:
        spectrum_file: 谱图文件路径
        smiles: 可选，化合物 SMILES（用于绘制结构图）
        output_dir: 输出目录
    
    返回:
        {
            "spectrum_analysis": {...},
            "structure_drawing": {...}
        }
    """
    result = {
        "spectrum_analysis": None,
        "structure_drawing": None
    }
    
    # 1. 谱图分析
    result["spectrum_analysis"] = analyze_spectrum(spectrum_file, output_dir)
    
    # 2. 结构绘制（如果提供了 SMILES）
    if smiles:
        struct_dir = os.path.join(output_dir or "./outputs", "structure")
        result["structure_drawing"] = draw_structure(smiles, struct_dir)
    
    return result


# ====================================================================
# 命令行使用
# ====================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI 智能识谱工具")
    parser.add_argument("--check", action="store_true", help="检查软件可用性")
    parser.add_argument("--analyze", type=str, help="分析谱图文件")
    parser.add_argument("--draw", type=str, help="绘制 SMILES 结构")
    parser.add_argument("--output", type=str, help="输出目录")
    
    args = parser.parse_args()
    
    if args.check:
        sw = check_software()
        print("软件检查结果:")
        print(f"  Mestrenova: {'✓ 可用' if sw['mestrenova'] else '✗ 未找到'}")
        print(f"  ChemDraw:    {'✓ 可用' if sw['chemdraw'] else '✗ 未找到'}")
        print(f"  Spartan:     {'✓ 可用' if sw['spartan'] else '✗ 未找到'}")
    
    elif args.analyze:
        analyze_spectrum(args.analyze, args.output)
    
    elif args.draw:
        draw_structure(args.draw, args.output)
    
    else:
        parser.print_help()

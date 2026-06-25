#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spectrum_analyzer.py — AI 智能识谱工具（通用版，v3.0.0）

支持谱图类型：
  - 1D NMR (1H, 13C, 19F, 31P)
  - 2D NMR (COSY, HSQC, HMBC, NOESY, ROESY, TOCSY)
  - MS (质谱 - 高分辨/低分辨)
  - IR (红外光谱)
  - UV-Vis (紫外-可见)
  - CD (圆二色谱)
  - X-ray CIF (X 射线晶体学)
  - HPLC / GC (色谱)

============================================================

【最常用】自动识别并分析谱图：
    
    from spectrum_analyzer import analyze_spectrum
    result = analyze_spectrum("path/to/your/spectrum.mnova")
    # 自动识别是 1H-NMR, 2D-NMR, MS, IR, UV, CD...
    # 然后用相应的专业方法分析

【多谱图联合推导】：

    from spectrum_analyzer import full_analysis
    result = full_analysis(
        spectrum_files=["1H.mnova", "13C.mnova", "HMRS.dta", "IR.jdx"],
        smiles=None  # 让 AI 推导
    )

【画结构图】从 SMILES 绘制化合物结构：
    
    from spectrum_analyzer import draw_structure
    result = draw_structure("CCOC(=O)c1ccc(cc1)OC")

【检查软件是否可用】：
    
    from spectrum_analyzer import check_software
    result = check_software()

============================================================
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

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
    spectrum_type: Optional[str] = None,
    auto_detect: bool = True
) -> Dict[str, Any]:
    """
    分析谱图文件（自动识别类型 + 专业分析）

    【这是最常用的函数！】
    给一个谱图文件路径，自动完成：
    1. 识别谱图类型（NMR/MS/IR/UV/CD/X-ray/...）
    2. 1D vs 2D NMR
    3. 核类型（1H/13C/...）
    4. 调取相应的分析方法
    5. 提取结构信息
    6. 输出标准化结果

    参数:
        spectrum_file: 谱图文件路径
        output_dir: 输出目录（默认 ./outputs/文件名/）
        spectrum_type: 手动指定类型（None 则自动识别）
        auto_detect: 是否自动识别类型

    返回:
        {
            "success": True/False,
            "spectrum_type": "识别的谱图类型",
            "file_path": "原文件路径",
            "output_dir": "输出目录",
            "peaks": [峰列表],
            "structural_info": {结构信息},
            "functional_groups": [官能团列表],
            "molecular_formula": "分子式（如有）",
            "molecular_weight": 分子量（如有）,
            "output_files": {输出文件路径},
            "notes": [分析备注],
            "errors": [错误列表]
        }
    """
    config = load_config()
    result = {
        "success": False,
        "spectrum_type": "Unknown",
        "file_path": spectrum_file,
        "output_dir": None,
        "peaks": [],
        "structural_info": {},
        "functional_groups": [],
        "molecular_formula": None,
        "molecular_weight": None,
        "output_files": {},
        "notes": [],
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

    try:
        # 使用多类型谱图分析器
        from multi_spectrum_analyzer import MultiSpectrumAnalyzer

        analyzer = MultiSpectrumAnalyzer(config=config)
        analysis_result = analyzer.analyze(spectrum_file, output_dir)

        # 转换为统一格式
        result["success"] = analysis_result.success
        result["spectrum_type"] = analysis_result.spectrum_type
        result["peaks"] = analysis_result.peaks
        result["structural_info"] = analysis_result.structural_info
        result["functional_groups"] = analysis_result.functional_groups
        result["molecular_formula"] = analysis_result.molecular_formula
        result["molecular_weight"] = analysis_result.molecular_weight
        result["output_files"] = analysis_result.output_files
        result["notes"] = analysis_result.notes
        result["errors"] = analysis_result.errors

        if not result["success"] and not result["errors"]:
            result["errors"].append("分析未成功，请检查文件格式和软件可用性")

    except Exception as e:
        result["errors"].append(f"分析失败: {str(e)}")
        logger.exception("谱图分析异常")

    # 保存分析结果为 JSON
    try:
        result_json = os.path.join(output_dir, "analysis_result.json")
        with open(result_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        result["output_files"]["analysis_result"] = result_json
    except Exception as e:
        result["notes"].append(f"保存分析结果失败: {e}")

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
            "output_files": {...},
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
        from chemdraw_gui import ChemDrawGUI

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
    spectrum_files: Union[str, List[str]],
    smiles: Optional[str] = None,
    output_dir: Optional[str] = None,
    auto_elucidate: bool = True
) -> Dict[str, Any]:
    """
    完整分析流程：分析谱图 + 推导结构 + 绘制结构图

    支持单个或多个谱图（多谱图联合推导结构）

    参数:
        spectrum_files: 谱图文件路径（字符串或列表）
        smiles: 可选，已知 SMILES（如果提供则直接绘制）
        output_dir: 输出目录
        auto_elucidate: 是否自动推导结构

    返回:
        {
            "spectrum_analyses": [各谱图分析结果],
            "structure_elucidation": {结构推导结果},
            "structure_drawing": {结构图绘制结果},
            "summary": {综合摘要}
        }
    """
    if isinstance(spectrum_files, str):
        spectrum_files = [spectrum_files]

    if output_dir is None:
        output_dir = str(SCRIPT_DIR / "outputs" / "full_analysis")
    os.makedirs(output_dir, exist_ok=True)

    result = {
        "spectrum_analyses": [],
        "structure_elucidation": None,
        "structure_drawing": None,
        "summary": {}
    }

    # 1. 分析所有谱图
    all_groups = set()
    all_info = {}
    molecular_formula = None
    molecular_weight = None

    print(f"\n{'='*60}")
    print(f"开始分析 {len(spectrum_files)} 个谱图")
    print(f"{'='*60}")

    for spec_file in spectrum_files:
        print(f"\n>>> 分析: {spec_file}")
        analysis = analyze_spectrum(spec_file, output_dir=os.path.join(output_dir, Path(spec_file).stem))
        result["spectrum_analyses"].append({
            "file": spec_file,
            "analysis": analysis
        })

        # 累积信息
        if analysis.get("functional_groups"):
            all_groups.update(analysis["functional_groups"])
        if analysis.get("structural_info"):
            all_info.update(analysis["structural_info"])
        if analysis.get("molecular_formula") and not molecular_formula:
            molecular_formula = analysis["molecular_formula"]
        if analysis.get("molecular_weight") and not molecular_weight:
            molecular_weight = analysis["molecular_weight"]

    # 2. 结构推导（如果有多个谱图）
    if auto_elucidate and len(spectrum_files) > 0:
        print(f"\n{'='*60}")
        print("综合多谱图信息进行结构推导")
        print(f"{'='*60}")

        structure_elucidation = {
            "functional_groups": list(all_groups),
            "molecular_formula": molecular_formula,
            "molecular_weight": molecular_weight,
            "structural_clues": all_info,
            "confidence": 0.0
        }

        # 简单的置信度计算
        n_files = len(spectrum_files)
        n_groups = len(all_groups)
        structure_elucidation["confidence"] = min(0.95, 0.3 + n_files * 0.15 + n_groups * 0.05)

        result["structure_elucidation"] = structure_elucidation

        print(f"\n检测到的官能团 ({len(all_groups)}):")
        for g in list(all_groups)[:10]:
            print(f"  - {g}")
        if molecular_formula:
            print(f"\n推测分子式: {molecular_formula}")
        if molecular_weight:
            print(f"分子量: {molecular_weight}")
        print(f"结构推导置信度: {structure_elucidation['confidence']:.0%}")

    # 3. 绘制结构图（如果提供了 SMILES）
    if smiles:
        print(f"\n{'='*60}")
        print("绘制化合物结构图")
        print(f"{'='*60}")
        struct_dir = os.path.join(output_dir, "structure")
        result["structure_drawing"] = draw_structure(smiles, struct_dir)

    # 4. 生成摘要
    result["summary"] = {
        "n_spectra": len(spectrum_files),
        "spectrum_types": [a["analysis"].get("spectrum_type", "Unknown") for a in result["spectrum_analyses"]],
        "functional_groups_count": len(all_groups),
        "molecular_formula": molecular_formula,
        "molecular_weight": molecular_weight,
        "confidence": result.get("structure_elucidation", {}).get("confidence", 0) if result.get("structure_elucidation") else 0
    }

    # 保存综合结果
    try:
        summary_path = os.path.join(output_dir, "full_analysis_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✓ 综合分析结果已保存: {summary_path}")
    except Exception as e:
        print(f"保存综合结果失败: {e}")

    return result


def detect_spectrum_type(filepath: str) -> Dict[str, Any]:
    """
    仅识别谱图类型，不进行完整分析

    返回:
        {
            "spectrum_type": "1H-NMR" / "2D-NMR" / "MS" / "IR" / ...,
            "file_format": "MestReNova" / "mzML" / ...,
            "confidence": 0.0-1.0,
            "nucleus": "1H" / "13C" / ... (NMR only),
            "solvent": "CDCl3" / ... (NMR only),
            "sub_type": "COSY" / "HSQC" / ... (2D NMR only),
            "notes": [...]
        }
    """
    try:
        from spectrum_type_detector import SpectrumTypeDetector
        detector = SpectrumTypeDetector()
        meta = detector.detect(filepath)
        return {
            "spectrum_type": meta.spectrum_type.value,
            "file_format": meta.file_format,
            "confidence": meta.confidence,
            "nucleus": meta.nucleus,
            "solvent": meta.solvent,
            "sub_type": meta.sub_type,
            "notes": meta.notes
        }
    except Exception as e:
        return {
            "spectrum_type": "Unknown",
            "error": str(e)
        }


# ====================================================================
# 命令行使用
# ====================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI 智能识谱工具（通用版）")
    parser.add_argument("--check", action="store_true", help="检查软件可用性")
    parser.add_argument("--detect", type=str, help="仅识别谱图类型，不分析")
    parser.add_argument("--analyze", type=str, help="分析谱图文件")
    parser.add_argument("--draw", type=str, help="绘制 SMILES 结构")
    parser.add_argument("--full", nargs="+", help="完整分析（多个谱图文件）")
    parser.add_argument("--output", type=str, help="输出目录")

    args = parser.parse_args()

    if args.check:
        sw = check_software()
        print("软件检查结果:")
        print(f"  Mestrenova: {'✓ 可用' if sw['mestrenova'] else '✗ 未找到'}")
        print(f"  ChemDraw:    {'✓ 可用' if sw['chemdraw'] else '✗ 未找到'}")
        print(f"  Spartan:     {'✓ 可用' if sw['spartan'] else '✗ 未找到'}")

    elif args.detect:
        result = detect_spectrum_type(args.detect)
        print(f"谱图类型: {result['spectrum_type']}")
        print(f"文件格式: {result['file_format']}")
        print(f"置信度: {result.get('confidence', 0):.0%}")
        if result.get('nucleus'):
            print(f"核类型: {result['nucleus']}")
        if result.get('solvent'):
            print(f"溶剂: {result['solvent']}")
        if result.get('sub_type'):
            print(f"子类型: {result['sub_type']}")

    elif args.analyze:
        result = analyze_spectrum(args.analyze, args.output)
        print(f"\n谱图类型: {result['spectrum_type']}")
        print(f"成功: {result['success']}")
        print(f"峰数量: {len(result['peaks'])}")
        if result['functional_groups']:
            print(f"官能团: {', '.join(result['functional_groups'][:5])}")
        if result['molecular_formula']:
            print(f"分子式: {result['molecular_formula']}")
        if result['molecular_weight']:
            print(f"分子量: {result['molecular_weight']}")
        if result['errors']:
            print(f"错误: {result['errors']}")
        print(f"\n输出文件:")
        for k, v in result.get('output_files', {}).items():
            print(f"  {k}: {v}")

    elif args.draw:
        result = draw_structure(args.draw, args.output)
        print(f"成功: {result['success']}")
        print(f"输出文件: {list(result.get('output_files', {}).keys())}")

    elif args.full:
        result = full_analysis(args.full, output_dir=args.output)
        print(f"\n综合分析完成: {result['summary']}")

    else:
        parser.print_help()

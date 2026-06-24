#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_controller.py — AI 智能识谱工具主控制器

职责：协调整个分析流程，将各模块组合成完整的端到端自动化系统

工作流程：
  1. spectrum_parser         — 识别谱图类型、解析数据
  2. mestrenova_api          — 调用 Mestrenova 处理 NMR 原始数据（如可用）
  3. db_query                — 查询 PubChem/SDBS/ChemSpider 辅助结构确定
  4. structure_elucidator    — 核心结构推导引擎（天然药物化学推理思路）
  5. spartan_api             — 调用 Spartan 进行量化计算、NMR 预测（如可用）
  6. specdis_api             — 手性分析（ECD/ORD 数据）
  7. chemistry_drawing_api   — 综合绘制（RDKit / ChemDraw / Chem3D / OpenBabel / 文本）
  8. 生成综合报告 report.md + 所有结构文件

使用方法（命令行）：
  python main_controller.py --data ./sample_spectra.json --output ./outputs/
  python main_controller.py --mass 250.135 --hnmr 7.25 3.62 2.35 --cnmr 138 129 60 21
  python main_controller.py --smiles "CCOC(=O)c1ccc(cc1)OC" --name "Ethyl 4-methoxybenzoate"
  python main_controller.py --interactive  (交互式输入谱图数据)

在 TRAE 中作为 Skill 使用:
  直接在对话中描述谱图数据，系统将调用 run_analysis()。
"""

import os
import sys
import json
import time
import logging
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main_controller")


# ---------------------------------------------------------------------------
# 模块路径设置 — 确保在任何目录运行都能正确 import
# ---------------------------------------------------------------------------
MODULE_DIR = Path(__file__).parent.resolve()
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

try:
    from spectrum_parser import SpectrumParser, SPECTRUM_TYPES
    from mestrenova_api import MestrenovaAPI
    from spartan_api import SpartanAPI
    from specdis_api import SpecdisAPI
    # 注意：使用新的综合绘制模块 chemistry_drawing_api
    from chemistry_drawing_api import ChemistryDrawingAPI, Molecule
    from db_query import compound_lookup, PubChem
    from structure_elucidator import (
        StructureElucidator, NMRSignal, NMRAnalyzer,
        identify_functional_groups, calc_unsaturation,
    )
    _MODULES_OK = True
except Exception as e:
    _MODULES_OK = False
    logger.error(f"[错误] 模块导入失败: {e}")


# ---------------------------------------------------------------------------
# 1. 配置加载
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> Dict:
    """加载配置文件；若不存在则使用默认配置。"""
    default_config = {
        "software_paths": {
            "mestrenova": "",
            "spartan": "",
            "specdis": "",
            "chem3d": "",
            "chemdraw": "",
            "chemdraw_exe": "",
        },
        "api_keys": {
            "pubchem": "",
            "chemspider": "",
        },
        "preferred_drawing_backend": "RDKIT",
        "output_dir": "./outputs",
        "log_level": "INFO",
        "use_online_database": True,
        "max_candidates": 20,
        "hmass_tolerance_ppm": 10.0,
        "tutorial_mode": True,
    }

    if config_path and Path(config_path).exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            for k, v in user_cfg.items():
                if isinstance(v, dict) and isinstance(default_config.get(k), dict):
                    default_config[k].update(v)
                else:
                    default_config[k] = v
            logger.info(f"[信息] 已加载配置: {config_path}")
        except Exception as e:
            logger.warning(f"[警告] 配置文件读取失败，使用默认配置: {e}")
    else:
        logger.info("[信息] 使用默认配置")

    return default_config


# ---------------------------------------------------------------------------
# 2. 核心分析流程 — run_analysis()
# ---------------------------------------------------------------------------

def run_analysis(input_path: Optional[str] = None,
                  spectral_data: Optional[Dict] = None,
                  smiles: Optional[str] = None,
                  name: str = "Compound",
                  config: Optional[Dict] = None,
                  output_dir: Optional[str] = None) -> Dict:
    """
    AI 智能识谱工具 — 完整自动化流程（端到端）。

    参数:
      input_path:     谱图数据文件/目录路径（如 .mnova / .csv / .txt / .jdx 等）
      spectral_data:  直接传入的谱图数据字典（推荐格式见 sample_spectra.json）
      smiles:         已知化合物的 SMILES（可选，加快结构确定）
      name:           化合物名称（默认 "Compound"）
      config:         配置字典（软件路径、API Key 等）
      output_dir:     输出目录（默认 ./outputs）

    返回:
      包含完整分析结果的 Dict，同时在 output_dir 写入以下文件：
        • report.md                 — 人类可读完整推导报告
        • structure_2D.png          — 2D 结构式（需 RDKit 或 ChemDraw）
        • structure_2D.svg          — 2D 结构式矢量图
        • structure_2D_labeled.png  — 带原子编号的 2D 图（用于 NMR 归属）
        • structure.sdf             — 3D 结构文件（SDF 格式，所有化学软件兼容）
        • structure.mol             — MDL MOL V2000 格式
        • structure.cdxml           — ChemDraw XML 文件（双击用 ChemDraw 打开）
        • structure.cml             — Chemical Markup Language（CML，XML 标准）
        • structure.pdb             — PDB 格式（兼容生物信息学/分子对接软件）
        • structure.smiles          — SMILES 字符串
        • nmr_assignments.csv       — NMR 信号归属表
        • confidence_scores.json    — 置信度评分 + 改进建议
        • spectrum_raw.json         — 原始解析数据（便于二次分析）
    """
    cfg = config or load_config()
    output_dir = Path(output_dir or cfg.get("output_dir", "./outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()

    # ===============================================================
    # 打印标题
    # ===============================================================
    logger.info("=" * 70)
    logger.info("  AI 智能识谱工具 — 自动化合物结构推导")
    logger.info(f"  系统: {platform.system()} {platform.release()} | Python {platform.python_version()}")
    logger.info(f"  开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if _MODULES_OK:
        logger.info("  核心模块: 已加载 ✓")
    else:
        logger.warning("  核心模块: 存在加载失败（将使用最小功能集）")
    logger.info("=" * 70)

    # ===============================================================
    # 结果总容器
    # ===============================================================
    result = {
        "inputs": {"input_path": str(input_path) if input_path else None,
                   "has_spectral_data": bool(spectral_data),
                   "smiles": smiles,
                   "compound_name": name},
        "parsing": {},
        "nmr_processing": {},
        "database_query": {},
        "structure_elucidation": {},
        "quantum_calculation": {},
        "chiral_analysis": {},
        "structure_drawing": {},
        "final_report": {},
        "output_files": [],
        "warnings": [],
    }

    # ===============================================================
    # Step 1: 谱图数据解析（spectrum_parser）
    # ===============================================================
    logger.info("\n[Step 1/7] 谱图数据识别与解析")
    logger.info("-" * 70)

    try:
        if input_path and Path(input_path).exists() and _MODULES_OK:
            sp = SpectrumParser(cfg)
            parsed = sp.parse(input_path)
            result["parsing"] = {"found_types": parsed.get("detected_types", []),
                                 "files": [str(p) for p in parsed.get("files", [])]}
            logger.info(f"  ✓ 检测到谱图类型: {', '.join(result['parsing']['found_types']) or 'N/A'}")
        else:
            logger.info("  · 无文件输入，使用提供的谱图数据或信号列表")
    except Exception as e:
        logger.error(f"  ✗ Step 1 失败: {e}")
        result["warnings"].append(f"Step 1 解析错误: {e}")

    # ===============================================================
    # Step 2: NMR 信号整理
    # ===============================================================
    logger.info("\n[Step 2/7] NMR 谱图信号整理")
    logger.info("-" * 70)

    nmr_signals = {"h_nmr": [], "c_nmr": []}
    try:
        if spectral_data:
            nmr_signals["h_nmr"] = spectral_data.get("h_nmr", [])
            nmr_signals["c_nmr"] = spectral_data.get("c_nmr", [])
            logger.info(f"  ✓ 从数据读取: ¹H NMR {len(nmr_signals['h_nmr'])} 个信号")
            logger.info(f"  ✓ 从数据读取: ¹³C NMR {len(nmr_signals['c_nmr'])} 个信号")

        # 如同时有 .mnova 文件，则调用 Mestrenova 进一步处理
        if input_path and Path(input_path).exists() and _MODULES_OK:
            p = Path(input_path)
            if p.suffix.lower() == ".mnova":
                try:
                    mn = MestrenovaAPI(cfg)
                    mres = mn.process(str(p), output_dir=str(output_dir))
                    for s in mres.get("signals", []):
                        if isinstance(s, dict):
                            if s.get("shift_ppm", 0) > 30:
                                nmr_signals["c_nmr"].append(s)
                            else:
                                nmr_signals["h_nmr"].append(s)
                    logger.info(f"  ✓ Mestrenova 处理: {len(mres.get('signals', []))} 条信号")
                except Exception as e:
                    logger.warning(f"  · Mestrenova 不可用或失败: {e}")
        result["nmr_processing"] = nmr_signals
    except Exception as e:
        logger.error(f"  ✗ Step 2 失败: {e}")
        result["warnings"].append(f"Step 2 NMR 处理错误: {e}")

    # ===============================================================
    # Step 3: 在线数据库查询（PubChem/SDBS/ChemSpider）
    # ===============================================================
    logger.info("\n[Step 3/7] 在线化学数据库查询（PubChem / SDBS）")
    logger.info("-" * 70)

    db_result = {}
    try:
        if cfg.get("use_online_database", True) and _MODULES_OK:
            mass = None
            if spectral_data and spectral_data.get("ms"):
                mass = spectral_data["ms"].get("exact_mass")
            formula = spectral_data.get("formula") if spectral_data else None
            db_result = compound_lookup(
                exact_mass=mass, formula=formula, smiles=smiles,
                chemspider_key=cfg.get("api_keys", {}).get("chemspider", "")
            )
            logger.info(f"  ✓ 分子式候选: {len(db_result.get('formula_candidates', []))} 个")
            logger.info(f"  ✓ 数据库匹配: {len(db_result.get('pubchem_hits', []))} 条")
        else:
            logger.info("  · 已禁用在线数据库查询或模块不可用，跳过")
    except Exception as e:
        logger.error(f"  ✗ Step 3 失败: {e}")
        result["warnings"].append(f"Step 3 数据库查询错误: {e}")

    result["database_query"] = db_result

    # ===============================================================
    # Step 4: 核心结构推导（模拟天然药物化学家的推理过程）
    # ===============================================================
    logger.info("\n[Step 4/7] 核心结构推导（天然药物化学推理思路）")
    logger.info("-" * 70)

    elucidation = {}
    best_formula = None
    best_smiles = None
    try:
        if _MODULES_OK:
            engine_data = {
                "h_nmr": nmr_signals.get("h_nmr", []),
                "c_nmr": nmr_signals.get("c_nmr", []),
                "ms": spectral_data.get("ms", {}) if spectral_data else {},
                "ir": spectral_data.get("ir", []) if spectral_data else [],
                "uv": spectral_data.get("uv", []) if spectral_data else [],
            }
            engine = StructureElucidator(engine_data, cfg)
            elucidation = engine.elucidate(output_dir=str(output_dir))
            summary = elucidation.get("summary", {})
            best_formula = summary.get("best_formula")
            logger.info(f"  ✓ 最佳分子式: {best_formula}")
            logger.info(f"  ✓ 不饱和度 Ω: {summary.get('unsaturation_omega', 'N/A')}")
            logger.info(f"  ✓ 官能团: {len(elucidation.get('functional_groups', []))} 个")
            logger.info(f"  ✓ 结构候选: {len(elucidation.get('database_candidates', []))} 个")
            logger.info(f"  ✓ 置信度: {summary.get('overall_confidence', 0)}%")
        else:
            logger.warning("  ✗ 核心引擎不可用，跳过结构推理")
    except Exception as e:
        logger.error(f"  ✗ Step 4 失败: {e}")
        result["warnings"].append(f"Step 4 结构推导错误: {e}")

    result["structure_elucidation"] = elucidation

    # ===============================================================
    # Step 5: 量化计算（Spartan，如可用）
    # ===============================================================
    logger.info("\n[Step 5/7] 量化计算与 NMR 位移预测（Spartan）")
    logger.info("-" * 70)

    qm_result = {}
    try:
        if _MODULES_OK:
            sp_api = SpartanAPI(cfg)
            # 如果有数据库候选，用第一个的 SMILES 初始化
            candidate_smiles = None
            for hit in elucidation.get("database_candidates", []):
                if hit.get("smiles"):
                    candidate_smiles = hit["smiles"]
                    best_smiles = best_smiles or candidate_smiles
                    break

            molecule_info = {"name": name, "smiles": smiles or candidate_smiles or ""}
            if molecule_info["smiles"]:
                qm_result = sp_api.optimize_geometry(molecule_info, output_dir=str(output_dir))
                logger.info(f"  ✓ Spartan 状态: {qm_result.get('status', 'UNKNOWN')}")
            else:
                logger.info("  · 无 SMILES 可用，跳过量化计算（可在前端手动进行）")
        else:
            logger.info("  · 模块不可用，跳过 Spartan 计算")
    except Exception as e:
        logger.warning(f"  ✗ Step 5 失败: {e}")
        result["warnings"].append(f"Step 5 量化计算错误: {e}")

    result["quantum_calculation"] = qm_result

    # ===============================================================
    # Step 6: 手性分析（Specdis / ECD）
    # ===============================================================
    logger.info("\n[Step 6/7] 手性分析（ECD/ORD）")
    logger.info("-" * 70)

    chiral_result = {}
    try:
        if spectral_data and spectral_data.get("ecd") and _MODULES_OK:
            sd_api = SpecdisAPI(cfg)
            chiral_result = sd_api.compare_spectra(
                experimental_spectrum=spectral_data["ecd"],
                calculated_spectra=[],
                spectrum_type="ECD",
                output_dir=str(output_dir),
            )
            logger.info(f"  ✓ 手性分析完成，构型: {chiral_result.get('configuration', 'N/A')}")
        else:
            logger.info("  · 未提供 ECD/ORD 数据，跳过手性分析")
    except Exception as e:
        logger.warning(f"  ✗ Step 6 失败: {e}")
        result["warnings"].append(f"Step 6 手性分析错误: {e}")

    result["chiral_analysis"] = chiral_result

    # ===============================================================
    # Step 7: 结构绘制（多后端系统 — RDKit / ChemDraw / Chem3D / ...）
    # ===============================================================
    logger.info("\n[Step 7/7] 结构绘制与文件导出（RDKit / ChemDraw / Chem3D）")
    logger.info("-" * 70)

    drawing = {}
    try:
        if _MODULES_OK:
            # 确定最终 SMILES
            final_smiles = smiles or best_smiles
            # 从数据库候选中找 SMILES 兜底
            if not final_smiles:
                for hit in elucidation.get("database_candidates", []):
                    if hit.get("smiles"):
                        final_smiles = hit["smiles"]
                        break

            mol = Molecule(name=name)
            mol.smiles = final_smiles or ""
            if best_formula:
                mol.from_formula(best_formula)
            elif spectral_data and spectral_data.get("formula"):
                mol.from_formula(spectral_data["formula"])

            # 综合绘制引擎
            drawing_api = ChemistryDrawingAPI(cfg)

            # 用户指定优先后端
            preferred = cfg.get("preferred_drawing_backend", "RDKIT")
            if preferred and preferred in drawing_api.available_backends:
                drawing_api.set_preferred_backend(preferred)

            logger.info(f"  · 可用绘制后端: {', '.join(drawing_api.available_backends)}")
            logger.info(f"  · 当前后端: {drawing_api.mode}")

            # 批量导出
            files = drawing_api.export_all_formats(mol, str(output_dir))
            drawing["exported_files"] = files
            drawing["backend_used"] = drawing_api.mode
            drawing["available_backends"] = drawing_api.available_backends

            # 特别标注：CDXML 文件可直接双击用 ChemDraw 打开
            if "cdxml" in files:
                logger.info(f"  ✓ CDXML: {files['cdxml']} (可用 ChemDraw 双击打开)")
            if "png" in files:
                logger.info(f"  ✓ PNG 2D 结构: {files['png']}")
            if "sdf" in files:
                logger.info(f"  ✓ SDF 3D 结构: {files['sdf']} (兼容所有化学软件)")

            for fpath in files.values():
                result["output_files"].append(str(fpath))
        else:
            logger.warning("  ✗ 核心模块不可用，跳过绘制（仅生成文本报告）")
    except Exception as e:
        logger.error(f"  ✗ Step 7 失败: {e}")
        result["warnings"].append(f"Step 7 结构绘制错误: {e}")

    result["structure_drawing"] = drawing

    # ===============================================================
    # 最终: 生成综合报告（report.md）
    # ===============================================================
    logger.info("\n[Final] 生成综合分析报告 (report.md)")
    logger.info("-" * 70)

    # NMR 归属表（CSV）
    csv_lines = ["类型,化学位移(ppm),积分,多重性,J(Hz),归属建议"]
    for s in nmr_signals.get("h_nmr", []):
        if isinstance(s, dict):
            csv_lines.append(
                f"1H,{s.get('shift_ppm', 0):.3f},{s.get('intensity', 1):.1f},"
                f"{s.get('multiplicity', 's')},{s.get('j_hz', 0):.1f},"
                f"{_suggest(s.get('shift_ppm', 0), 'H')}"
            )
    for s in nmr_signals.get("c_nmr", []):
        if isinstance(s, dict):
            csv_lines.append(
                f"13C,{s.get('shift_ppm', 0):.2f},{s.get('intensity', 1):.1f},"
                f"{s.get('multiplicity', 's')},{s.get('j_hz', 0):.1f},"
                f"{_suggest(s.get('shift_ppm', 0), 'C')}"
            )
    csv_path = output_dir / "nmr_assignments.csv"
    csv_path.write_text("\n".join(csv_lines), encoding="utf-8")
    result["output_files"].append(str(csv_path))

    # 置信度 JSON
    confidence = {
        "overall": elucidation.get("summary", {}).get("overall_confidence", 0),
        "components": {
            "data_completeness": _score_data(nmr_signals, spectral_data),
            "formula_confidence": min(100, 40 + (5 if spectral_data and spectral_data.get("ms") else 0)
                                      + len(elucidation.get("database_candidates", [])) * 8),
            "functional_groups_confidence": min(100, len(elucidation.get("functional_groups", [])) * 20),
            "database_support": min(100, len(db_result.get("pubchem_hits", [])) * 10),
            "chiral_support": chiral_result.get("confidence", 0),
        },
        "recommendations": _generate_recommendations(result),
    }
    conf_path = output_dir / "confidence_scores.json"
    conf_path.write_text(json.dumps(confidence, ensure_ascii=False, indent=2), encoding="utf-8")
    result["output_files"].append(str(conf_path))

    # 原始数据 JSON
    raw_path = output_dir / "spectrum_raw.json"
    raw_obj = {
        "nmr_signals": nmr_signals,
        "spectral_data": spectral_data or {},
        "input_path": str(input_path) if input_path else None,
        "parsed_files": [str(x) for x in result["parsing"].get("files", [])],
    }
    raw_path.write_text(json.dumps(raw_obj, ensure_ascii=False, indent=2, default=str),
                         encoding="utf-8")
    result["output_files"].append(str(raw_path))

    # report.md（主报告）
    report_path = _generate_report_md(
        result=result, output_dir=output_dir,
        nmr_signals=nmr_signals, elucidation=elucidation,
        db_result=db_result, chiral_result=chiral_result,
        drawing=drawing, confidence=confidence,
        duration=time.time() - start_time,
        compound_name=name, formula=best_formula,
        mass=spectral_data.get("ms", {}).get("exact_mass") if spectral_data else None,
    )
    result["output_files"].append(report_path)

    # ===============================================================
    # 最终摘要
    # ===============================================================
    duration = time.time() - start_time
    result["final_report"] = {
        "duration_seconds": round(duration, 2),
        "output_directory": str(output_dir),
        "n_output_files": len(result["output_files"]),
        "confidence": confidence,
        "compound_name": name,
        "formula": best_formula,
        "smiles": smiles or best_smiles,
        "drawing_backend": drawing.get("backend_used", "TEXT"),
        "recommendations": _generate_recommendations(result),
    }

    logger.info("\n" + "=" * 70)
    logger.info(f"  分析完成！耗时 {duration:.1f} 秒，生成 {len(result['output_files'])} 个文件")
    logger.info(f"  输出目录: {output_dir}")
    logger.info(f"  核心文件: report.md, structure_2D.png, structure.sdf, structure.cdxml")
    logger.info("=" * 70)

    return result


# ---------------------------------------------------------------------------
# 辅助函数: NMR 化学位移 → 结构片段建议
# ---------------------------------------------------------------------------

def _suggest(shift: float, nucleus: str) -> str:
    """根据化学位移给出初步结构片段建议"""
    if nucleus == "H":
        if 6.5 <= shift <= 8.5: return "芳香氢 Ar-H"
        if 4.5 <= shift < 6.5: return "烯氢 =CH-"
        if 3.3 <= shift < 4.5: return "连氧氢 -O-CH₂-"
        if 2.0 <= shift < 2.8: return "芳甲基 / 乙酰基"
        if 1.0 <= shift < 2.0: return "脂肪烷基 CH/CH₂"
        if 0.5 <= shift < 1.0: return "烷基 CH₃"
        if shift >= 9.5: return "醛/羧基活泼氢"
    else:
        if 190 <= shift <= 220: return "酮/醛羰基 C=O"
        if 160 <= shift < 190: return "酯/羧酸/酰胺羰基"
        if 120 <= shift < 160: return "芳香 sp² C"
        if 100 <= shift < 120: return "烯碳 / 异头碳"
        if 50 <= shift < 100: return "连氧 sp³ C"
        if 0 <= shift < 50: return "普通脂肪 sp³ C"
    return "—"


def _score_data(nmr, spectral):
    score = 0
    if nmr.get("h_nmr"): score += 30
    if nmr.get("c_nmr"): score += 30
    if spectral and spectral.get("ms"): score += 20
    if spectral and spectral.get("ir"): score += 10
    if spectral and spectral.get("uv"): score += 10
    return min(score, 100)


def _generate_recommendations(result):
    recs = []
    elu = result.get("structure_elucidation", {})
    if not result.get("nmr_processing", {}).get("c_nmr"):
        recs.append("建议补充 ¹³C-NMR 数据，提高碳骨架推断可靠性")
    if not result.get("nmr_processing", {}).get("h_nmr"):
        recs.append("建议补充 ¹H-NMR 数据")
    if not elu.get("summary", {}).get("best_formula"):
        recs.append("建议提供高分辨质谱 (HRMS) 精确确定分子式")
    if not result.get("chiral_analysis"):
        recs.append("如需确定绝对构型，请提供 ECD 或旋光度数据")
    if elu.get("summary", {}).get("overall_confidence", 0) < 60:
        recs.append("当前整体置信度较低，建议补充 2D-NMR (COSY/HMBC/HSQC) 或单晶衍射数据")
    if not recs:
        recs.append("当前数据较为完整，可在人工复核后将结果作为初步结论使用")
    return recs


# ---------------------------------------------------------------------------
# 辅助函数: 生成 Markdown 报告
# ---------------------------------------------------------------------------

def _generate_report_md(result, output_dir, nmr_signals, elucidation, db_result,
                         chiral_result, drawing, confidence, duration,
                         compound_name, formula, mass):
    lines = []
    lines.append("# AI 智能识谱工具 — 综合分析报告")
    lines.append("")
    lines.append(f"**化合物名称**: {compound_name}")
    lines.append(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**分析耗时**: {duration:.1f} 秒")
    lines.append(f"**整体置信度**: ⭐ {confidence.get('overall', 0)}%")
    lines.append("")
    lines.append("## 一、核心结论")
    lines.append("")
    lines.append(f"- **推断分子式**: **{formula or '(未确定)'}**")
    lines.append(f"- **精确质量**: {mass or 'N/A'} Da")
    omega = elucidation.get("summary", {}).get("unsaturation_omega", "N/A")
    lines.append(f"- **不饱和度 Ω**: {omega}")
    lines.append(f"- **绘制后端**: {drawing.get('backend_used', 'TEXT')}")
    lines.append(f"- **可用绘制后端**: {', '.join(drawing.get('available_backends', ['TEXT']))}")
    lines.append("")
    lines.append("## 二、谱图数据摘要")
    lines.append("")
    lines.append(f"- ¹H-NMR 信号数: **{len(nmr_signals.get('h_nmr', []))}**")
    lines.append(f"- ¹³C-NMR 信号数: **{len(nmr_signals.get('c_nmr', []))}**")
    lines.append(f"- 质谱精确质量: {mass or 'N/A'}")
    lines.append("")
    lines.append("### 2.1 ¹H-NMR 信号表")
    lines.append("")
    if nmr_signals.get("h_nmr"):
        lines.append("| δ (ppm) | 积分 | 多重性 | J (Hz) | 归属建议 |")
        lines.append("|---|---|---|---|---|")
        for s in nmr_signals["h_nmr"]:
            if isinstance(s, dict):
                lines.append(f"| {s.get('shift_ppm', 0):.3f} | {s.get('intensity', 1):.1f} | "
                             f"{s.get('multiplicity', 's')} | {s.get('j_hz', 0):.1f} | "
                             f"{_suggest(s.get('shift_ppm', 0), 'H')} |")
    else:
        lines.append("_(未提供 ¹H-NMR 数据)_")
    lines.append("")
    lines.append("### 2.2 ¹³C-NMR 信号表")
    lines.append("")
    if nmr_signals.get("c_nmr"):
        lines.append("| δ (ppm) | 积分 | 多重性 | 归属建议 |")
        lines.append("|---|---|---|---|")
        for s in nmr_signals["c_nmr"]:
            if isinstance(s, dict):
                lines.append(f"| {s.get('shift_ppm', 0):.2f} | {s.get('intensity', 1):.1f} | "
                             f"{s.get('multiplicity', 's')} | "
                             f"{_suggest(s.get('shift_ppm', 0), 'C')} |")
    else:
        lines.append("_(未提供 ¹³C-NMR 数据)_")
    lines.append("")

    lines.append("## 三、官能团识别")
    lines.append("")
    fgs = elucidation.get("functional_groups", [])
    if fgs:
        lines.append("| 官能团 | 证据 | 置信度 (%) |")
        lines.append("|---|---|---|")
        for fg in fgs:
            lines.append(f"| {fg.get('functional_group', '')} | "
                         f"{fg.get('evidence', '')} | {fg.get('confidence', 0)} |")
    else:
        lines.append("_未识别到明确的官能团（谱图数据不足或信号复杂）_")
    lines.append("")

    lines.append("## 四、数据库候选化合物（PubChem）")
    lines.append("")
    candidates = elucidation.get("database_candidates", [])
    if candidates:
        lines.append("| # | 名称 | 分子量 | SMILES |")
        lines.append("|---|---|---|---|")
        for i, c in enumerate(candidates[:15], 1):
            lines.append(f"| {i} | {c.get('iupac', c.get('name', ''))[:60]} | "
                         f"{c.get('molecular_weight', '')} | {c.get('smiles', '')[:40]} |")
    else:
        lines.append("_未找到数据库匹配（可能是新化合物或分子式未确定）_")
    lines.append("")

    lines.append("## 五、结构文件索引")
    lines.append("")
    lines.append("以下文件已在输出目录中生成，可直接用对应软件打开：")
    lines.append("")
    for key, path in drawing.get("exported_files", {}).items():
        desc = {
            "png": "PNG 图像（Word/PPT 直接粘贴）",
            "svg": "SVG 矢量图（论文排版）",
            "labeled_png": "带原子编号的 PNG（用于 NMR 归属）",
            "sdf": "SDF 格式（所有化学软件兼容，含 3D 坐标）",
            "mol": "MDL MOL V2000 格式",
            "cml": "Chemical Markup Language (XML 标准)",
            "cdxml": "ChemDraw XML（双击用 ChemDraw 打开）",
            "pdb": "PDB 格式（生物信息学/分子对接）",
            "smiles": "SMILES 字符串（文本格式）",
        }.get(key, "")
        lines.append(f"- `{Path(path).name}` — {desc}")
    lines.append("")
    lines.append("**说明**:")
    lines.append("- 若 `structure_2D.png` 仅生成了文本报告，请安装 `pip install rdkit-pypi` 或在 config.json 配置 ChemDraw 路径以获得图形化结构。")
    lines.append("- `structure.cdxml` 可直接双击用 ChemDraw 打开，修改后可用于学术论文/专利。")
    lines.append("- `structure.sdf` 可导入到 Chem3D, Spartan, Maestro, PyMOL, VMD 等所有主流化学/生物信息学软件。")
    lines.append("")

    lines.append("## 六、置信度评估")
    lines.append("")
    for comp, val in confidence.get("components", {}).items():
        lines.append(f"- **{comp}**: {val}%")
    lines.append("")

    lines.append("## 七、改进建议")
    lines.append("")
    for r in confidence.get("recommendations", []):
        lines.append(f"- {r}")
    lines.append("")

    if result.get("warnings"):
        lines.append("## 八、处理过程中的警告")
        lines.append("")
        for w in result["warnings"]:
            lines.append(f"- ⚠ {w}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_本报告由 **AI 智能识谱工具** 自动生成，模拟天然药物化学研究者的推理过程。")
    lines.append("最终结论须由具备资质的化学专业人员人工复核。_")

    report_path = str(output_dir / "report.md")
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"  ✓ 已生成综合报告: {report_path}")
    return report_path


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="AI 智能识谱工具 — 从谱图数据推导化合物结构（支持 RDKit/ChemDraw/Chem3D/OpenBabel 绘制）"
    )
    parser.add_argument("--input", "-i", help="谱图文件或目录路径")
    parser.add_argument("--data", "-d", help="JSON 格式谱图数据（如 sample_spectra.json）")
    parser.add_argument("--smiles", "-s", help="已知 SMILES（如已确定结构，仅需绘制）")
    parser.add_argument("--name", "-n", default="Compound", help="化合物名称")
    parser.add_argument("--formula", "-f", help="分子式")
    parser.add_argument("--hnmr", nargs="+", type=float, help="¹H-NMR 化学位移（ppm），如 7.25 3.62 2.35")
    parser.add_argument("--cnmr", nargs="+", type=float, help="¹³C-NMR 化学位移（ppm）")
    parser.add_argument("--mass", type=float, help="HRMS 精确质量 (Da)")
    parser.add_argument("--config", "-c", help="配置文件 (JSON)")
    parser.add_argument("--output", "-o", default="./outputs", help="输出目录")
    parser.add_argument("--backend", "-b", choices=["RDKIT", "CHEMDRAW", "CHEM3D", "OPENBABEL", "TEXT"],
                       help="指定绘制后端（默认自动按优先级选择）")
    parser.add_argument("--interactive", action="store_true", help="交互式输入谱图数据")
    args = parser.parse_args()

    # 加载配置
    cfg = load_config(args.config)
    if args.backend:
        cfg["preferred_drawing_backend"] = args.backend

    # 组装谱图数据对象
    spectral_data = None
    if args.data and Path(args.data).exists():
        with open(args.data, "r", encoding="utf-8") as f:
            spectral_data = json.load(f)
        logger.info(f"[信息] 已载入 JSON 数据文件: {args.data}")
    else:
        spectral_data = {}
        if args.hnmr:
            spectral_data["h_nmr"] = [
                {"shift_ppm": s, "intensity": 1.0, "multiplicity": "s", "j_hz": 0.0}
                for s in args.hnmr
            ]
        if args.cnmr:
            spectral_data["c_nmr"] = [
                {"shift_ppm": s, "intensity": 1.0, "multiplicity": "s", "j_hz": 0.0}
                for s in args.cnmr
            ]
        if args.mass:
            spectral_data["ms"] = {"exact_mass": args.mass}
        if args.formula:
            spectral_data["formula"] = args.formula

    # 交互式输入
    if args.interactive and not spectral_data:
        spectral_data = {}
        print("\n=== 交互式谱图输入 ===")
        print("输入每行一个化学位移，空行结束。\n")
        for label, key in (("¹H-NMR (ppm)", "h_nmr"), ("¹³C-NMR (ppm)", "c_nmr")):
            print(f"{label}:")
            shifts = []
            while True:
                line = input("  δ = ").strip()
                if not line:
                    break
                try:
                    shifts.append(float(line))
                except ValueError:
                    print("  (请输入数字)")
            if shifts:
                spectral_data[key] = [
                    {"shift_ppm": s, "intensity": 1.0, "multiplicity": "s", "j_hz": 0.0}
                    for s in shifts
                ]
        line = input("HRMS 精确质量 (Da，留空跳过): ").strip()
        if line:
            try:
                spectral_data["ms"] = {"exact_mass": float(line)}
            except ValueError:
                pass

    if not args.input and not spectral_data and not args.smiles:
        parser.print_help()
        print("\n示例:")
        print(f'  python {Path(__file__).name} --data sample_spectra.json')
        print(f'  python {Path(__file__).name} --hnmr 7.25 3.62 2.35 --mass 180.0786')
        print(f'  python {Path(__file__).name} --smiles "CCOC(=O)c1ccc(cc1)OC" -n "Ethyl 4-methoxybenzoate"')
        print(f'  python {Path(__file__).name} --interactive')
        sys.exit(1)

    # 运行主分析流程
    final = run_analysis(
        input_path=args.input,
        spectral_data=spectral_data,
        smiles=args.smiles,
        name=args.name,
        config=cfg,
        output_dir=args.output,
    )

    print("\n" + "=" * 70)
    print("  完成！核心文件：")
    print(f"    • 综合报告:   {Path(args.output) / 'report.md'}")
    print(f"    • 2D 结构:    {Path(args.output) / 'structure_2D.png'}")
    print(f"    • ChemDraw:   {Path(args.output) / 'structure.cdxml'}")
    print(f"    • 3D 结构:    {Path(args.output) / 'structure.sdf'}")
    print(f"    • NMR 归属:   {Path(args.output) / 'nmr_assignments.csv'}")
    print(f"  整体置信度: {final['final_report'].get('confidence', {}).get('overall', 0)}%")
    print("=" * 70)


if __name__ == "__main__":
    main()

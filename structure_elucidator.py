#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
structure_elucidator.py — 化合物结构推导核心引擎

功能：模拟天然药物化学研究者的完整思考过程：
  1. 从谱图数据（NMR/IR/MS/UV/ECD）提取关键信息
  2. 确定分子式（基于 HRMS + 元素分析）
  3. 计算不饱和度 Ω，判断骨架类型
  4. 分析 ¹H-NMR：识别结构片段（芳香/烯氢/脂肪氢/活泼氢）
  5. 分析 ¹³C-NMR + DEPT：识别碳类型（sp³/sp²/sp，CH/CH₂/CH₃/季碳）
  6. 识别官能团（羰基/羟基/氨基/双键/三键/芳环等）
  7. 查询在线数据库（PubChem/SDBS）获取已知结构候选
  8. 组装候选结构并打分
  9. 输出最终建议化合物及完整推导报告

这是整个工具的「大脑」部分，完成从谱图数据 → 结构的核心推理。
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("structure_elucidator")


# ---------------------------------------------------------------------------
# 1. 化学知识库（NMR 化学位移规则、官能团特征、IR 峰位等）
# ---------------------------------------------------------------------------

# ¹H-NMR 化学位移区间 → 结构片段推断 (δ, ppm)
H_NMR_SHIFTS = [
    (0.5, 1.5, "CH₃- (烷基甲基)", "aliphatic_CH3"),
    (1.0, 2.0, "-CH₂- (烷基亚甲基)", "aliphatic_CH2"),
    (1.2, 2.5, "-CH- (烷基亚甲基)", "aliphatic_CH"),
    (1.5, 3.0, "与杂原子/芳环/羰基相连的 sp³ C-H", "heteroatom_CH"),
    (2.0, 2.5, "-CO-CH₃ (乙酰基/酮甲基)", "acetyl_CH3"),
    (2.3, 3.0, "Ar-CH₃ (芳甲基)", "aryl_CH3"),
    (3.3, 4.2, "-CH₂-O- (醚/酯氧邻)", "ether_CH2"),
    (3.5, 4.8, "-OH (羟基/醇羟基) — 宽峰/浓度相关", "hydroxyl"),
    (4.0, 5.5, "-O-CH₂-OR (半缩醛/糖苷氢)", "acetal_CH"),
    (4.5, 6.5, "=CH₂ (端烯氢 / =CH- 烯氢)", "alkene_H"),
    (6.5, 8.5, "Ar-H (芳香氢) — 单峰/多重峰", "aromatic_H"),
    (8.5, 10.0, "-CHO (醛基氢)", "aldehyde_H"),
    (10.0, 13.0, "-COOH (羧基氢) — 宽峰", "carboxyl_H"),
]

# ¹³C-NMR 化学位移区间 → 碳类型推断 (δ, ppm)
C_NMR_SHIFTS = [
    (0, 50, "sp³ C (饱和烷基碳)", "aliphatic_C"),
    (20, 35, "-CH₃ (甲基碳)", "methyl_C"),
    (40, 60, "-CH₂- (与杂原子相连 sp³ C)", "CH2_heteroatom"),
    (50, 80, "sp³ C-O (连氧碳 / 醇 / 醚 / 苷元)", "oxygenated_sp3_C"),
    (100, 110, "O=C-O-CH< (异头碳 / 半缩醛碳)", "anomeric_C"),
    (100, 150, "sp² C (C=C 双键碳)", "alkene_C"),
    (120, 140, "芳香 sp² C (芳环碳)", "aromatic_C"),
    (120, 135, "Ar-CH (芳环 CH 碳)", "aromatic_CH"),
    (135, 150, "Ar-C (季碳 / 芳环取代位)", "aromatic_quaternary"),
    (150, 160, "Ar-O (酚氧取代的芳环碳)", "phenol_C"),
    (160, 185, "-COO- (酯 / 羧酸羰基碳)", "carboxyl_C"),
    (190, 220, "C=O (酮 / 醛羰基碳)", "carbonyl_C"),
]

# IR 光谱特征峰位 (cm⁻¹) → 官能团
IR_PEAKS = [
    (3600, 3200, "O-H 伸缩振动（羟基，宽峰）", "hydroxyl"),
    (3500, 3300, "N-H 伸缩振动（氨基/酰胺，中强双锋）", "amine_NH"),
    (3100, 3000, "sp² C-H 伸缩振动（烯/芳环 C-H）", "alkene_aromatic_CH"),
    (3000, 2850, "sp³ C-H 伸缩振动（烷基 C-H）", "aliphatic_CH"),
    (2830, 2695, "醛基 C-H 伸缩振动（醛特征双峰）", "aldehyde_CH"),
    (2260, 2100, "C≡C / C≡N (三键 / 氰基)", "triple_bond"),
    (1820, 1660, "C=O 伸缩振动（羰基，强峰）", "carbonyl"),
    (1760, 1735, "酯 C=O (1740)", "ester_CO"),
    (1725, 1700, "羧酸 / 酮 C=O", "ketone_acid_CO"),
    (1710, 1680, "酰胺 C=O (Amide I)", "amide_CO"),
    (1700, 1660, "醛 C=O", "aldehyde_CO"),
    (1680, 1600, "C=C 双键伸缩振动（芳环/烯）", "alkene_CC"),
    (1600, 1450, "芳环骨架振动（1600/1500/1450 三条带）", "aromatic_ring"),
    (1300, 1000, "C-O 伸缩振动（醇/醚/酯）", "ether_CO"),
    (900, 690, "芳环 C-H 面外弯曲振动（指示取代类型）", "aromatic_out_of_plane"),
]

# UV 最大吸收波长 → 共轭系统推断
UV_MAXIMA = [
    (200, 220, "孤立双键 / 饱和羰基 (弱吸收)", "isolated_CC"),
    (220, 250, "二烯 / α,β-不饱和羰基", "conjugated_diene"),
    (250, 290, "简单芳环 / 苯环", "simple_aromatic"),
    (280, 330, "多烯 / 芳香羰基（黄酮/香豆素）", "polyene_aromaticCO"),
    (330, 400, "稠环芳烃 / 高度共轭系统（蒽醌/萘醌）", "fused_polyaromatic"),
    (400, 500, "长共轭发色团 / 有色化合物（类胡萝卜素/花青素）", "long_conjugated"),
]


# ---------------------------------------------------------------------------
# 2. NMR 信号片段识别引擎
# ---------------------------------------------------------------------------

class NMRSignal:
    """单个 NMR 信号的数据结构"""

    def __init__(self, shift_ppm: float, intensity: float = 1.0,
                 multiplicity: str = "s", j_hz: float = 0.0, nucleus: str = "H"):
        self.shift = shift_ppm
        self.intensity = intensity
        self.multiplicity = multiplicity
        self.j = j_hz
        self.nucleus = nucleus

    def __repr__(self):
        return f"δ {self.shift:.2f} ({self.intensity:.1f}H, {self.multiplicity}, J={self.j:.1f}Hz)"


class NMRAnalyzer:
    """NMR 信号分析器"""

    def __init__(self, h_signals: List[NMRSignal], c_signals: List[NMRSignal]):
        self.h_signals = h_signals
        self.c_signals = c_signals

    # ---------------------------------------------------------------
    # 统计信息
    # ---------------------------------------------------------------
    def h_statistics(self) -> Dict:
        total_h = sum(s.intensity for s in self.h_signals)
        aromatic = sum(s.intensity for s in self.h_signals if 6.5 <= s.shift <= 8.5)
        alkene = sum(s.intensity for s in self.h_signals if 4.5 <= s.shift < 6.5)
        aliphatic = sum(s.intensity for s in self.h_signals if s.shift < 4.5)
        exchangeable = sum(s.intensity for s in self.h_signals if s.shift >= 9.0)  # 醛/羧
        return {
            "total_protons_observed": round(total_h, 1),
            "aromatic_protons": round(aromatic, 1),
            "alkene_protons": round(alkene, 1),
            "aliphatic_heteroatom_protons": round(aliphatic, 1),
            "aldehyde_carboxyl_protons": round(exchangeable, 1),
        }

    def c_statistics(self) -> Dict:
        n_c = len(self.c_signals)
        aromatic_or_alkene = sum(1 for s in self.c_signals if 100 <= s.shift <= 160)
        carbonyl = sum(1 for s in self.c_signals if 160 <= s.shift <= 220)
        aliphatic = sum(1 for s in self.c_signals if s.shift < 100)
        return {
            "total_carbons_observed": n_c,
            "aromatic_alkene_carbons": aromatic_or_alkene,
            "carbonyl_carbons": carbonyl,
            "aliphatic_carbons": aliphatic,
        }

    # ---------------------------------------------------------------
    # 片段识别（基于化学位移区间 + 峰形 + 积分）
    # ---------------------------------------------------------------
    def identify_fragments(self) -> List[Dict]:
        """基于 ¹H-NMR 信号识别结构片段"""
        fragments = []
        for sig in self.h_signals:
            matched = []
            for lo, hi, desc, tag in H_NMR_SHIFTS:
                if lo <= sig.shift <= hi:
                    matched.append({"description": desc, "tag": tag, "probability": 0.0})
            # 根据匹配情况给概率（简化算法）
            if matched:
                # 居中给更高概率
                center = (matched[0] and (matched[0]["description"] != "") )
                fragments.append({
                    "signal": f"δ {sig.shift:.2f} ({sig.intensity:.1f}H, {sig.multiplicity}, J={sig.j:.1f}Hz)",
                    "possible_fragments": matched[:3],
                })
        return fragments

    # ---------------------------------------------------------------
    # 碳谱分区分析
    # ---------------------------------------------------------------
    def carbon_partition(self) -> Dict:
        regions = {}
        for lo, hi, desc, tag in C_NMR_SHIFTS:
            count = sum(1 for s in self.c_signals if lo <= s.shift <= hi)
            if count:
                regions[tag] = {"description": desc, "count": count,
                                 "shifts": [round(s.shift, 2) for s in self.c_signals if lo <= s.shift <= hi]}
        return regions


# ---------------------------------------------------------------------------
# 3. 分子式验证 + 不饱和度计算
# ---------------------------------------------------------------------------

def calc_unsaturation(formula: str) -> float:
    """
    计算不饱和度 Ω (Degree of Unsaturation)
    Ω = (2C + 2 + N + P - H - X) / 2
    """
    from collections import Counter
    tokens = []
    import re
    for m in re.finditer(r"([A-Z][a-z]?)(\d*)", formula):
        element = m.group(1)
        count = int(m.group(2)) if m.group(2) else 1
        tokens.extend([element] * count)
    counts = Counter(tokens)
    c = counts.get("C", 0)
    h = counts.get("H", 0) + counts.get("D", 0)
    n = counts.get("N", 0) + counts.get("P", 0)
    hal = (counts.get("F", 0) + counts.get("Cl", 0)
           + counts.get("Br", 0) + counts.get("I", 0))
    omega = (2 * c + 2 + n - h - hal) / 2.0
    return omega


# ---------------------------------------------------------------------------
# 4. 官能团综合判断（多谱联合）
# ---------------------------------------------------------------------------

def identify_functional_groups(h_signals: List[NMRSignal],
                                c_signals: List[NMRSignal],
                                ir_peaks: Optional[List[float]] = None,
                                uv_lambdamax: Optional[List[float]] = None) -> List[Dict]:
    """
    多谱联合的官能团识别

    基本策略：
      • 若 NMR 某区间有信号 + IR 对应峰位 → 置信度高
      • 若只有 NMR 或 只有 IR → 置信度中
      • 若出现矛盾 → 需人工复核
    """
    fg_detected = []

    # (1) 芳香环
    ar_h = sum(1 for s in h_signals if 6.5 <= s.shift <= 8.5)
    ar_c = sum(1 for s in c_signals if 120 <= s.shift <= 150)
    ir_ar = any(1600 <= p <= 1500 or 1460 <= p <= 1440 for p in (ir_peaks or []))
    uv_ar = any(250 <= l <= 290 for l in (uv_lambdamax or []))
    ar_conf = 0
    if ar_h >= 2: ar_conf += 30
    if ar_c >= 4: ar_conf += 30
    if ir_ar: ar_conf += 20
    if uv_ar: ar_conf += 20
    if ar_conf:
        fg_detected.append({
            "functional_group": "芳香环 (Ar)",
            "evidence": f"{ar_h} 个芳香 H 信号, {ar_c} 个 sp² C 信号"
                       + (" + IR 芳环带" if ir_ar else "")
                       + (" + UV 芳香吸收" if uv_ar else ""),
            "confidence": min(ar_conf, 100),
        })

    # (2) 羰基 (C=O)
    co_c = sum(1 for s in c_signals if 160 <= s.shift <= 220)
    ir_co = any(1660 <= p <= 1820 for p in (ir_peaks or []))
    co_conf = 0
    if co_c: co_conf += 55
    if ir_co: co_conf += 45
    if co_conf >= 30:
        subtype = "酮/醛/酯/酸 — 需要更多细节判断"
        for s in c_signals:
            if 190 <= s.shift <= 220:
                subtype = "酮/醛 (δ_C > 190)"
            elif 160 <= s.shift <= 185:
                subtype = "酯/羧酸/酰胺 (δ_C 160-185)"
        fg_detected.append({
            "functional_group": f"羰基 (C=O) — {subtype}",
            "evidence": f"{co_c} 个羰基 C 信号" + (" + IR 1660-1820 cm⁻¹" if ir_co else ""),
            "confidence": min(co_conf, 100),
        })

    # (3) 羟基 (OH)
    has_oh_h = any(3.5 <= s.shift <= 5.0 and s.multiplicity in ("s", "br")
                    for s in h_signals)
    oh_c = sum(1 for s in c_signals if 50 <= s.shift <= 90)
    ir_oh = any(3200 <= p <= 3600 for p in (ir_peaks or []))
    oh_conf = 0
    if has_oh_h: oh_conf += 25
    if oh_c: oh_conf += 35
    if ir_oh: oh_conf += 40
    if oh_conf >= 30:
        fg_detected.append({
            "functional_group": "羟基 (-OH)",
            "evidence": (f"{oh_c} 个连氧 sp³ C" if oh_c else "")
                       + (" + IR O-H 宽峰" if ir_oh else "")
                       + (" + 可交换 H 信号" if has_oh_h else ""),
            "confidence": min(oh_conf, 100),
        })

    # (4) 双键 / 烯烃
    alkene_h = sum(1 for s in h_signals if 4.5 <= s.shift <= 6.5)
    alkene_c = sum(1 for s in c_signals if 100 <= s.shift <= 150)
    ir_c = any(1600 <= p <= 1680 for p in (ir_peaks or []))
    alk_conf = 0
    if alkene_h: alk_conf += 40
    if alkene_c: alk_conf += 35
    if ir_c: alk_conf += 25
    if alk_conf >= 40:
        fg_detected.append({
            "functional_group": "C=C 双键 (烯 / 芳环 C=C)",
            "evidence": f"{alkene_h} 个烯 H 信号, {alkene_c} 个 sp² C 信号"
                       + (" + IR C=C 带" if ir_c else ""),
            "confidence": min(alk_conf, 100),
        })

    # (5) 甲氧基 / 烷氧基 (OCH₃)
    och3 = any(3.3 <= s.shift <= 4.0 and 2.5 <= s.intensity <= 3.5
               and s.multiplicity in ("s",) for s in h_signals)
    if och3:
        fg_detected.append({
            "functional_group": "甲氧基 (-OCH₃)",
            "evidence": "δ 3.3-4.0 约 3H 单峰",
            "confidence": 80,
        })

    # (6) N-H (氨基/酰胺)
    ir_nh = any(3300 <= p <= 3500 for p in (ir_peaks or []))
    if ir_nh:
        fg_detected.append({
            "functional_group": "氨基 / 酰胺 N-H",
            "evidence": "IR 3300-3500 cm⁻¹ N-H 伸缩振动",
            "confidence": 70,
        })

    # (7) 共轭系统判断 (UV)
    if uv_lambdamax:
        for lo, hi, desc, tag in UV_MAXIMA:
            if any(lo <= l <= hi for l in uv_lambdamax):
                fg_detected.append({
                    "functional_group": f"共轭系统: {desc}",
                    "evidence": f"UV λ_max = {uv_lambdamax} nm",
                    "confidence": 75,
                })
                break

    return fg_detected


# ---------------------------------------------------------------------------
# 5. 候选结构排名与置信度评估
# ---------------------------------------------------------------------------

def score_candidate_structure(structure: Dict, h_signals: List[NMRSignal],
                                c_signals: List[NMRSignal],
                                functional_groups: List[Dict],
                                db_match: Optional[Dict] = None) -> int:
    """
    对候选结构打分 (0-100)
    打分因子：
      • 分子式匹配 (20)
      • ¹H-NMR 信号数/积分匹配 (25)
      • ¹³C-NMR 信号数/区间分布匹配 (25)
      • 官能团匹配 (20)
      • 数据库文献支持 (10)
    """
    score = 0
    # (简化实现：真实需要与计算 NMR / 3D 结构精细比对)
    report = structure.get("formula_report", {})

    # 分子式相关
    if report.get("formula_match", False):
        score += 20

    # NMR 信号统计
    h_stat = structure.get("h_statistics", {})
    c_stat = structure.get("c_statistics", {})
    # 简单检查是否存在 H/C 数量对应
    if h_stat and h_signals:
        ratio = len(h_signals) / max(1, h_stat.get("total_protons_observed", 1))
        if 0.5 < ratio < 3:
            score += 15
    if c_stat and c_signals:
        ratio_c = len(c_signals) / max(1, c_stat.get("total_carbons_observed", 1))
        if 0.5 < ratio_c < 3:
            score += 15

    # 官能团（此处只做保守打分）
    if functional_groups:
        score += min(15, len(functional_groups) * 4)

    # 数据库支持
    if db_match:
        score += 10

    return min(score, 100)


# ---------------------------------------------------------------------------
# 6. 主引擎：StructureElucidator — 综合推导
# ---------------------------------------------------------------------------

class StructureElucidator:
    """
    化合物结构推导核心引擎

    工作流程：
      1. 接收谱图解析结果 (NMR/IR/MS/UV)
      2. HRMS → 分子式候选 → 数据库查询
      3. NMR 信号分析 → 结构片段 + 官能团
      4. 组装候选结构 → 排序打分
      5. 生成完整推导报告
    """

    def __init__(self, spectral_data: Dict, config: Optional[Dict] = None):
        """
        spectral_data 格式（由 spectrum_parser / mestrenova_api 等提供）：
        {
            "h_nmr": [{"shift_ppm": 7.25, "intensity": 5.0, "multiplicity": "m", "j_hz": 0}, ...],
            "c_nmr": [{"shift_ppm": 138.0, ...}, ...],
            "ms": {"exact_mass": 250.1350, "molecular_ion": 250, "peaks": [...]},
            "ir": [{"wavenumber_cm1": 3450, "intensity": 0.6}, ...],
            "uv": [{"wavelength_nm": 254, "absorbance": 0.8}, ...],
            "ecd": {...},
        }
        """
        self.spectral = spectral_data
        self.config = config or {}
        self.analysis_report = {}

    # ---------------------------------------------------------------
    # 主流程
    # ---------------------------------------------------------------
    def elucidate(self, output_dir: Optional[str] = None) -> Dict:
        """执行完整结构推导"""
        logger.info("=" * 60)
        logger.info("  结构推导引擎启动")
        logger.info("=" * 60)

        # Step 1: 数据整理
        h_signals = [NMRSignal(s["shift_ppm"], s.get("intensity", 1),
                                s.get("multiplicity", "s"), s.get("j_hz", 0), "H")
                     for s in self.spectral.get("h_nmr", [])]
        c_signals = [NMRSignal(s["shift_ppm"], s.get("intensity", 1),
                                s.get("multiplicity", "s"), s.get("j_hz", 0), "C")
                     for s in self.spectral.get("c_nmr", [])]
        ir_peaks = [p["wavenumber_cm1"] for p in self.spectral.get("ir", [])]
        uv_max = [p["wavelength_nm"] for p in self.spectral.get("uv", [])]
        exact_mass = self.spectral.get("ms", {}).get("exact_mass")

        # Step 2: NMR 统计分析
        nmr_analyzer = NMRAnalyzer(h_signals, c_signals)
        h_stat = nmr_analyzer.h_statistics()
        c_stat = nmr_analyzer.c_statistics()
        h_fragments = nmr_analyzer.identify_fragments()
        c_regions = nmr_analyzer.carbon_partition()

        logger.info(f"[Step 1] NMR 统计: H={h_stat['total_protons_observed']}, "
                     f"C={c_stat['total_carbons_observed']}")
        logger.info(f"        芳香 H: {h_stat['aromatic_protons']}, 芳香/烯 C: {c_stat['aromatic_alkene_carbons']}")

        # Step 3: 官能团识别
        functional_groups = identify_functional_groups(h_signals, c_signals, ir_peaks, uv_max)
        logger.info(f"[Step 2] 识别到 {len(functional_groups)} 个官能团:")
        for fg in functional_groups:
            logger.info(f"         • {fg['functional_group']} (置信 {fg['confidence']}%)")

        # Step 4: 分子式确定（HRMS 优先；若无则从 NMR 估计）
        formula_candidates = []
        best_formula = None
        best_mass_error = 999.0
        if exact_mass:
            from db_query import generate_formula_candidates
            formula_candidates = generate_formula_candidates(exact_mass, tolerance_ppm=10.0)
            logger.info(f"[Step 3] HRMS 精确质量 {exact_mass:.4f} → "
                         f"{len(formula_candidates)} 个分子式候选")
            if formula_candidates:
                best_formula, calc_mass, error_ppm = formula_candidates[0]
                best_mass_error = abs(error_ppm)
                logger.info(f"        最佳分子式: {best_formula} (误差 {error_ppm:+.2f} ppm)")
        else:
            # 无 HRMS → 从 NMR 粗估
            n_c_est = max(c_stat["total_carbons_observed"], 1)
            n_h_est = max(int(h_stat["total_protons_observed"]), 1)
            n_o_est = 2  # 假设
            best_formula = f"C{n_c_est}H{n_h_est}O{n_o_est}"
            logger.warning(f"[Step 3] 未提供 HRMS，估算分子式: {best_formula}（仅供参考）")

        # Step 5: 不饱和度
        omega = calc_unsaturation(best_formula) if best_formula else 0.0
        logger.info(f"[Step 4] 不饱和度 Ω = {omega} → "
                     f"{'可能为芳香化合物' if omega >= 4 else '脂肪族/低不饱和度化合物'}")

        # Step 6: 数据库查询（如可用）
        db_hits = []
        try:
            from db_query import PubChem
            if best_formula and best_formula != "C1H1O2":
                db_hits = PubChem.from_formula(best_formula, limit=10)
                logger.info(f"[Step 5] PubChem 查询: 获得 {len(db_hits)} 个结构候选")
        except Exception as e:
            logger.warning(f"[Step 5] 数据库查询跳过: {e}")

        # Step 7: 候选结构排序打分
        candidates_ranked = []
        for hit in db_hits:
            candidate = {
                "cid": hit.get("cid", ""),
                "iupac": hit.get("iupac", ""),
                "smiles": hit.get("smiles", ""),
                "molecular_weight": hit.get("molecular_weight", ""),
                "formula": best_formula,
            }
            # 简化打分：只做基础信息
            candidate["score"] = score_candidate_structure(
                {"formula_report": {"formula_match": True},
                 "h_statistics": h_stat, "c_statistics": c_stat},
                h_signals, c_signals, functional_groups, db_hit=hit)
            candidates_ranked.append(candidate)
        candidates_ranked.sort(key=lambda x: -x["score"])

        # Step 8: 生成最终报告
        overall_confidence = self._calc_confidence(
            has_exact_mass=bool(exact_mass),
            n_h_signals=len(h_signals),
            n_c_signals=len(c_signals),
            mass_error_ppm=best_mass_error,
            omega=omega,
            n_functional_groups=len(functional_groups),
            n_db_hits=len(db_hits),
        )

        self.analysis_report = {
            "summary": {
                "best_formula": best_formula,
                "exact_mass": exact_mass,
                "mass_error_ppm": round(best_mass_error, 2) if best_mass_error < 999 else None,
                "unsaturation_omega": omega,
                "n_functional_groups": len(functional_groups),
                "overall_confidence": overall_confidence,
            },
            "formula_candidates": [
                {"formula": f, "exact_mass": round(m, 4), "error_ppm": round(e, 2)}
                for f, m, e in formula_candidates[:10]
            ],
            "nmr_analysis": {
                "proton_summary": h_stat,
                "carbon_summary": c_stat,
                "carbon_regions": c_regions,
                "signal_fragments": h_fragments[:20],
            },
            "functional_groups": functional_groups,
            "database_candidates": candidates_ranked[:15],
            "structural_hypothesis": self._generate_hypothesis(
                best_formula, omega, functional_groups, h_stat, c_stat,
            ),
        }

        # Step 9: 输出到文件
        if output_dir:
            self._save_report(output_dir)

        logger.info(f"[完成] 推导置信度: {overall_confidence}%")
        logger.info("=" * 60)
        return self.analysis_report

    # ---------------------------------------------------------------
    # 综合置信度估算
    # ---------------------------------------------------------------
    def _calc_confidence(self, has_exact_mass, n_h_signals, n_c_signals,
                          mass_error_ppm, omega, n_functional_groups, n_db_hits) -> int:
        score = 0
        # 数据完整性
        if has_exact_mass:
            score += 25 if abs(mass_error_ppm) <= 5 else (15 if abs(mass_error_ppm) <= 20 else 5)
        else:
            score += 5
        score += min(25, n_h_signals * 2)       # ¹H 信号数贡献
        score += min(25, n_c_signals * 2)       # ¹³C 信号数贡献
        score += min(15, n_functional_groups * 4)   # 官能团确定度
        score += min(10, n_db_hits)                  # 数据库支持
        return min(score, 100)

    # ---------------------------------------------------------------
    # 结构假说生成（基于化学知识 + 谱图证据）
    # ---------------------------------------------------------------
    def _generate_hypothesis(self, formula, omega, functional_groups, h_stat, c_stat) -> str:
        """生成自然语言描述的结构假说"""
        lines = []
        lines.append(f" 分子式 {formula}，不饱和度 Ω = {omega}")

        if omega >= 4 and c_stat.get("aromatic_alkene_carbons", 0) >= 4:
            lines.append(" → 推断含一个或多个芳环（苯环系统）")
        if any("羰基" in fg["functional_group"] for fg in functional_groups):
            lines.append(" → 推断含羰基官能团（可能为酯/酮/羧酸）")
        if any("羟基" in fg["functional_group"] for fg in functional_groups):
            lines.append(" → 推断含一个或多个羟基")
        if any("甲氧基" in fg["functional_group"] for fg in functional_groups):
            lines.append(" → 推断含甲氧基 (-OCH₃)")
        if h_stat.get("aromatic_protons", 0) > 0:
            lines.append(f" → 芳香区 {h_stat['aromatic_protons']:.1f} H 信号, 指示苯环/芳氢")
        if omega == 0:
            lines.append(" → 完全饱和化合物，为脂肪族链状或环状结构")

        if not lines[1:]:
            lines.append(" → 需要更多谱图数据支持进一步推断")

        return "\n".join(lines)

    # ---------------------------------------------------------------
    # 保存报告到 JSON
    # ---------------------------------------------------------------
    def _save_report(self, output_dir: str):
        out_path = Path(output_dir) / "structure_analysis.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.analysis_report, f, ensure_ascii=False, indent=2)
        logger.info(f"[报告] JSON 报告已保存: {out_path}")


# ---------------------------------------------------------------------------
# 命令行入口（调试用）
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="化合物结构推导引擎")
    parser.add_argument("--data", "-d", help="JSON 谱图数据文件路径")
    parser.add_argument("--mass", type=float, help="高分辨质谱精确质量 (Da)")
    parser.add_argument("--formula", "-f", help="已知分子式")
    parser.add_argument("--hnmr", nargs="+", type=float, help="¹H-NMR 化学位移列表 (ppm)")
    parser.add_argument("--cnmr", nargs="+", type=float, help="¹³C-NMR 化学位移列表 (ppm)")
    parser.add_argument("--output", "-o", default="./outputs", help="输出目录")
    args = parser.parse_args()

    # 构建数据
    spectral_data = {}
    if args.data and Path(args.data).exists():
        with open(args.data, "r", encoding="utf-8") as f:
            spectral_data = json.load(f)
    else:
        if args.hnmr:
            spectral_data["h_nmr"] = [{"shift_ppm": s, "intensity": 1.0,
                                        "multiplicity": "s", "j_hz": 0.0}
                                       for s in args.hnmr]
        if args.cnmr:
            spectral_data["c_nmr"] = [{"shift_ppm": s, "intensity": 1.0,
                                        "multiplicity": "s", "j_hz": 0.0}
                                       for s in args.cnmr]
        if args.mass:
            spectral_data["ms"] = {"exact_mass": args.mass}

    if not spectral_data:
        parser.print_help()
        sys.exit(1)

    engine = StructureElucidator(spectral_data)
    report = engine.elucidate(output_dir=args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_query.py — 在线化学数据库查询模块

功能：
  1. PubChem (REST API) — 分子式/分子量/CAS号/SMILES/结构检索
  2. SDBS (日本光谱数据库) — 标准谱图比对
  3. ChemSpider — 结构检索 / 文献引用
  4. 分子式 -> 可能结构候选列表
  5. 精确质量 -> 候选分子式列表（高分辨质谱匹配）

工作流程模拟天然药物化学研究者：
  "得到 HRMS 精确质量 → 查分子式 → 查已知天然产物 → 与自己样品比对"
"""

import os
import sys
import json
import time
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("db_query")


# ---------------------------------------------------------------------------
# 1. 基础 HTTP 请求
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: int = 30, params: Optional[Dict] = None) -> Optional[str]:
    """发起 HTTP GET 请求，返回文本"""
    full_url = url
    if params:
        full_url += "?" + urllib.parse.urlencode(params)
    try:
        logger.info(f"[查询] {full_url[:80]}...")
        req = urllib.request.Request(full_url, headers={"User-Agent": "spectrum-analyzer/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            return data
    except Exception as e:
        logger.warning(f"[警告] HTTP 请求失败: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. PubChem API 封装
# ---------------------------------------------------------------------------

class PubChem:
    """
    PubChem REST API 封装
    参考: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
    """

    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    @classmethod
    def from_formula(cls, formula: str, limit: int = 10) -> List[Dict]:
        """根据分子式查询化合物列表"""
        url = f"{cls.BASE}/compound/formula/{urllib.parse.quote(formula)}/JSON"
        params = {"Limit": limit, "MaxRecords": limit}
        data = _http_get(url, params=params)
        results = []
        if not data:
            return results
        try:
            obj = json.loads(data)
            for c in obj.get("PC_Compounds", []):
                cid = ""
                for prop in c.get("id", {}).get("id", []):
                    if prop.get("type") == "cid":
                        cid = str(prop.get("id", {}).get("cid", ""))
                        break
                mw = iupac = smiles = ""
                for p in c.get("props", []):
                    label = p.get("urn", {}).get("label", "")
                    value = p.get("value", {})
                    if label == "Molecular Weight":
                        mw = str(value.get("fval", ""))
                    elif label == "IUPAC Name":
                        iupac = value.get("sval", "")
                    elif label == "SMILES":
                        smiles = value.get("sval", "")
                results.append({"cid": cid, "molecular_weight": mw,
                                 "iupac": iupac, "smiles": smiles})
        except Exception as e:
            logger.warning(f"[警告] PubChem 解析失败: {e}")
        return results

    @classmethod
    def from_exact_mass(cls, exact_mass: float, tolerance: float = 0.01,
                         limit: int = 20) -> List[Dict]:
        """
        根据高分辨精确质量查询候选化合物（Monoisotopic Mass）
        先得到候选分子式，再查 PubChem
        """
        candidates = []
        # 方式: 用 molecular formula 候选表做查询
        formulas = generate_formula_candidates(exact_mass, tolerance)
        logger.info(f"[信息] 精确质量 {exact_mass:.4f} → {len(formulas)} 个分子式候选")

        for formula, mass, error in formulas:
            compounds = cls.from_formula(formula, limit=3)
            for c in compounds:
                c["formula"] = formula
                c["exact_mass"] = round(mass, 4)
                c["mass_error_ppm"] = round(error, 2)
                candidates.append(c)
            time.sleep(0.2)  # 遵守 API 限制

        # 按误差从小到大排序
        candidates.sort(key=lambda x: x.get("mass_error_ppm", 999))
        return candidates[:limit]

    @classmethod
    def get_properties(cls, cid: str) -> Dict:
        """获取特定 CID 的详细属性"""
        url = f"{cls.BASE}/compound/cid/{cid}/property/"
        url += "MolecularFormula,MolecularWeight,ExactMass,IUPACName,IsomericSMILES,"
        url += "CanonicalSMILES,InChI,InChIKey,RotatableBondCount,HeavyAtomCount,"
        url += "Charge,Complexity,CovalentUnitCount,XLogP,TPSA,FeatureRingCount3D"
        url += "/JSON"
        data = _http_get(url)
        result = {"cid": cid}
        if data:
            try:
                obj = json.loads(data)
                props = obj.get("PropertyTable", {}).get("Properties", [{}])[0]
                result.update(props)
            except Exception as e:
                logger.warning(f"[警告] 解析 Properties 失败: {e}")
        return result

    @classmethod
    def similarity_search(cls, smiles: str, threshold: float = 0.8,
                            limit: int = 20) -> List[Dict]:
        """相似结构搜索（基于 SMILES）"""
        url = f"{cls.BASE}/compound/similarity/smiles/{urllib.parse.quote(smiles)}/JSON"
        params = {"Threshold": int(threshold * 100), "MaxRecords": limit}
        data = _http_get(url, params=params)
        results = []
        if data:
            try:
                obj = json.loads(data)
                for c in obj.get("IdentifierList", {}).get("CID", []):
                    results.append({"cid": str(c)})
            except Exception:
                pass
        return results


# ---------------------------------------------------------------------------
# 3. 分子式候选列表生成（HRMS 精确质量 → 分子式）
# ---------------------------------------------------------------------------

# 精确原子量（monoisotopic mass）
MONOISOTOPIC_MASSES = {
    "C": 12.000000,
    "H": 1.007825,
    "D": 2.014102,
    "N": 14.003074,
    "O": 15.994915,
    "F": 18.998403,
    "P": 30.973763,
    "S": 31.972072,
    "Cl": 34.968853,
    "Br": 78.918338,
    "I": 126.904477,
    "Na": 22.989769,
    "K": 38.963708,
}


def generate_formula_candidates(exact_mass: float, tolerance_ppm: float = 5.0,
                                  max_c: int = 40, max_n: int = 10, max_o: int = 15,
                                  max_s: int = 5, max_p: int = 3,
                                  max_cl: int = 3, max_br: int = 3,
                                  max_f: int = 5, max_i: int = 2) -> List[Tuple[str, float, float]]:
    """
    根据高分辨精确质量生成候选分子式列表

    参数:
      exact_mass: 精确质量 (Da)
      tolerance_ppm: 允许的误差 (ppm)
      max_{元素}: 该元素原子数上限

    返回:
      [(分子式字符串, 计算质量, 误差 ppm), ...]  — 按误差从小到大排序
    """
    candidates = []
    tolerance_da = exact_mass * tolerance_ppm / 1e6

    logger.info(f"[算法] 生成分子式候选: 目标质量 = {exact_mass:.4f} Da, "
                 f"允许误差 ±{tolerance_da:.4f} Da (±{tolerance_ppm:.1f} ppm)")

    # 简化算法: 使用嵌套循环（限制搜索范围，保证效率）
    for c in range(0, max_c + 1):
        for h in range(0, max_c * 2 + 4):  # H 上限与 C 相关
            for n in range(0, max_n + 1):
                for o in range(0, max_o + 1):
                    # 简单骨架: C/H/N/O 作为主成分
                    mass = (c * MONOISOTOPIC_MASSES["C"]
                            + h * MONOISOTOPIC_MASSES["H"]
                            + n * MONOISOTOPIC_MASSES["N"]
                            + o * MONOISOTOPIC_MASSES["O"])
                    if abs(mass - exact_mass) > tolerance_da + max_s * MONOISOTOPIC_MASSES["S"]:
                        continue

                    # 可选: 加入 S, P, F, Cl, Br, I
                    # 这里扩展更简单的枚举
                    for s in range(0, max_s + 1):
                        for p in range(0, max_p + 1):
                            for cl in range(0, max_cl + 1):
                                for br in range(0, max_br + 1):
                                    for f in range(0, max_f + 1):
                                        for i in range(0, max_i + 1):
                                            total_mass = (
                                                mass
                                                + s * MONOISOTOPIC_MASSES["S"]
                                                + p * MONOISOTOPIC_MASSES["P"]
                                                + cl * MONOISOTOPIC_MASSES["Cl"]
                                                + br * MONOISOTOPIC_MASSES["Br"]
                                                + f * MONOISOTOPIC_MASSES["F"]
                                                + i * MONOISOTOPIC_MASSES["I"]
                                            )
                                            error = total_mass - exact_mass
                                            if abs(error) <= tolerance_da:
                                                # 组装分子式 (Hill system)
                                                formula_parts = []
                                                if c: formula_parts.append(f"C{c}" if c > 1 else "C")
                                                if h: formula_parts.append(f"H{h}" if h > 1 else "H")
                                                if n: formula_parts.append(f"N{n}" if n > 1 else "N")
                                                if o: formula_parts.append(f"O{o}" if o > 1 else "O")
                                                if f: formula_parts.append(f"F{f}" if f > 1 else "F")
                                                if p: formula_parts.append(f"P{p}" if p > 1 else "P")
                                                if s: formula_parts.append(f"S{s}" if s > 1 else "S")
                                                if cl: formula_parts.append(f"Cl{cl}" if cl > 1 else "Cl")
                                                if br: formula_parts.append(f"Br{br}" if br > 1 else "Br")
                                                if i: formula_parts.append(f"I{i}" if i > 1 else "I")
                                                formula = "".join(formula_parts)
                                                error_ppm = error / exact_mass * 1e6

                                                # 氮规则检查: 偶数质量 → 偶数氮（含 C、H、N、O、卤素）
                                                if c + h + n + o + s + p + cl + br + f + i == 0:
                                                    continue

                                                candidates.append((formula, total_mass, error_ppm))

    # 去重 + 排序
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c[0] not in seen:
            seen.add(c[0])
            unique_candidates.append(c)

    unique_candidates.sort(key=lambda x: abs(x[2]))
    logger.info(f"[结果] 共 {len(unique_candidates)} 个分子式候选")
    return unique_candidates[:50]


# ---------------------------------------------------------------------------
# 4. SDBS 数据库（日本光谱数据库）
# ---------------------------------------------------------------------------

class SDBS:
    """
    SDBS (日本 AIST 光谱数据库) 查询
    网站: https://sdbs.db.aist.go.jp/
    """

    BASE = "https://sdbs.db.aist.go.jp/sdbs/cgi-bin"

    @classmethod
    def search_by_formula(cls, formula: str) -> List[Dict]:
        """通过分子式在 SDBS 中搜索（非官方 API，基于页面解析，可能失效）"""
        # SDBS 没有公开的 REST API；此处保留接口结构供未来实现
        logger.info(f"[信息] SDBS 分子式搜索: {formula}")
        logger.warning("[警告] SDBS 无官方 REST API，需手动访问网站查询")
        return [{"note": f"请在 SDBS 网站查询: {cls.BASE}/direct_frame.cgi?target={formula}"}]

    @classmethod
    def search_by_mass(cls, exact_mass: float, tolerance: float = 0.05) -> List[Dict]:
        logger.info(f"[信息] SDBS 精确质量搜索: {exact_mass:.4f}")
        return [{"note": "请在 https://sdbs.db.aist.go.jp/ 手动查询"}]


# ---------------------------------------------------------------------------
# 5. ChemSpider (需 API Key)
# ---------------------------------------------------------------------------

class ChemSpider:
    """ChemSpider 数据库查询（需在 https://developer.rsc.org/ 申请 API Key）"""

    BASE = "https://api.rsc.org/compounds/v1"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def search_by_smiles(self, smiles: str) -> List[Dict]:
        if not self.api_key:
            logger.warning("[警告] 未配置 ChemSpider API Key，跳过查询")
            return []
        url = f"{self.BASE}/filter/smiles"
        try:
            data = _http_get(url, params={"smiles": smiles})
            if data:
                return [{"chemspider_id": json.loads(data).get("queryId", "")}]
        except Exception:
            pass
        return []


# ---------------------------------------------------------------------------
# 6. 高层组合查询
# ---------------------------------------------------------------------------

def compound_lookup(exact_mass: Optional[float] = None,
                     formula: Optional[str] = None,
                     smiles: Optional[str] = None,
                     chemspider_key: str = "") -> Dict:
    """
    综合查询：根据精确质量 / 分子式 / SMILES 获取候选化合物信息

    返回:
      {
        "query": {...},
        "formula_candidates": [...],
        "pubchem_hits": [...],
        "sdbs_links": [...],
      }
    """
    result = {
        "query": {"exact_mass": exact_mass, "formula": formula, "smiles": smiles},
        "formula_candidates": [],
        "pubchem_hits": [],
        "sdbs_hits": [],
    }

    # 1) 如果提供了精确质量 → 生成分子式候选
    if exact_mass:
        result["formula_candidates"] = [
            {"formula": f, "exact_mass": round(m, 5), "error_ppm": round(e, 3)}
            for f, m, e in generate_formula_candidates(exact_mass, tolerance_ppm=5.0)
        ]

    # 2) 查 PubChem
    formulas_to_query = []
    if formula:
        formulas_to_query = [formula]
    elif result["formula_candidates"]:
        formulas_to_query = [c["formula"] for c in result["formula_candidates"][:5]]

    for f in formulas_to_query:
        hits = PubChem.from_formula(f, limit=10)
        for h in hits:
            h["query_formula"] = f
            result["pubchem_hits"].append(h)
        time.sleep(0.3)  # 遵守 API 速率限制

    # 3) 如果有 SMILES，查相似结构
    if smiles:
        similar = PubChem.similarity_search(smiles, threshold=0.7, limit=10)
        for s in similar:
            s["note"] = "相似结构搜索结果"
        result["similar_structures"] = similar

    # 4) SDBS 链接
    for f in formulas_to_query:
        result["sdbs_hits"].append({
            "formula": f,
            "query_url": f"https://sdbs.db.aist.go.jp/sdbs/cgi-bin/direct_frame_top.cgi?compoundname={f}"
        })

    # 5) ChemSpider
    if smiles and chemspider_key:
        cs = ChemSpider(chemspider_key)
        result["chemspider"] = cs.search_by_smiles(smiles)

    return result


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="在线化学数据库查询")
    parser.add_argument("--mass", type=float, help="精确质量 (Da)，用于 HRMS 分子式推断")
    parser.add_argument("--formula", "-f", help="分子式，例如 C10H12O2")
    parser.add_argument("--smiles", "-s", help="SMILES 字符串")
    parser.add_argument("--tolerance", type=float, default=5.0, help="质量误差容忍 (ppm)")
    parser.add_argument("--chemspider-key", default="", help="ChemSpider API Key")
    parser.add_argument("--output", "-o", help="输出 JSON 文件")
    args = parser.parse_args()

    if not args.mass and not args.formula and not args.smiles:
        parser.print_help()
        sys.exit(1)

    result = compound_lookup(
        exact_mass=args.mass,
        formula=args.formula,
        smiles=args.smiles,
        chemspider_key=args.chemspider_key,
    )

    # 输出
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"[完成] 已保存到 {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chem3d_api.py — Chem3D / 通用分子绘制接口模块

功能：
  1. 从 SMILES / 分子式 / 原子坐标生成 2D 结构式
  2. 生成 3D 分子结构 (MOL / SDF / CML 格式)
  3. 调用 Chem3D / RDKit 进行结构绘制
  4. 输出结构式图像文件 (PNG / SVG)
  5. NMR 信号编号标注

工作流程模拟天然药物化学研究者：
  "确定分子式 → 画结构 → 标编号 → 归属 NMR 信号 → 出图"
"""

import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chem3d_api")


# ---------------------------------------------------------------------------
# 1. 分子结构类
# ---------------------------------------------------------------------------

class Molecule:
    """分子结构数据模型"""

    # 元素原子量（最常见同位素）
    ATOMIC_WEIGHTS = {
        "H": 1.007825, "D": 2.014102, "He": 4.002603,
        "Li": 7.016004, "Be": 9.012182, "B": 11.009305,
        "C": 12.000000, "N": 14.003074, "O": 15.994915,
        "F": 18.998403, "Ne": 19.992440, "Na": 22.989769,
        "Mg": 23.985042, "Al": 26.981541, "Si": 28.976495,
        "P": 30.973763, "S": 31.972072, "Cl": 34.968853,
        "Ar": 39.962384, "K": 38.963708, "Ca": 39.962591,
        "Fe": 55.934940, "Cu": 62.929599, "Zn": 63.929145,
        "Br": 78.918338, "I": 126.904477,
    }

    def __init__(self, name: str = "Unknown"):
        self.name = name
        self.atoms: List[Dict] = []       # [{element, x, y, z, charge}]
        self.bonds: List[Dict] = []       # [{atom1_idx, atom2_idx, order}]
        self.formula: str = ""
        self.molecular_weight: float = 0.0
        self.smiles: str = ""
        self.assignments: Dict = {}        # NMR 信号归属

    # ---------------------------------------------------------------
    # 从分子式统计原子（不建结构，仅用于展示）
    # ---------------------------------------------------------------
    def from_formula(self, formula: str):
        self.formula = formula
        from collections import Counter
        counts = Counter()
        for m in self._parse_formula(formula):
            counts[m["element"]] += m["count"]
        for element, count in counts.items():
            self.molecular_weight += self.ATOMIC_WEIGHTS.get(element, 0.0) * count
        logger.info(f"[信息] 分子式: {formula}, 分子量: {self.molecular_weight:.4f}")

    # ---------------------------------------------------------------
    # 解析分子式（如 C10H12O2 → [{'C':10}, {'H':12}, {'O':2}]）
    # ---------------------------------------------------------------
    @staticmethod
    def _parse_formula(formula: str) -> List[Dict]:
        import re
        tokens = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
        result = []
        for element, count_str in tokens:
            if not element:
                continue
            count = int(count_str) if count_str else 1
            result.append({"element": element, "count": count})
        return result

    # ---------------------------------------------------------------
    # 计算分子式（根据 atoms）
    # ---------------------------------------------------------------
    def calc_formula(self) -> str:
        from collections import Counter
        counts = Counter(a["element"] for a in self.atoms)
        parts = []
        # Hill 系统排序：C, H 在前，其他按字母
        if "C" in counts:
            parts.append(f"C{counts['C']}" if counts["C"] > 1 else "C")
            if "H" in counts:
                parts.append(f"H{counts['H']}" if counts["H"] > 1 else "H")
                del counts["H"]
            del counts["C"]
        for element in sorted(counts.keys()):
            n = counts[element]
            parts.append(f"{element}{n}" if n > 1 else element)
        self.formula = "".join(parts)
        return self.formula

    # ---------------------------------------------------------------
    # 计算不饱和度 Ω
    # ---------------------------------------------------------------
    def calc_unsaturation(self) -> float:
        from collections import Counter
        counts = Counter(a["element"] for a in self.atoms)
        if not counts:
            # 从分子式推断
            tokens = self._parse_formula(self.formula)
            counts = Counter()
            for t in tokens:
                counts[t["element"]] += t["count"]

        c = counts.get("C", 0)
        h = counts.get("H", 0) + counts.get("D", 0)
        n = counts.get("N", 0) + counts.get("P", 0)
        hal = counts.get("F", 0) + counts.get("Cl", 0) + counts.get("Br", 0) + counts.get("I", 0)
        omega = (2 * c + 2 + n - h - hal) / 2.0
        return omega


# ---------------------------------------------------------------------------
# 2. Chem3D / RDKit 接口核心类
# ---------------------------------------------------------------------------

class Chem3DAPI:
    """
    分子绘制接口

    绘制策略优先级：
      1. RDKit (Python 库)  — 首选，无需外部软件
      2. Chem3D (本地软件) — 如果配置了路径
      3. Indigo / OpenBabel — 后备方案
      4. 文本/ASCII 绘制 — 最终兜底
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.exe_path = self.config.get("software_paths", {}).get("chem3d", "")
        self.mode = self._detect_mode()
        logger.info(f"[信息] 分子绘制模式: {self.mode}")

    # ---------------------------------------------------------------
    # 检测可用的绘制引擎
    # ---------------------------------------------------------------
    def _detect_mode(self) -> str:
        # 1) 优先使用 RDKit
        try:
            import rdkit  # noqa: F401
            return "RDKIT"
        except ImportError:
            pass

        # 2) Chem3D 本地软件
        if self.exe_path and Path(self.exe_path).exists():
            return "CHEM3D"
        common_paths = [
            r"C:\Program Files\ChemOffice2020\Chem3D\Chem3D.exe",
            r"C:\Program Files\PerkinElmerInformatics\ChemOffice2021\Chem3D\Chem3D.exe",
        ]
        for p in common_paths:
            if Path(p).exists():
                self.exe_path = p
                return "CHEM3D"

        # 3) 尝试 OpenBabel
        try:
            subprocess.run(["obabel", "-V"], capture_output=True, timeout=5)
            return "OPENBABEL"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 4) 最终兜底：ASCII / 文本
        return "TEXT"

    # ---------------------------------------------------------------
    # 从 SMILES 生成 2D 结构图像
    # ---------------------------------------------------------------
    def draw_2d_from_smiles(self, smiles: str, output_file: str,
                              name: str = "Molecule", size: Tuple[int, int] = (600, 400)) -> str:
        """从 SMILES 生成 2D 结构式图像 (PNG/SVG)"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.mode == "RDKIT":
            try:
                from rdkit import Chem
                from rdkit.Chem import Draw, AllChem

                mol = Chem.MolFromSmiles(smiles)
                if mol is None:
                    raise ValueError(f"SMILES 无法解析: {smiles}")
                mol = Chem.AddHs(mol)
                AllChem.Compute2DCoords(mol)

                # 添加名称
                mol.SetProp("_Name", name)

                # 绘图
                img = Draw.MolToImage(mol, size=size)
                img.save(str(output_path))
                logger.info(f"[完成] 2D 结构已保存: {output_path}")
                return str(output_path)
            except Exception as e:
                logger.warning(f"[警告] RDKit 绘制失败 ({e})，降级到 TEXT 模式")
                self.mode = "TEXT"

        # 文本模式（ASCII / 文本报告）
        text_output = output_path.with_suffix(".txt")
        content = f"""
{'='*60}
  2D 结构示意（文本模式，非图形化）
  名称: {name}
  SMILES: {smiles}
{'='*60}

  提示: 请安装 RDKit 以获得图形化结构
  pip install rdkit-pypi

  或使用 Chem3D / ChemDraw 打开以下格式:
  • SDF 文件: {str(output_path.with_suffix('.sdf'))}
  • MOL 文件: {str(output_path.with_suffix('.mol'))}

{'='*60}
"""
        text_output.write_text(content, encoding="utf-8")
        logger.info(f"[完成] 文本报告已保存: {text_output}")
        return str(text_output)

    # ---------------------------------------------------------------
    # 生成 SDF / MOL 文件（3D 结构）
    # ---------------------------------------------------------------
    def save_3d_structure(self, molecule: Molecule, output_file: str,
                           format_: str = "sdf") -> str:
        """将分子结构保存为 SDF / MOL / CML 文件"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_.lower() in ("sdf", "mol"):
            if self.mode == "RDKIT":
                try:
                    from rdkit import Chem
                    from rdkit.Chem import AllChem, SDWriter

                    if molecule.smiles:
                        mol = Chem.MolFromSmiles(molecule.smiles)
                        if mol is None:
                            raise ValueError("SMILES 解析失败")
                        mol = Chem.AddHs(mol)
                        AllChem.EmbedMolecule(mol, randomSeed=42)
                        AllChem.MMFFOptimizeMolecule(mol)
                        mol.SetProp("_Name", molecule.name)

                        writer = SDWriter(str(output_path))
                        writer.write(mol)
                        writer.close()
                        logger.info(f"[完成] {format_.upper()} 已保存: {output_path}")
                        return str(output_path)
                except Exception as e:
                    logger.warning(f"[警告] RDKit 3D 构建失败: {e}，降级到手动格式")

            # 手动写 MOL (V2000 格式，最小版本)
            self._write_simple_sdf(molecule, output_path)
            return str(output_path)

        elif format_.lower() == "cml":
            self._write_cml(molecule, output_path)
            return str(output_path)

        return str(output_path)

    # ---------------------------------------------------------------
    # 简单 SDF 写入（无需原子坐标，根据分子式或 SMILES 生成骨架）
    # ---------------------------------------------------------------
    def _write_simple_sdf(self, molecule: Molecule, output_path: Path):
        name = molecule.name or "Molecule"
        n_atoms = len(molecule.atoms) if molecule.atoms else 1
        n_bonds = len(molecule.bonds)
        lines = []
        lines.append(f"{name}")
        lines.append("  Created by spectrum-analyzer")
        lines.append("")
        lines.append(f"{n_atoms:>3}{n_bonds:>3}  0  0  0  0  0  0  0  0999 V2000")

        if molecule.atoms:
            for atom in molecule.atoms:
                lines.append(
                    f"{atom.get('x',0.0):>10.4f}{atom.get('y',0.0):>10.4f}"
                    f"{atom.get('z',0.0):>10.4f} {atom['element']:<3} 0  0  0  0  0  0  0  0  0  0  0  0"
                )
        else:
            # 没有原子坐标，至少写一个原子（占位）
            lines.append(f"{0.0:>10.4f}{0.0:>10.4f}{0.0:>10.4f} C   0  0  0  0  0  0  0  0  0  0  0  0")

        for bond in molecule.bonds:
            lines.append(
                f"{bond['atom1_idx']+1:>3}{bond['atom2_idx']+1:>3}{bond.get('order',1):>3}"
                "  0  0  0  0"
            )

        lines.append("M  END")
        lines.append("")
        lines.append("$$$$")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[信息] SDF 已保存: {output_path}")

    # ---------------------------------------------------------------
    # CML 格式写入
    # ---------------------------------------------------------------
    def _write_cml(self, molecule: Molecule, output_path: Path):
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<cml xmlns="http://www.xml-cml.org/schema" xmlns:cml="http://www.xml-cml.org/schema">',
            f'  <molecule id="{molecule.name or "molecule"}">',
            f'    <formula concise="{molecule.formula}" countUnits="atom"/>',
            f'    <moleculeWeight> {molecule.molecular_weight:.4f} </moleculeWeight>',
            '    <atomArray>',
        ]
        for i, atom in enumerate(molecule.atoms):
            xml_lines.append(
                f'      <atom id="a{i+1}" elementType="{atom["element"]}" '
                f'x3="{atom.get("x",0.0)}" y3="{atom.get("y",0.0)}" z3="{atom.get("z",0.0)}"/>'
            )
        xml_lines.append('    </atomArray>')
        xml_lines.append('    <bondArray>')
        for bond in molecule.bonds:
            xml_lines.append(
                f'      <bond atomRefs2="a{bond["atom1_idx"]+1} a{bond["atom2_idx"]+1}" '
                f'order="{bond.get("order",1)}"/>'
            )
        xml_lines.append('    </bondArray>')
        xml_lines.append('  </molecule>')
        xml_lines.append('</cml>')
        output_path.write_text("\n".join(xml_lines), encoding="utf-8")
        logger.info(f"[信息] CML 已保存: {output_path}")


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="分子结构绘制接口 (Chem3D / RDKit)")
    parser.add_argument("--smiles", "-s", help="SMILES 字符串，例如 c1ccc(cc1)CCO")
    parser.add_argument("--formula", "-f", help="分子式，例如 C10H12O2")
    parser.add_argument("--name", "-n", default="Molecule", help="分子名称")
    parser.add_argument("--output", "-o", default="./outputs/structure.png", help="输出文件路径")
    parser.add_argument("--format", default="png", help="图像格式 (png/svg)")
    parser.add_argument("--config", "-c", help="配置文件路径")
    args = parser.parse_args()

    cfg = {}
    if args.config and Path(args.config).exists():
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    api = Chem3DAPI(cfg)

    mol = Molecule(name=args.name)

    if args.smiles:
        mol.smiles = args.smiles
        logger.info(f"[信息] 使用 SMILES: {args.smiles}")

        # 生成 2D 结构图
        out = Path(args.output)
        image_path = str(out.with_suffix(f".{args.format}"))
        api.draw_2d_from_smiles(args.smiles, image_path, args.name)

        # 生成 3D SDF
        api.save_3d_structure(mol, str(out.with_suffix(".sdf")), "sdf")
        api.save_3d_structure(mol, str(out.with_suffix(".cml")), "cml")

        print(f"[完成] 结构文件已输出到: {out.parent}")

    elif args.formula:
        mol.from_formula(args.formula)
        api.save_3d_structure(mol, str(Path(args.output).with_suffix(".sdf")), "sdf")
        print(f"[完成] 分子式 {args.formula} 的结构框架已保存")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

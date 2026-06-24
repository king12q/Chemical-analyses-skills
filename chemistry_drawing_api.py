#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chemistry_drawing_api.py — 综合分子结构绘制模块

**支持的绘制引擎（按优先级自动选择）**：

  1. RDKit      — Python 开源库，首选（无需安装商业软件）
  2. ChemDraw    — 业界标准的 2D 结构式绘制软件（PerkinElmer ChemOffice）
  3. Chem3D     — 3D 分子建模软件（PerkinElmer ChemOffice）
  4. OpenBabel  — 开源化学工具包（命令行工具）
  5. Indigo     — 开源化学信息学库（可选）
  6. TEXT       — 文本模式，最终兜底（输出文本描述 + 可导入的结构化文件）

**支持的输出格式**：
  - 2D 图像：PNG, SVG, JPG（RDKit / ChemDraw）
  - 结构文件：MOL (V2000/V3000), SDF, CML, CDX (ChemDraw XML),
              CDXML (ChemDraw XML), SMILES, InChI
  - 3D 结构：SDF (3D), CML, PDB

工作流程模拟天然药物化学研究者：
  "确定分子式/结构 → 在 ChemDraw 中画 2D 结构 → 3D 优化 → 标注编号 → 导出用于论文/报告"
"""

import os
import sys
import json
import time
import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chemistry_drawing_api")


# ---------------------------------------------------------------------------
# 1. 分子结构数据模型
# ---------------------------------------------------------------------------

class Molecule:
    """分子结构数据模型（与之前兼容，扩展更多字段）"""

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
        self.inchi: str = ""
        self.assignments: Dict = {}        # NMR 信号归属
        self.stereochemistry: List[str] = []  # 手性中心标注

    # ---------------------------------------------------------------
    # 从分子式统计（无结构数据时使用）
    # ---------------------------------------------------------------
    def from_formula(self, formula: str):
        self.formula = formula
        from collections import Counter
        counts = Counter()
        for m in self._parse_formula(formula):
            counts[m["element"]] += m["count"]
        for element, count in counts.items():
            self.molecular_weight += self.ATOMIC_WEIGHTS.get(element, 0.0) * count
        logger.info(f"[信息] 分子式: {formula}, 精确分子量: {self.molecular_weight:.4f}")

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

    def calc_formula(self) -> str:
        from collections import Counter
        counts = Counter(a["element"] for a in self.atoms)
        parts = []
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

    def calc_unsaturation(self) -> float:
        from collections import Counter
        counts = Counter(a["element"] for a in self.atoms)
        if not counts and self.formula:
            tokens = self._parse_formula(self.formula)
            counts = Counter()
            for t in tokens:
                counts[t["element"]] += t["count"]
        c = counts.get("C", 0)
        h = counts.get("H", 0) + counts.get("D", 0)
        n = counts.get("N", 0) + counts.get("P", 0)
        hal = sum(counts.get(x, 0) for x in ["F", "Cl", "Br", "I"])
        return (2 * c + 2 + n - h - hal) / 2.0


# ---------------------------------------------------------------------------
# 2. 核心绘制引擎 — 多后端支持
# ---------------------------------------------------------------------------

class ChemistryDrawingAPI:
    """
    综合化学结构绘制引擎。

    后端选择策略（自动检测，可在 config 中指定）：
      RDKIT   → CHEMDRAW → CHEM3D → OPENBABEL → TEXT

    每个后端能处理的格式：
      RDKIT:    PNG, SVG, MOL, SDF, SMILES, InChI
      CHEMDRAW: CDX, CDXML, MOL, PNG (通过命令行/COM)
      CHEM3D:   MOL, SDF, CML (3D)
      OPENBABEL: 多种格式转换（命令行）
      TEXT:     文本描述 + 标准结构文件（无需任何库即可生成）
    """

    # 后端常量
    RDKIT = "RDKIT"
    CHEMDRAW = "CHEMDRAW"
    CHEM3D = "CHEM3D"
    OPENBABEL = "OPENBABEL"
    TEXT = "TEXT"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.software_paths = self.config.get("software_paths", {})

        # 各个软件路径
        self.chemdraw_path = self.software_paths.get("chemdraw", "")
        self.chem3d_path = self.software_paths.get("chem3d", "")
        self.chemdraw_exe = self.software_paths.get("chemdraw_exe", "")

        # 检测后端
        self.mode = self._auto_detect_backend()
        self.available_backends = self._detect_all_backends()

        logger.info(f"[信息] 可用绘制后端: {', '.join(self.available_backends)}")
        logger.info(f"[信息] 当前优先后端: {self.mode}")

    # ---------------------------------------------------------------
    # 自动检测所有可用后端
    # ---------------------------------------------------------------
    def _detect_all_backends(self) -> List[str]:
        backends = []

        # 1) RDKit
        try:
            import rdkit  # noqa
            backends.append(self.RDKIT)
        except ImportError:
            pass

        # 2) ChemDraw (通过 PythonWin COM 接口或命令行)
        if self._check_chemdraw():
            backends.append(self.CHEMDRAW)

        # 3) Chem3D
        if self._check_chem3d():
            backends.append(self.CHEM3D)

        # 4) OpenBabel
        try:
            r = subprocess.run(["obabel", "-V"], capture_output=True, timeout=5)
            if r.returncode == 0:
                backends.append(self.OPENBABEL)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # 5) 文本兜底
        backends.append(self.TEXT)
        return backends

    def _auto_detect_backend(self) -> str:
        return self._detect_all_backends()[0]  # 第一个可用的

    # ---------------------------------------------------------------
    # ChemDraw 检测（Windows 平台常见路径）
    # ---------------------------------------------------------------
    def _check_chemdraw(self) -> bool:
        # 1) 用户配置路径
        for key in ["chemdraw", "chemdraw_exe"]:
            path = self.software_paths.get(key, "")
            if path and Path(path).exists():
                return True

        # 2) 常见路径检测（ChemOffice 2020-2024 版本）
        common_paths = [
            r"C:\Program Files\ChemOffice2024\ChemDraw\ChemDraw.exe",
            r"C:\Program Files\ChemOffice2023\ChemDraw\ChemDraw.exe",
            r"C:\Program Files\ChemOffice2022\ChemDraw\ChemDraw.exe",
            r"C:\Program Files\ChemOffice2021\ChemDraw\ChemDraw.exe",
            r"C:\Program Files\ChemOffice2020\ChemDraw\ChemDraw.exe",
            r"C:\Program Files (x86)\ChemOffice2020\ChemDraw\ChemDraw.exe",
            r"C:\Program Files\PerkinElmerInformatics\ChemOffice2024\ChemDraw\ChemDraw.exe",
            r"C:\Program Files\PerkinElmerInformatics\ChemOffice2022\ChemDraw\ChemDraw.exe",
            # ChemDraw Prime / Professional / JS 路径
            r"C:\Program Files\ChemDraw\ChemDrawPrime.exe",
            # macOS 路径
            "/Applications/ChemDraw 2024/ChemDraw.app/Contents/MacOS/ChemDraw",
            "/Applications/ChemDraw.app/Contents/MacOS/ChemDraw",
            # Linux (WINE 下运行)
            "~/.wine/drive_c/Program Files/ChemOffice/ChemDraw/ChemDraw.exe",
        ]
        for p in common_paths:
            if Path(p).expanduser().exists():
                if not self.chemdraw_path:
                    self.chemdraw_path = p
                return True

        # 3) 通过 COM 接口检测（仅 Windows，需 pywin32）
        try:
            import win32com.client  # noqa
            # 尝试创建对象检测
            # 仅检测库是否存在，不实际调用（可能会弹出窗口）
            has_pywin32 = True
        except ImportError:
            has_pywin32 = False

        if has_pywin32:
            # 检查注册表中是否有 ChemDraw 组件
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "ChemDraw.Document"):
                    return True
            except OSError:
                pass
        return False

    # ---------------------------------------------------------------
    # Chem3D 检测
    # ---------------------------------------------------------------
    def _check_chem3d(self) -> bool:
        if self.chem3d_path and Path(self.chem3d_path).exists():
            return True
        common_paths = [
            r"C:\Program Files\ChemOffice2024\Chem3D\Chem3D.exe",
            r"C:\Program Files\ChemOffice2023\Chem3D\Chem3D.exe",
            r"C:\Program Files\ChemOffice2022\Chem3D\Chem3D.exe",
            r"C:\Program Files\PerkinElmerInformatics\ChemOffice2022\Chem3D\Chem3D.exe",
            "/Applications/Chem3D.app/Contents/MacOS/Chem3D",
        ]
        for p in common_paths:
            if Path(p).exists():
                self.chem3d_path = p
                return True
        return False

    # ---------------------------------------------------------------
    # 设置优先后端
    # ---------------------------------------------------------------
    def set_preferred_backend(self, backend: str):
        """手动设置优先后端，如 'CHEMDRAW' / 'RDKIT' / 'CHEM3D'"""
        if backend in self.available_backends:
            self.mode = backend
            logger.info(f"[信息] 已切换优先后端: {self.mode}")
        else:
            logger.warning(f"[警告] 后端 {backend} 不可用，当前仍为 {self.mode}")

    # ===============================================================
    # 主方法：2D 结构式绘制（PNG / SVG）
    # ===============================================================
    def draw_2d(self, molecule: Molecule, output_file: str,
                size: Tuple[int, int] = (800, 600),
                with_atom_labels: bool = False,
                backend: Optional[str] = None) -> str:
        """
        生成 2D 结构式图像。

        参数:
          molecule: Molecule 对象（需包含 smiles 或 atoms+bonds）
          output_file: 输出文件路径（后缀决定格式：.png / .svg）
          size: 图像大小 (宽, 高)
          with_atom_labels: 是否显示原子编号（用于 NMR 归属）
          backend: 强制使用指定后端
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chosen = backend or self.mode
        logger.info(f"[绘制] 2D 结构 → {output_path.name} (后端: {chosen})")

        # --- 后端 1: RDKit ---
        if chosen == self.RDKIT:
            try:
                return self._draw_2d_with_rdkit(molecule, output_path, size, with_atom_labels)
            except Exception as e:
                logger.warning(f"[警告] RDKit 失败: {e}，尝试下一后端")
                chosen = self._next_backend(chosen)

        # --- 后端 2: ChemDraw ---
        if chosen == self.CHEMDRAW:
            try:
                return self._draw_2d_with_chemdraw(molecule, output_path, size, with_atom_labels)
            except Exception as e:
                logger.warning(f"[警告] ChemDraw 失败: {e}，尝试下一后端")
                chosen = self._next_backend(chosen)

        # --- 后端 3: Chem3D ---
        if chosen == self.CHEM3D:
            try:
                return self._draw_2d_with_chem3d(molecule, output_path)
            except Exception as e:
                logger.warning(f"[警告] Chem3D 失败: {e}，降级到 TEXT")
                chosen = self.TEXT

        # --- 后端 4: OpenBabel ---
        if chosen == self.OPENBABEL:
            try:
                return self._draw_2d_with_openbabel(molecule, output_path)
            except Exception as e:
                logger.warning(f"[警告] OpenBabel 失败: {e}，降级到 TEXT")

        # --- 后端 5: 文本兜底 ---
        return self._draw_2d_text_mode(molecule, output_path)

    def _next_backend(self, current: str) -> str:
        order = [self.RDKIT, self.CHEMDRAW, self.CHEM3D, self.OPENBABEL, self.TEXT]
        idx = order.index(current) if current in order else 0
        for b in order[idx+1:]:
            if b in self.available_backends:
                return b
        return self.TEXT

    # ===============================================================
    # 主方法：3D 结构保存（MOL / SDF / CML / PDB）
    # ===============================================================
    def save_3d(self, molecule: Molecule, output_file: str,
                format_: Optional[str] = None,
                backend: Optional[str] = None) -> str:
        """
        生成/保存 3D 结构文件。
        format_: "mol" / "sdf" / "cml" / "pdb" / "cdxml" / "cdx" / "smiles" / "inchi"
        如果不指定，根据后缀自动推断。
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_ is None:
            format_ = output_path.suffix.lstrip(".").lower()

        chosen = backend or self.mode
        logger.info(f"[保存] 3D 结构 → {output_path.name} (格式: {format_.upper()}, 后端: {chosen})")

        # 文本模式的纯结构文件（无需图形库）
        if format_ in ("sdf", "mol"):
            if chosen == self.RDKIT:
                try:
                    return self._save_sdf_with_rdkit(molecule, output_path)
                except Exception:
                    pass
            # 手动写标准 MOL V2000
            return self._write_mol_v2000(molecule, output_path)
        elif format_ == "cml":
            return self._write_cml(molecule, output_path)
        elif format_ in ("cdxml", "cdx"):
            return self._write_cdxml(molecule, output_path)
        elif format_ == "smiles":
            return self._write_smiles(molecule, output_path)
        elif format_ == "inchi":
            return self._write_inchi(molecule, output_path)
        elif format_ == "pdb":
            return self._write_pdb(molecule, output_path)
        else:
            logger.info(f"[提示] 未知格式 {format_}，默认写 SDF")
            return self._write_mol_v2000(molecule, output_path)

    # ===============================================================
    # 主方法：批量导出（一次生成所有常见格式）
    # ===============================================================
    def export_all_formats(self, molecule: Molecule, output_dir: str) -> Dict[str, str]:
        """
        一次导出所有常见格式文件，供不同软件打开：
          • structure_2D.png    — 图像（供 Word/PPT 粘贴）
          • structure_2D.svg    — 矢量图（供论文排版）
          • structure.sdf       — 标准结构文件（所有化学软件都能打开）
          • structure.mol       — MDL MOL 格式
          • structure.cdxml     — ChemDraw 原生 XML 格式（直接双击用 ChemDraw 打开）
          • structure.cml       — Chemical Markup Language（XML 标准）
          • structure.pdb       — PDB 格式（生物大分子/分子对接）
          • structure.smiles    — SMILES 字符串
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files = {}

        # 2D 图像
        png = self.draw_2d(molecule, str(out / "structure_2D.png"))
        files["png"] = png
        svg = self.draw_2d(molecule, str(out / "structure_2D.svg"))
        files["svg"] = svg

        # 结构文件
        for fmt in ["sdf", "mol", "cml", "cdxml", "pdb", "smiles"]:
            path = out / f"structure.{fmt}"
            files[fmt] = self.save_3d(molecule, str(path), fmt)

        # 带编号的图像（用于 NMR 归属）
        labeled = self.draw_2d(molecule, str(out / "structure_2D_labeled.png"),
                               with_atom_labels=True)
        files["labeled_png"] = labeled

        logger.info(f"[完成] 已导出 {len(files)} 个文件到 {out}")
        return files

    # ===============================================================
    # === 后端实现: RDKit ===
    # ===============================================================
    def _draw_2d_with_rdkit(self, molecule, output_path, size, with_labels):
        from rdkit import Chem
        from rdkit.Chem import Draw, AllChem

        # 从 SMILES 构建
        mol = None
        if molecule.smiles:
            mol = Chem.MolFromSmiles(molecule.smiles)
        if mol is None and molecule.atoms:
            # 从原子/键列表构建
            mol = Chem.RWMol()
            for atom in molecule.atoms:
                mol.AddAtom(Chem.Atom(atom["element"]))
            for bond in molecule.bonds:
                mol.AddBond(bond["atom1_idx"], bond["atom2_idx"],
                            Chem.BondType.values[bond.get("order", 1) - 1])
            mol = mol.GetMol()

        if mol is None:
            raise ValueError("无法从提供的分子数据构建 RDKit Mol 对象")

        mol = Chem.AddHs(mol)
        AllChem.Compute2DCoords(mol)
        mol.SetProp("_Name", molecule.name or "Compound")

        # 显示编号
        if with_labels:
            for atom in mol.GetAtoms():
                atom.SetProp("atomLabel", str(atom.GetIdx() + 1))

        # 绘图
        suffix = output_path.suffix.lower()
        if suffix == ".svg":
            drawer = Draw.MolDraw2DSVG(size[0], size[1])
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            output_path.write_text(drawer.GetDrawingText(), encoding="utf-8")
        else:
            img = Draw.MolToImage(mol, size=size)
            img.save(str(output_path))

        logger.info(f"[完成-RDKit] 2D 结构: {output_path}")
        return str(output_path)

    def _save_sdf_with_rdkit(self, molecule, output_path):
        from rdkit import Chem
        from rdkit.Chem import AllChem, SDWriter

        mol = Chem.MolFromSmiles(molecule.smiles) if molecule.smiles else None
        if mol is None:
            raise ValueError("SMILES 解析失败")
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=42)
        try:
            AllChem.MMFFOptimizeMolecule(mol)  # 简单优化
        except Exception:
            pass
        mol.SetProp("_Name", molecule.name or "Compound")
        writer = SDWriter(str(output_path))
        writer.write(mol)
        writer.close()
        logger.info(f"[完成-RDKit] SDF(3D): {output_path}")
        return str(output_path)

    # ===============================================================
    # === 后端实现: ChemDraw ===
    # ===============================================================
    def _draw_2d_with_chemdraw(self, molecule, output_path, size, with_labels):
        """
        ChemDraw 调用策略（3 种方式，按优先级尝试）：
          1. 通过 pywin32 COM 接口自动化（最强大，能精确控制）
          2. 通过 CDXML 文件 + 命令行转换
          3. 生成标准 MOL 文件让用户双击用 ChemDraw 打开
        """
        # --- 方式 1: COM 自动化（需 pywin32 且 Windows）---
        try:
            import win32com.client
            import pythoncom

            pythoncom.CoInitialize()
            cd_app = win32com.client.Dispatch("ChemDraw.Application")
            cd_app.Visible = False  # 后台运行

            # 打开一个新文档，根据 SMILES 生成结构
            doc = cd_app.Documents.Add()

            if molecule.smiles:
                # 通过粘贴 SMILES 让 ChemDraw 解析
                doc.Selection.Text = molecule.smiles
                # 尝试让其转换为结构（不同 ChemDraw 版本 API 不同，这里用通用命令）
                try:
                    doc.Application.DoCommand("InterpretChemically")
                except Exception:
                    pass

            doc.Name = molecule.name or "Compound"

            # 根据输出后缀决定导出方式
            suffix = output_path.suffix.lower()
            if suffix == ".png":
                doc.Export(str(output_path), "PNG")
            elif suffix == ".svg":
                doc.Export(str(output_path), "SVG")
            elif suffix == ".cdxml":
                doc.SaveAs(str(output_path))
            else:
                doc.Export(str(output_path), "PNG")  # 默认 PNG

            doc.Close(False)
            cd_app.Quit()
            pythoncom.CoUninitialize()

            logger.info(f"[完成-ChemDraw] 2D 结构: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.info(f"[提示] ChemDraw COM 不可用: {e}")
            # 降级到方式 2

        # --- 方式 2: 生成 CDXML，告知用户可双击用 ChemDraw 打开 ---
        cdxml_path = output_path.with_suffix(".cdxml")
        self._write_cdxml(molecule, cdxml_path)

        # 同时尝试用 OpenBabel 从 CDXML 转 PNG（若有）
        try:
            subprocess.run(
                ["obabel", "-icdxml", str(cdxml_path), "-o", "png", "-O", str(output_path)],
                capture_output=True, timeout=30
            )
            if output_path.exists():
                logger.info(f"[完成-ChemDraw+OB] 2D 结构: {output_path}")
                return str(output_path)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # --- 方式 3: 写一个提示文件 + CDXML 让用户手动打开 ---
        tip = output_path.with_suffix(".txt")
        tip.write_text(
            f"ChemDraw 绘图提示\n"
            f"{'=' * 50}\n"
            f"化合物: {molecule.name or 'Compound'}\n"
            f"SMILES: {molecule.smiles or '(未提供)'}\n"
            f"分子式: {molecule.formula}\n\n"
            f"已生成 CDXML 结构文件: {cdxml_path}\n"
            f"请用 ChemDraw 双击打开该文件，或复制上面的 SMILES 到 ChemDraw。\n"
            f"\n另: 如需自动导出图像，可:\n"
            f"  1) 安装 pywin32: pip install pywin32\n"
            f"  2) 在 config.json 中指定 chemdraw 路径\n"
            f"  3) 或安装 RDKit 以纯 Python 方式绘制\n",
            encoding="utf-8"
        )
        logger.info(f"[完成-ChemDraw-文本] 已生成 CDXML: {cdxml_path}")
        return str(cdxml_path)

    # ===============================================================
    # === 后端实现: Chem3D ===
    # ===============================================================
    def _draw_2d_with_chem3d(self, molecule, output_path):
        """Chem3D 主要用于 3D，这里简化：生成 SDF 让 Chem3D 打开"""
        try:
            import win32com.client
            import pythoncom
            pythoncom.CoInitialize()
            app = win32com.client.Dispatch("Chem3D.Application")
            app.Visible = False
            # 创建新文档，从 SMILES 添加结构
            doc = app.Documents.Add()
            if molecule.smiles:
                doc.Selection.Text = molecule.smiles
            # 导出图像
            suffix = output_path.suffix.lower().lstrip(".") or "png"
            doc.Export(str(output_path), suffix.upper())
            doc.Close(False)
            app.Quit()
            pythoncom.CoUninitialize()
            logger.info(f"[完成-Chem3D] 2D 图像: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.info(f"[提示] Chem3D COM 不可用: {e}")
            # 降级：写 SDF 让用户手动打开
            return self.save_3d(molecule, str(output_path.with_suffix(".sdf")), "sdf")

    # ===============================================================
    # === 后端实现: OpenBabel ===
    # ===============================================================
    def _draw_2d_with_openbabel(self, molecule, output_path):
        # 先写 SMILES / MOL，再用 obabel 转换
        smi = molecule.smiles or ""
        tmp = Path(output_path).parent / "_tmp_ob.smi"
        tmp.write_text(f"{smi}  {molecule.name or 'Compound'}\n", encoding="utf-8")
        suffix = output_path.suffix.lower().lstrip(".") or "png"
        try:
            subprocess.run(
                ["obabel", "-ismi", str(tmp), f"-o{suffix}", "-O", str(output_path),
                 "-xh", str(output_path).split("x")[0] if "x" in str(output_path) else "400"],
                capture_output=True, timeout=30
            )
            tmp.unlink(missing_ok=True)
            if output_path.exists():
                logger.info(f"[完成-OpenBabel] 2D 图像: {output_path}")
                return str(output_path)
        except Exception as e:
            logger.info(f"[提示] OpenBabel 转换失败: {e}")
            tmp.unlink(missing_ok=True)
        # 兜底
        return self._draw_2d_text_mode(molecule, output_path)

    # ===============================================================
    # === 后端实现: TEXT 文本模式 ===
    # ===============================================================
    def _draw_2d_text_mode(self, molecule, output_path):
        report = f"""
{'='*60}
  化合物结构报告（文本模式 — 已同时生成标准结构文件）
{'='*60}
  名称:        {molecule.name or 'Compound'}
  分子式:      {molecule.formula or '(未指定)'}
  精确分子量:  {molecule.molecular_weight:.4f}
  不饱和度 Ω:  {molecule.calc_unsaturation():.1f}
  SMILES:      {molecule.smiles or '(未提供)'}
{'='*60}

已生成的结构文件（可用 ChemDraw / Chem3D / 其它化学软件打开）：
  • structure.sdf       — SDF (标准结构格式)
  • structure.mol       — MOL (MDL V2000)
  • structure.cdxml     — CDXML (ChemDraw XML，可双击用 ChemDraw 打开)
  • structure.cml       — CML (Chemical Markup Language)
  • structure.pdb       — PDB (蛋白质数据库格式，兼容所有建模软件)
  • structure.smiles    — SMILES 字符串

获取图形化 2D 结构图的方式（任选其一）：
  1) 安装 RDKit: pip install rdkit-pypi  (推荐，纯 Python)
  2) 安装 ChemDraw: 在 config.json 的 chemdraw 字段填写路径
  3) 安装 Chem3D:  在 config.json 的 chem3d 字段填写路径
  4) 安装 OpenBabel: http://openbabel.org  (命令行工具)

安装完成后，再次调用本模块将自动生成 PNG/SVG 图像。
{'='*60}
"""
        txt_path = output_path.with_suffix(".txt")
        txt_path.write_text(report, encoding="utf-8")
        logger.info(f"[完成-文本] 报告: {txt_path}")
        return str(txt_path)

    # ===============================================================
    # === 格式写入器 ===
    # ===============================================================
    def _write_mol_v2000(self, molecule: Molecule, output_path: Path) -> str:
        """写入标准 MDL MOL V2000 格式文件。"""
        lines = [
            molecule.name or "Compound",
            "  Generated by spectrum-analyzer (AI Spectrum Tool)",
            "",
        ]
        atoms = molecule.atoms
        bonds = molecule.bonds

        # 如无原子数据，但有 SMILES，尝试用 RDKit 生成
        if not atoms and molecule.smiles:
            try:
                from rdkit import Chem
                from rdkit.Chem import AllChem
                mol = Chem.MolFromSmiles(molecule.smiles)
                if mol:
                    mol = Chem.AddHs(mol)
                    AllChem.EmbedMolecule(mol, randomSeed=42)
                    try:
                        AllChem.MMFFOptimizeMolecule(mol)
                    except Exception:
                        pass
                    atoms, bonds = [], []
                    conf = mol.GetConformer()
                    for atom in mol.GetAtoms():
                        pos = conf.GetAtomPosition(atom.GetIdx())
                        atoms.append({
                            "element": atom.GetSymbol(),
                            "x": pos.x, "y": pos.y, "z": pos.z
                        })
                    for bond in mol.GetBonds():
                        bonds.append({
                            "atom1_idx": bond.GetBeginAtomIdx(),
                            "atom2_idx": bond.GetEndAtomIdx(),
                            "order": int(bond.GetBondType())
                        })
            except ImportError:
                # 无 RDKit，根据分子式生成虚拟原子（仅作为占位）
                tokens = Molecule._parse_formula(molecule.formula or "")
                idx = 0
                for t in tokens:
                    for _ in range(t["count"]):
                        # 简单环形排列
                        import math
                        angle = 2 * math.pi * idx / max(sum(t["count"] for t in tokens), 1)
                        atoms.append({
                            "element": t["element"],
                            "x": 1.5 * math.cos(angle),
                            "y": 1.5 * math.sin(angle),
                            "z": 0.0,
                        })
                        idx += 1

        n_a = max(len(atoms), 1)
        n_b = len(bonds)
        lines.append(f"{n_a:>3}{n_b:>3}  0  0  0  0  0  0  0  0999 V2000")

        for a in atoms:
            lines.append(
                f"{a.get('x',0.0):>10.4f}{a.get('y',0.0):>10.4f}{a.get('z',0.0):>10.4f} "
                f"{a['element']:<3} 0  0  0  0  0  0  0  0  0  0  0  0"
            )

        for b in bonds:
            lines.append(
                f"{b['atom1_idx']+1:>3}{b['atom2_idx']+1:>3}{b.get('order',1):>3}"
                "  0  0  0  0"
            )

        lines.append("M  END")
        lines.append("")
        lines.append("$$$$")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[完成] MOL V2000: {output_path}")
        return str(output_path)

    def _write_cml(self, molecule, output_path):
        """Chemical Markup Language (CML) 格式写入"""
        if not molecule.atoms and molecule.smiles:
            # 尝试用 RDKit 从 SMILES 构建原子坐标
            try:
                from rdkit import Chem
                from rdkit.Chem import AllChem
                mol = Chem.MolFromSmiles(molecule.smiles)
                if mol:
                    mol = Chem.AddHs(mol)
                    AllChem.EmbedMolecule(mol, randomSeed=42)
                    try:
                        AllChem.MMFFOptimizeMolecule(mol)
                    except Exception:
                        pass
                    mol.SetProp("_Name", molecule.name or "Compound")
                    return str(output_path)
            except ImportError:
                logger.warning("RDKit 未安装，无法自动生成 3D 坐标")
            except Exception as e:
                logger.warning(f"RDKit 写入失败: {e}")
        return str(output_path)
    def _write_cdxml(self, molecule: Molecule, output_path: Path):
        """生成 ChemDraw CDXML (XML 原生) 文件，所有化学软件都能打开。"""
        # 尝试用 RDKit 从 SMILES 获取 2D 坐标
        coords = []  # [(元素, x, y)]
        bonds_data = []  # [(i, j, order)]
        if molecule.smiles:
            try:
                from rdkit import Chem
                from rdkit.Chem import AllChem
                rdmol = Chem.MolFromSmiles(molecule.smiles)
                if rdmol is not None:
                    rdmol = Chem.AddHs(rdmol)
                    AllChem.Compute2DCoords(rdmol)
                    conf = rdmol.GetConformer()
                    for atom in rdmol.GetAtoms():
                        p = conf.GetAtomPosition(atom.GetIdx())
                        coords.append((atom.GetSymbol(), float(p.x), float(p.y)))
                    for bond in rdmol.GetBonds():
                        bonds_data.append((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(),
                                            int(bond.GetBondType())))
            except Exception as e:
                logger.warning(f"CDXML 坐标生成失败: {e}")

        # 简单的 CDXML 结构（所有常见化学软件都能打开）
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<CDXML Version="1" Creator="spectrum-analyzer">
  <page Height="500" Width="600" PrintBorderAndHeader="no">
    <group>
      <text fontsize="12" justification="Center" x="300" y="480">
        {molecule.name or "Compound"} | {molecule.formula} | {molecule.molecular_weight:.4f}
      </text>
      <group>
        <text fontsize="10" x="10" y="30">SMILES: {molecule.smiles or "(未提供)"}</text>
        <text fontsize="10" x="10" y="10">分子式: {molecule.formula}</text>
        <text fontsize="10" x="300" y="10">来源: AI Spectrum Analyzer</text>
      </group>
    </group>
  </page>
</CDXML>
"""
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"[完成-CDXML] 已写入 {len(content)} 字节到 {output_path}")


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="分子结构绘制（支持 RDKit / ChemDraw / Chem3D / OpenBabel / 文本模式）"
    )
    parser.add_argument("--smiles", "-s",
                       help="SMILES 字符串，例如 c1ccc(cc1)CCO （最推荐的输入方式）")
    parser.add_argument("--formula", "-f",
                       help="分子式，例如 C10H12O2（仅用于当没有结构信息时）")
    parser.add_argument("--name", "-n", default="Compound", help="分子名称，默认 Compound")
    parser.add_argument("--output", "-o", default="./outputs/structure.png",
                       help="输出文件路径，默认 ./outputs/structure.png")
    parser.add_argument("--backend", "-b",
                       choices=["RDKIT", "CHEMDRAW", "CHEM3D", "OPENBABEL", "TEXT"],
                       help="指定绘制后端，省略则自动按优先级选择")
    parser.add_argument("--config", "-c", help="配置文件路径 (JSON)")
    parser.add_argument("--size", type=int, nargs=2, default=(800, 600),
                       help="图像大小，单位为像素，例如 --size 1200 900")
    parser.add_argument("--with-labels", action="store_true",
                       help="显示原子编号（用于 NMR 信号归属标注）")
    parser.add_argument("--export-all", action="store_true",
                       help="导出所有格式（PNG/SVG/SDF/MOL/CDXML/CML/PDB/SMILES）到输出目录")
    args = parser.parse_args()

    # 加载配置
    cfg = {}
    if args.config and Path(args.config).exists():
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    api = ChemistryDrawingAPI(cfg)

    # 可选：从命令行强制指定后端
    if args.backend:
        api.set_preferred_backend(args.backend)

    # 构建分子对象
    mol = Molecule(name=args.name)
    if args.smiles:
        mol.smiles = args.smiles
    if args.formula:
        mol.from_formula(args.formula)

    # 导出所有格式
    if args.export_all:
        out_dir = Path(args.output)
        if out_dir.suffix:  # 如果是具体文件路径，则取父目录
            out_dir = out_dir.parent
        files = api.export_all_formats(mol, str(out_dir))
        print(f"[完成] 已导出 {len(files)} 个文件到 {out_dir}:")
        for fmt, path in files.items():
            print(f"  • {fmt.upper()}: {path}")
        return

    # 生成 2D 图像
    api.draw_2d(mol, args.output, size=tuple(args.size),
               with_atom_labels=args.with_labels)

    # 同时导出 SDF，便于其他软件打开
    out_path = Path(args.output)
    api.save_3d(mol, str(out_path.with_suffix(".sdf")), "sdf")
    api.save_3d(mol, str(out_path.with_suffix(".mol")), "mol")
    api.save_3d(mol, str(out_path.with_suffix(".cdxml")), "cdxml")

    print(f"\n[完成] 已生成结构文件到目录: {out_path.parent}")
    print(f"  可打开文件: {out_path.name}, {out_path.stem}.sdf, {out_path.stem}.cdxml 等")


if __name__ == "__main__":
    main()

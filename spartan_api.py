#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spartan_api.py — Spartan 软件接口模块（量子化学计算）

功能：
  1. 调用 Spartan 执行分子力学优化 (MMFF)
  2. 调用 Spartan 执行 DFT 几何优化 (B3LYP/6-31G*)
  3. NMR 化学位移预测 (GIAO 方法)
  4. ECD/ORD 圆二色谱计算 (TD-DFT)
  5. 构象搜索（蒙特卡洛/分子动力学）
  6. 生成 Spartan 输入文件 (.spinput)

工作流程模拟天然药物化学研究者：
  "建立结构 → 分子力学预优化 → DFT 精修 → 能量分析 → 与实验谱比对"
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
logger = logging.getLogger("spartan_api")


# ---------------------------------------------------------------------------
# 1. Spartan API 核心类
# ---------------------------------------------------------------------------

class SpartanAPI:
    """
    Spartan 量子化学计算软件接口

    支持：
      - 分子力学优化 (MMFF94, MM3)
      - 半经验方法 (AM1, PM3)
      - DFT (B3LYP, M06-2X, ωB97X-D 等)
      - ab initio (HF, MP2)
      - NMR 化学位移预测 (GIAO)
      - ECD/ORD 计算 (TD-DFT)
      - 构象搜索
    """

    CALCULATION_TYPES = {
        "energy": "单点能量计算",
        "geometry_optimization": "几何优化",
        "frequency": "频率计算（确认基态）",
        "nmr": "NMR 化学位移预测 (GIAO)",
        "ecd": "ECD 圆二色谱计算 (TD-DFT)",
        "ord": "ORD 旋光色散计算",
        "conformers": "构象搜索",
        "uv": "UV-Vis 光谱 (TD-DFT)",
        "ir": "红外光谱 (频率计算)",
    }

    METHODS = ["MMFF", "MM3", "AM1", "PM3", "HF", "B3LYP", "M062X", "wB97XD", "MP2"]
    BASIS_SETS = ["STO-3G", "3-21G", "6-31G", "6-31G*", "6-31G**", "6-31+G*", "6-311G**", "cc-pVDZ", "cc-pVTZ"]

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.exe_path = self.config.get("software_paths", {}).get("spartan", "")
        self.mode = self._detect_mode()
        logger.info(f"[信息] Spartan 运行模式: {self.mode}")
        logger.info(f"[信息] Spartan 路径: {self.exe_path or '(未配置)'}")

    # ------------------------------------------------------------------
    # 检测运行模式
    # ------------------------------------------------------------------

    def _detect_mode(self) -> str:
        if self.exe_path and Path(self.exe_path).exists():
            return "NATIVE"
        common_paths = [
            r"C:\Program Files\Wavefunction\Spartan18v114\spartan18-64.exe",
            r"C:\Program Files (x86)\Wavefunction\Spartan18v114\spartan18.exe",
            r"C:\Program Files\Wavefunction\Spartan\Spartan.exe",
            "/Applications/Spartan18.app/Contents/MacOS/spartan18",
        ]
        for p in common_paths:
            if Path(p).exists():
                self.exe_path = p
                return "NATIVE"
        return "SIMULATION"

    # ------------------------------------------------------------------
    # 生成 Spartan 输入文件 (.spinput)
    # ------------------------------------------------------------------

    def build_spinput(self, molecule_info: Dict, calculation_type: str = "geometry_optimization",
                       method: str = "B3LYP", basis_set: str = "6-31G*",
                       output_file: str = "molecule.spinput") -> str:
        """
        生成 Spartan 输入文件（.spinput 格式）

        参数:
          molecule_info: {'atoms': [{'element': 'C', 'x':.., 'y':.., 'z':..}], 'name': '..'}
          calculation_type: 计算类型
          method: 理论方法
          basis_set: 基组
        """
        lines = []
        lines.append("# Spartan 输入文件 — 由 spectrum-analyzer 生成")
        lines.append(f"# 任务: {self.CALCULATION_TYPES.get(calculation_type, calculation_type)}")
        lines.append(f"# 方法: {method}/{basis_set}")
        lines.append(f"# 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 任务定义
        lines.append("BEGIN")
        lines.append(f"  CALCULATION {calculation_type.upper()}")
        lines.append(f"  METHOD {method}")
        lines.append(f"  BASIS {basis_set}")
        lines.append("  SOLVATION NO")
        lines.append("  CHARGE 0")
        lines.append("  MULTIPLICITY 1")

        # 特殊选项
        if calculation_type == "nmr":
            lines.append("  NMR_METHOD GIAO")
        elif calculation_type == "ecd":
            lines.append("  TD_DFT")
            lines.append("  NSTATES 30")
            lines.append("  ECD_SPECTRUM")
        elif calculation_type == "conformers":
            lines.append("  CONFORMER_SEARCH MONTE_CARLO")
            lines.append("  NCONFORMERS 50")

        lines.append("END")
        lines.append("")

        # 分子结构
        name = molecule_info.get("name", "Molecule")
        lines.append(f"NAME {name}")
        lines.append("")

        # 原子坐标
        atoms = molecule_info.get("atoms", [])
        if atoms:
            lines.append(f"ATOMS {len(atoms)}")
            for i, atom in enumerate(atoms, 1):
                lines.append(
                    f"  {i:>4} {atom['element']:<3} {atom.get('x',0):>10.6f} "
                    f"{atom.get('y',0):>10.6f} {atom.get('z',0):>10.6f}"
                )
        else:
            # 使用 SMILES 构建（如果有）
            if "smiles" in molecule_info:
                lines.append(f"SMILES {molecule_info['smiles']}")
                lines.append("# 请在 Spartan 中导入 SMILES 以建立 3D 结构")

        lines.append("")
        lines.append("# EOF")

        # 保存文件
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[文件] 已生成 Spartan 输入: {out_path}")
        return str(out_path)

    # ------------------------------------------------------------------
    # 执行 Spartan 计算
    # ------------------------------------------------------------------

    def run_calculation(self, spinput_file: str, output_dir: Optional[str] = None,
                        timeout: int = 3600) -> Dict:
        """
        执行 Spartan 计算任务

        参数:
          spinput_file: .spinput 输入文件
          output_dir: 输出目录
          timeout: 超时时间（秒），默认 1 小时
        """
        input_path = Path(spinput_file)
        if not input_path.exists():
            raise FileNotFoundError(f"[错误] 未找到输入文件: {spinput_file}")

        output_dir = Path(output_dir or "./outputs")
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "input_file": str(input_path),
            "mode": self.mode,
            "status": "PENDING",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "output_files": [],
            "energies": {},
            "properties": {},
        }

        if self.mode == "NATIVE":
            try:
                # 调用 Spartan (无界面模式)
                cmd = [str(self.exe_path), "--batch", str(input_path), "--output", str(output_dir)]
                logger.info(f"[执行] {' '.join(cmd)}")
                logger.info(f"[信息] 预计计算时间：小分子 ~ 数分钟到数小时")

                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                result["status"] = "SUCCESS" if proc.returncode == 0 else "FAILED"
                result["return_code"] = proc.returncode
                result["stdout"] = proc.stdout[:2000]
                result["stderr"] = proc.stderr[:2000]

                # 收集输出文件
                for f in output_dir.glob("*"):
                    if f.is_file() and f.suffix in (".sp", ".out", ".log", ".txt", ".jdx", ".csv"):
                        result["output_files"].append(str(f))

            except subprocess.TimeoutExpired:
                result["status"] = "TIMEOUT"
                logger.warning(f"[警告] 计算超时 (> {timeout}s)，请手动检查")
            except Exception as e:
                result["status"] = "ERROR"
                result["error"] = str(e)
                logger.error(f"[错误] 执行异常: {e}")
        else:
            # 模拟模式
            result["status"] = "SIMULATED"
            result["energies"] = {
                "MMFF_energy_kcal_mol": -45.2,
                "DFT_energy_Hartree": -235.48267,
                "HOMO_eV": -7.21,
                "LUMO_eV": -1.85,
                "dipole_moment_D": 1.85,
            }
            result["properties"] = {
                "molecular_weight": molecule_weight_from_file(spinput_file),
                "n_atoms": "from input file",
                "calculation_type": "(从 .spinput 文件解析)",
            }
            logger.info(f"[模拟] 已完成模拟计算，实际结果请使用本地 Spartan")

        result["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return result

    # ------------------------------------------------------------------
    # 便捷方法：几何优化
    # ------------------------------------------------------------------

    def optimize_geometry(self, molecule_info: Dict, method: str = "MMFF",
                           output_dir: Optional[str] = None) -> Dict:
        """执行几何优化（默认先跑 MMFF 分子力学）"""
        output_dir = Path(output_dir or "./outputs")
        spinput = self.build_spinput(
            molecule_info,
            calculation_type="geometry_optimization",
            method=method,
            basis_set="6-31G*",
            output_file=str(output_dir / f"{molecule_info.get('name','mol')}_opt.spinput"),
        )
        return self.run_calculation(spinput, str(output_dir))

    # ------------------------------------------------------------------
    # 便捷方法：NMR 化学位移预测
    # ------------------------------------------------------------------

    def predict_nmr_shifts(self, molecule_info: Dict, method: str = "B3LYP",
                            basis_set: str = "6-31G*", output_dir: Optional[str] = None) -> Dict:
        """预测 NMR 化学位移（GIAO 方法）"""
        output_dir = Path(output_dir or "./outputs")
        spinput = self.build_spinput(
            molecule_info,
            calculation_type="nmr",
            method=method,
            basis_set=basis_set,
            output_file=str(output_dir / f"{molecule_info.get('name','mol')}_nmr.spinput"),
        )
        return self.run_calculation(spinput, str(output_dir), timeout=7200)

    # ------------------------------------------------------------------
    # 便捷方法：ECD 光谱计算
    # ------------------------------------------------------------------

    def calculate_ecd(self, molecule_info: Dict, method: str = "B3LYP",
                       basis_set: str = "6-31G*", n_states: int = 30,
                       output_dir: Optional[str] = None) -> Dict:
        """使用 TD-DFT 计算 ECD 光谱"""
        molecule_info_cp = dict(molecule_info)
        molecule_info_cp["_n_states"] = n_states
        output_dir = Path(output_dir or "./outputs")
        spinput = self.build_spinput(
            molecule_info_cp,
            calculation_type="ecd",
            method=method,
            basis_set=basis_set,
            output_file=str(output_dir / f"{molecule_info_cp.get('name','mol')}_ecd.spinput"),
        )
        return self.run_calculation(spinput, str(output_dir), timeout=10800)

    # ------------------------------------------------------------------
    # 解析 Spartan 输出文件（NMR 结果）
    # ------------------------------------------------------------------

    def parse_nmr_output(self, output_file: str) -> Dict:
        """解析 Spartan 输出的 NMR 化学位移结果"""
        path = Path(output_file)
        result = {
            "filename": path.name,
            "c_shifts": [],  # ¹³C NMR
            "h_shifts": [],  # ¹H NMR
        }

        if not path.exists():
            return result

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # 解析 NMR 位移数据（Spartan 输出包含专门的 NMR 表格）
            # 这是一个简化的解析器，实际 Spartan 输出格式需要针对性调整
            in_nmr_section = False
            for line in content.splitlines():
                line_lower = line.lower().strip()
                if "nmr" in line_lower and "chemical" in line_lower:
                    in_nmr_section = True
                    continue
                if in_nmr_section:
                    # 尝试匹配: <原子号> <元素> <位移>
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            atom_num = int(parts[0])
                            element = parts[1].strip().upper()
                            shift = float(parts[2])
                            if element == "C":
                                result["c_shifts"].append({"atom": atom_num, "shift_ppm": shift})
                            elif element == "H":
                                result["h_shifts"].append({"atom": atom_num, "shift_ppm": shift})
                        except ValueError:
                            continue
        except Exception as e:
            logger.warning(f"[警告] 解析 NMR 输出失败: {e}")

        return result


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def molecule_weight_from_file(filename: str) -> float:
    """简单的分子量估算（模拟模式使用）"""
    return 0.0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Spartan 量子化学计算接口")
    parser.add_argument("action", choices=["build", "run", "optimize", "nmr", "ecd"],
                        help="操作类型")
    parser.add_argument("--smiles", help="分子 SMILES 字符串")
    parser.add_argument("--molfile", help="分子结构文件 (.mol/.sdf)")
    parser.add_argument("--method", default="B3LYP", help="理论方法")
    parser.add_argument("--basis", default="6-31G*", help="基组")
    parser.add_argument("--input", help=".spinput 文件路径 (用于 run)")
    parser.add_argument("--output", "-o", default="./outputs", help="输出目录")
    parser.add_argument("--config", "-c", help="配置文件路径")
    args = parser.parse_args()

    cfg = {}
    if args.config and Path(args.config).exists():
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    api = SpartanAPI(cfg)

    # 构造分子信息
    molecule_info = {"name": "Molecule"}
    if args.smiles:
        molecule_info["smiles"] = args.smiles
    elif args.molfile and Path(args.molfile).exists():
        molecule_info["molfile"] = args.molfile

    if args.action == "build":
        spinput = api.build_spinput(molecule_info, "geometry_optimization",
                                    args.method, args.basis,
                                    str(Path(args.output) / "input.spinput"))
        print(f"[完成] 已生成: {spinput}")

    elif args.action == "run" and args.input:
        result = api.run_calculation(args.input, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "optimize":
        result = api.optimize_geometry(molecule_info, args.method, args.output)
        print(f"[完成] 状态: {result['status']}")
        print(f"       输出文件数: {len(result['output_files'])}")

    elif args.action == "nmr":
        result = api.predict_nmr_shifts(molecule_info, args.method, args.basis, args.output)
        print(f"[完成] 状态: {result['status']}")

    elif args.action == "ecd":
        result = api.calculate_ecd(molecule_info, args.method, args.basis, 30, args.output)
        print(f"[完成] 状态: {result['status']}")


if __name__ == "__main__":
    main()

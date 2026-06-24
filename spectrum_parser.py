#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spectrum_parser.py — 谱图数据类型识别与解析模块

功能：
  1. 自动识别谱图数据类型（NMR / IR / MS / UV / ECD / ORD）
  2. 自动检测文件格式（.mnova / .jdx / .csv / .txt / .sp）
  3. 提取关键数据特征（化学位移、峰位、m/z、波数等）

工作流程模拟天然药物化学研究者：
  "拿到谱图 → 先判断是什么谱 → 看关键信号 → 记录数据"
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("spectrum_parser")


# ---------------------------------------------------------------------------
# 1. 谱图类型枚举
# ---------------------------------------------------------------------------

SPECTRUM_TYPES = {
    "1H_NMR": {
        "name": "¹H-NMR (氢谱)",
        "description": "一维氢核磁共振谱",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 14),
    },
    "13C_NMR": {
        "name": "¹³C-NMR (碳谱)",
        "description": "一维碳核磁共振谱",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 220),
    },
    "DEPT_90": {
        "name": "DEPT-90",
        "description": "无畸变极化转移增强-90°，只显示 CH",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 220),
    },
    "DEPT_135": {
        "name": "DEPT-135",
        "description": "无畸变极化转移增强-135°，CH/CH₃正峰，CH₂倒峰",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 220),
    },
    "COSY": {
        "name": "COSY (同核化学位移相关谱)",
        "description": "二维 ¹H-¹H 相关谱",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 14),
    },
    "HMBC": {
        "name": "HMBC (异核多键相关谱)",
        "description": "二维 ¹H-¹³C 远程相关谱（2-3J）",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 220),
    },
    "HMQC": {
        "name": "HMQC/HSQC (异核单量子相关谱)",
        "description": "二维 ¹H-¹³C 直接相关谱（¹J）",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 220),
    },
    "NOESY": {
        "name": "NOESY (核 Overhauser 效应谱)",
        "description": "二维空间邻近氢相关谱",
        "x_axis": "化学位移 δ (ppm)",
        "x_range": (0, 14),
    },
    "MS": {
        "name": "MS (质谱)",
        "description": "低分辨质谱",
        "x_axis": "m/z",
        "x_range": (0, 2000),
    },
    "HRMS": {
        "name": "HRMS (高分辨质谱)",
        "description": "高分辨质谱，用于精确分子式确定",
        "x_axis": "m/z (精确质量)",
        "x_range": (0, 2000),
    },
    "IR": {
        "name": "IR (红外光谱)",
        "description": "傅里叶变换红外光谱",
        "x_axis": "波数 (cm⁻¹)",
        "x_range": (400, 4000),
    },
    "UV": {
        "name": "UV-Vis (紫外-可见光谱)",
        "description": "紫外-可见吸收光谱",
        "x_axis": "波长 (nm)",
        "x_range": (200, 800),
    },
    "ECD": {
        "name": "ECD (电子圆二色谱)",
        "description": "电子圆二色谱，用于绝对构型确定",
        "x_axis": "波长 (nm)",
        "x_range": (200, 400),
    },
    "ORD": {
        "name": "ORD (旋光色散谱)",
        "description": "旋光色散谱",
        "x_axis": "波长 (nm)",
        "x_range": (200, 800),
    },
}


# ---------------------------------------------------------------------------
# 2. 文件格式与类型识别
# ---------------------------------------------------------------------------

FILE_EXT_MAP = {
    ".mnova":   "MNOVA",      # Mestrenova 原生格式
    ".mnova2":  "MNOVA",
    ".jdx":     "JCAMP",      # JCAMP-DX 标准格式
    ".dx":      "JCAMP",
    ".csv":     "CSV",        # 逗号分隔值
    ".txt":     "TXT",        # 纯文本（峰值表或原始数据）
    ".sp":      "SPARTAN",    # Spartan 文件
    ".spinput": "SPARTAN",
    ".spartan": "SPARTAN",
    ".mol":     "MOL",        # MOL 格式结构
    ".sdf":     "SDF",        # SDF 格式结构
    ".cml":     "CML",        # Chemical Markup Language
}


class SpectrumParser:
    """谱图解析器核心类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.results = {
            "files": [],
            "detected_types": [],
            "extracted_data": {},
        }

    # ------------------------------------------------------------------
    # 主入口：解析一个文件或目录
    # ------------------------------------------------------------------

    def parse(self, input_path: str) -> Dict:
        """解析谱图数据文件或目录"""
        path = Path(input_path)

        if not path.exists():
            raise FileNotFoundError(f"[ERROR] 未找到文件或目录: {input_path}")

        if path.is_dir():
            files = self._collect_files(path)
            logger.info(f"[信息] 在目录中发现 {len(files)} 个文件")
        else:
            files = [path]

        for f in files:
            try:
                result = self._parse_single_file(f)
                self.results["files"].append(result)
                if result["spectrum_type"]:
                    self.results["detected_types"].append(result["spectrum_type"])
                self.results["extracted_data"][result["spectrum_type"] or f.name] = result.get("data", {})
            except Exception as e:
                logger.error(f"[错误] 解析 {f.name} 失败: {e}")
                self.results["files"].append({
                    "filename": f.name,
                    "error": str(e),
                })

        self.results["detected_types"] = list(set(self.results["detected_types"]))
        return self.results

    # ------------------------------------------------------------------
    # 辅助：收集目录中的文件
    # ------------------------------------------------------------------

    def _collect_files(self, dir_path: Path) -> List[Path]:
        supported = set(FILE_EXT_MAP.keys()) | {".png", ".jpg", ".jpeg"}
        files = []
        for f in sorted(dir_path.iterdir()):
            if f.is_file() and f.suffix.lower() in supported:
                files.append(f)
        return files

    # ------------------------------------------------------------------
    # 解析单个文件
    # ------------------------------------------------------------------

    def _parse_single_file(self, filepath: Path) -> Dict:
        ext = filepath.suffix.lower()
        file_format = FILE_EXT_MAP.get(ext, "UNKNOWN")

        logger.info(f"[解析] {filepath.name} (格式: {file_format})")

        result = {
            "filename": filepath.name,
            "file_format": file_format,
            "spectrum_type": None,
            "data": {},
        }

        if file_format == "MNOVA":
            # Mestrenova 文件需要通过 mestrenova_api 处理
            result["spectrum_type"] = self._detect_spectrum_type_from_name(filepath.name)
            result["data"] = {"note": "需要调用 Mestrenova API 进一步解析"}
        elif file_format == "JCAMP":
            result.update(self._parse_jcamp(filepath))
        elif file_format in ("CSV", "TXT"):
            result.update(self._parse_text(filepath))
        elif file_format == "SPARTAN":
            result["spectrum_type"] = self._detect_spectrum_type_from_name(filepath.name)
            result["data"] = {"note": "Spartan 格式，需要调用 Spartan API"}
        else:
            # 尝试文本方式读取
            try:
                result.update(self._parse_text(filepath))
            except Exception:
                result["spectrum_type"] = None
                result["data"] = {"error": "无法解析此文件格式"}

        return result

    # ------------------------------------------------------------------
    # 从文件名推测谱图类型
    # ------------------------------------------------------------------

    def _detect_spectrum_type_from_name(self, filename: str) -> Optional[str]:
        name_lower = filename.lower()
        patterns = [
            ("1h", "1H_NMR"),
            ("hnmr", "1H_NMR"),
            ("proton", "1H_NMR"),
            ("氢谱", "1H_NMR"),
            ("13c", "13C_NMR"),
            ("cnmr", "13C_NMR"),
            ("碳谱", "13C_NMR"),
            ("dept90", "DEPT_90"),
            ("dept-90", "DEPT_90"),
            ("dept_90", "DEPT_90"),
            ("dept135", "DEPT_135"),
            ("dept-135", "DEPT_135"),
            ("dept_135", "DEPT_135"),
            ("dept", "DEPT_135"),
            ("cosy", "COSY"),
            ("hmbc", "HMBC"),
            ("hmqc", "HMQC"),
            ("hsqc", "HMQC"),
            ("noesy", "NOESY"),
            ("roesy", "NOESY"),
            ("hrms", "HRMS"),
            ("high.*res", "HRMS"),
            ("ms", "MS"),
            ("质谱", "MS"),
            ("ir", "IR"),
            ("ftir", "IR"),
            ("红外", "IR"),
            ("uv", "UV"),
            ("紫外", "UV"),
            ("ecd", "ECD"),
            ("circular", "ECD"),
            ("圆二色", "ECD"),
            ("ord", "ORD"),
            ("旋光", "ORD"),
        ]
        for pattern, stype in patterns:
            if re.search(pattern, name_lower):
                return stype
        return None

    # ------------------------------------------------------------------
    # 解析 JCAMP-DX 格式
    # ------------------------------------------------------------------

    def _parse_jcamp(self, filepath: Path) -> Dict:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 提取元数据
        title = re.search(r"##TITLE=\s*(.+?)\n", content, re.IGNORECASE)
        data_type = re.search(r"##DATATYPE=\s*(.+?)\n", content, re.IGNORECASE)
        xunits = re.search(r"##XUNITS=\s*(.+?)\n", content, re.IGNORECASE)
        yunits = re.search(r"##YUNITS=\s*(.+?)\n", content, re.IGNORECASE)
        firstx = re.search(r"##FIRSTX=\s*([\-\d\.]+)", content, re.IGNORECASE)
        lastx = re.search(r"##LASTX=\s*([\-\d\.]+)", content, re.IGNORECASE)
        npoints = re.search(r"##NPOINTS=\s*(\d+)", content, re.IGNORECASE)

        # 提取 ASCII 数据块
        data_match = re.search(r"##XYDATA=\s*\(.+?\)\n(.+?)##END", content, re.DOTALL | re.IGNORECASE)
        raw_data = []
        if data_match:
            data_block = data_match.group(1)
            for line in data_block.strip().splitlines():
                if line.startswith("##"):
                    continue
                parts = re.findall(r"[\-+]?\d*\.?\d+[eEdD][\-+]?\d+|[\-+]?\d+\.\d+|[\-+]?\d+", line)
                if parts:
                    raw_data.extend([float(x) for x in parts])

        # 自动识别谱图类型（根据 X 轴单位 + 范围）
        spectrum_type = None
        xunits_str = (xunits.group(1) if xunits else "").lower()
        if firstx and lastx:
            try:
                x1, x2 = float(firstx.group(1)), float(lastx.group(1))
                xrange = sorted([x1, x2])
                if "ppm" in xunits_str or (0 <= xrange[0] and xrange[1] <= 250):
                    if xrange[1] <= 16:
                        spectrum_type = "1H_NMR"
                    elif xrange[1] <= 230:
                        spectrum_type = "13C_NMR"
                elif "1/cm" in xunits_str or "cm-1" in xunits_str or "cm⁻¹" in xunits_str:
                    spectrum_type = "IR"
                elif "nm" in xunits_str:
                    spectrum_type = "UV"
                elif "m/z" in xunits_str or "mass" in xunits_str or "amu" in xunits_str:
                    spectrum_type = "MS"
            except ValueError:
                pass

        # 数据点重构
        peaks = []
        if raw_data and firstx and lastx and npoints:
            try:
                n = int(npoints.group(1))
                x0, xN = float(firstx.group(1)), float(lastx.group(1))
                step = (xN - x0) / (n - 1) if n > 1 else 0
                # 简化：只提取峰值（局部极大值）
                threshold = max(raw_data) * 0.05
                for i, v in enumerate(raw_data):
                    if v > threshold:
                        x = x0 + i * step
                        peaks.append({"x": round(x, 4), "y": round(v, 4)})
                # 如果峰过多，只保留前 50 个
                peaks = sorted(peaks, key=lambda p: -p["y"])[:50]
                peaks = sorted(peaks, key=lambda p: p["x"])
            except ValueError:
                pass

        return {
            "spectrum_type": spectrum_type,
            "data": {
                "title": title.group(1).strip() if title else None,
                "data_type": data_type.group(1).strip() if data_type else None,
                "x_units": xunits_str,
                "y_units": yunits.group(1).strip() if yunits else None,
                "x_range": (float(firstx.group(1)), float(lastx.group(1))) if firstx and lastx else None,
                "n_points": int(npoints.group(1)) if npoints else None,
                "peaks": peaks,
                "n_peaks": len(peaks),
            },
        }

    # ------------------------------------------------------------------
    # 解析 CSV / TXT / 文本格式
    # ------------------------------------------------------------------

    def _parse_text(self, filepath: Path) -> Dict:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()

        # 尝试从内容头部识别类型
        spectrum_type = self._detect_spectrum_type_from_name(filepath.name)
        if spectrum_type is None:
            # 从内容特征识别
            header_preview = "\n".join(lines[:20]).lower()
            if "m/z" in header_preview or "mass" in header_preview or "精确质量" in header_preview or "molecular ion" in header_preview:
                spectrum_type = "HRMS" if "high" in header_preview or "精确" in header_preview else "MS"
            elif "ppm" in header_preview or "chemical shift" in header_preview or "化学位移" in header_preview:
                spectrum_type = "1H_NMR"  # 默认氢谱
            elif "cm-1" in header_preview or "cm⁻¹" in header_preview or "wavenumber" in header_preview or "波数" in header_preview:
                spectrum_type = "IR"
            elif "nm" in header_preview and ("absorbance" in header_preview or "abs" in header_preview or "吸收" in header_preview):
                spectrum_type = "UV"
            elif "nm" in header_preview and ("cd" in header_preview or "mdeg" in header_preview or "circular" in header_preview):
                spectrum_type = "ECD"

        # 解析表格数据（支持 CSV / TSV / 空格分隔）
        peaks = []
        nmr_signals = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith(("#", "//", ";", "%")):
                continue
            # 尝试匹配数字行
            nums = re.findall(r"[\-+]?\d+\.?\d*", line)
            if len(nums) >= 2:
                try:
                    x, y = float(nums[0]), float(nums[1])
                    peaks.append({"x": x, "y": y})
                except ValueError:
                    pass
            elif len(nums) == 1 and spectrum_type in ("1H_NMR", "13C_NMR"):
                # NMR 峰值列表（只有化学位移）
                try:
                    nmr_signals.append(float(nums[0]))
                except ValueError:
                    pass

        data = {
            "content_preview": "\n".join(lines[:10]),
            "n_lines": len(lines),
            "peaks": peaks,
            "nmr_signals": nmr_signals,
            "n_peaks": len(peaks) + len(nmr_signals),
        }

        return {
            "spectrum_type": spectrum_type,
            "data": data,
        }

    # ------------------------------------------------------------------
    # 打印摘要
    # ------------------------------------------------------------------

    def summary(self) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("  谱图数据解析摘要")
        lines.append("=" * 60)
        lines.append(f"检测到的谱图类型: {', '.join(self.results['detected_types']) or '未识别'}")
        lines.append(f"已处理文件数: {len(self.results['files'])}")
        lines.append("")
        for f in self.results["files"]:
            lines.append(f"  - {f['filename']}")
            lines.append(f"    类型: {f.get('spectrum_type', '未识别')}")
            if "error" in f:
                lines.append(f"    错误: {f['error']}")
            else:
                d = f.get("data", {})
                if "n_peaks" in d:
                    lines.append(f"    提取数据点: {d['n_peaks']} 个峰")
                if "nmr_signals" in d and d["nmr_signals"]:
                    lines.append(f"    NMR 信号: {d['nmr_signals'][:10]}..." if len(d["nmr_signals"]) > 10 else f"    NMR 信号: {d['nmr_signals']}")
        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="谱图数据识别与解析工具")
    parser.add_argument("input", help="输入文件或目录路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    parser.add_argument("--output", "-o", help="输出结果到指定文件")
    args = parser.parse_args()

    sp = SpectrumParser()
    results = sp.parse(args.input)

    if args.json:
        output = json.dumps(results, ensure_ascii=False, indent=2)
    else:
        output = sp.summary()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info(f"结果已保存到: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()

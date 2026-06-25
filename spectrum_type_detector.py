#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spectrum_type_detector.py — 谱图类型自动识别模块

功能：
  - 根据文件扩展名、内容自动识别谱图类型
  - 支持 NMR (1D/2D), MS, IR, UV-Vis, CD, X-ray 等

支持的格式：
  - .mnova        → Mestrenova 项目文件
  - .mzML, .mzXML → 质谱 (Mass Spectrometry)
  - .raw          → 质谱 (Thermo, Waters, Agilent)
  - .dta          → 质谱 (Agilent)
  - .mgf          → 质谱 (Mascot Generic Format)
  - .jdx, .dx, .jcm→ JCAMP-DX (IR, UV, NMR)
  - .csv, .txt    → 通用文本数据
  - .xy, .xye     → X-Y 数据
  - .cif          → 晶体结构 (X-ray)
  - .pdb          → 蛋白质结构
"""

import os
import re
import json
import zipfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("spectrum_detector")


class SpectrumType(Enum):
    """谱图主类型"""
    NMR_1H = "1H-NMR"           # 1D 1H NMR
    NMR_13C = "13C-NMR"          # 1D 13C NMR
    NMR_19F = "19F-NMR"          # 1D 19F NMR
    NMR_31P = "31P-NMR"          # 1D 31P NMR
    NMR_2D = "2D-NMR"            # 2D NMR (COSY, HSQC, HMBC, NOESY...)
    MS_LOW_RES = "MS-LowRes"     # 低分辨质谱
    MS_HIGHRES = "MS-HighRes"    # 高分辨质谱 (HRMS)
    IR = "IR"                    # 红外光谱
    UV_VIS = "UV-Vis"            # 紫外-可见光谱
    CD = "CD"                    # 圆二色谱
    XRAY_CIF = "X-ray-CIF"       # X 射线晶体学
    HPLC_CHROMATOGRAM = "HPLC"   # 液相色谱
    GC_CHROMATOGRAM = "GC"       # 气相色谱
    UNKNOWN = "Unknown"


class NMRSpectrumType(Enum):
    """NMR 谱图子类型（2D 用）"""
    COSY = "COSY"
    HSQC = "HSQC"
    HMBC = "HMBC"
    NOESY = "NOESY"
    ROESY = "ROESY"
    TOCSY = "TOCSY"
    INADEQUATE = "INADEQUATE"
    UNKNOWN_2D = "Unknown-2D"


@dataclass
class SpectrumMetadata:
    """谱图元数据"""
    spectrum_type: SpectrumType
    file_format: str                       # 文件格式
    confidence: float                       # 识别置信度 (0-1)
    sub_type: Optional[str] = None          # 子类型（2D NMR 类型等）
    nucleus: Optional[str] = None          # 核类型
    solvent: Optional[str] = None           # 溶剂
    notes: List[str] = field(default_factory=list)
    raw_info: Dict[str, Any] = field(default_factory=dict)


class SpectrumTypeDetector:
    """谱图类型自动识别器"""

    # 文件扩展名到谱图类型的映射
    EXTENSION_MAP = {
        # 质谱
        ".mzml": (SpectrumType.MS_LOW_RES, "mzML"),
        ".mzxml": (SpectrumType.MS_LOW_RES, "mzXML"),
        ".raw": (SpectrumType.MS_LOW_RES, "RAW"),
        ".dta": (SpectrumType.MS_LOW_RES, "DTA"),
        ".mgf": (SpectrumType.MS_LOW_RES, "MGF"),
        ".ms": (SpectrumType.MS_LOW_RES, "MS"),
        # JCAMP-DX (可能包含 IR, UV, NMR)
        ".jdx": (None, "JCAMP-DX"),
        ".dx": (None, "JCAMP-DX"),
        ".jcm": (None, "JCAMP-DX"),
        # 文本
        ".csv": (None, "CSV"),
        ".txt": (None, "TXT"),
        ".xy": (None, "XY"),
        ".xye": (None, "XY"),
        ".asc": (None, "ASCII"),
        # 晶体学
        ".cif": (SpectrumType.XRAY_CIF, "CIF"),
        # Mestrenova
        ".mnova": (None, "MestReNova"),
    }

    # Mestrenova 内部存储格式（XML）
    MNOVA_INDICATORS = [
        "<?xml",
        "MestReNova",
        "mestrenova",
        "nmrSpectrum",
        "spectraData",
    ]

    # 2D NMR 关键词（注意：2D 类型之间通过优先级区分）
    NMRI_2D_KEYWORDS = [
        "HMBC",      # 优先级最高（最特异）
        "HSQC",      # 优先级次之
        "NOESY",     # 立体化学
        "ROESY",
        "TOCSY",
        "COSY",      # 通用
        "INADEQUATE",
        "HETCOR",
        "JRES",
    ]

    # 1D NMR 核类型
    NMR_NUCLEI = ["1H", "13C", "19F", "31P", "15N", "29Si"]

    def __init__(self):
        self.logger = logging.getLogger("spectrum_detector")

    def detect(self, filepath: str) -> SpectrumMetadata:
        """
        自动识别谱图类型

        Args:
            filepath: 谱图文件路径

        Returns:
            SpectrumMetadata 对象
        """
        if not os.path.exists(filepath):
            return SpectrumMetadata(
                spectrum_type=SpectrumType.UNKNOWN,
                file_format="N/A",
                confidence=0.0,
                notes=[f"文件不存在: {filepath}"]
            )

        path = Path(filepath)
        ext = path.suffix.lower()
        file_size = path.stat().st_size

        metadata = SpectrumMetadata(
            spectrum_type=SpectrumType.UNKNOWN,
            file_format=ext or "no_extension",
            confidence=0.0,
        )

        # Step 1: 根据扩展名初步判断
        ext_type, ext_format = self.EXTENSION_MAP.get(ext, (None, ext or "unknown"))

        # Step 2: 对于模糊类型，读取文件内容进一步判断
        try:
            content_sample = self._read_sample(filepath, max_bytes=4096)
        except Exception as e:
            self.logger.warning(f"读取文件失败: {e}")
            content_sample = b""

        # Step 3: 各种类型的判断
        if ext == ".mnova":
            metadata = self._detect_mnova(filepath, content_sample, file_size)
        elif ext in [".mzml", ".mzxml", ".raw", ".dta", ".mgf", ".ms"]:
            metadata = self._detect_mass_spec(filepath, ext_format)
        elif ext in [".jdx", ".dx", ".jcm"]:
            metadata = self._detect_jcamp(filepath, content_sample)
        elif ext in [".csv", ".txt", ".xy", ".xye", ".asc"]:
            metadata = self._detect_text_spectrum(filepath, content_sample)
        elif ext == ".cif":
            metadata.spectrum_type = SpectrumType.XRAY_CIF
            metadata.confidence = 0.95
            metadata.notes.append("X 射线晶体学 CIF 文件")
        else:
            # 尝试根据内容判断
            metadata = self._detect_by_content(filepath, content_sample)

        # Step 4: 文件大小提示
        if file_size > 100 * 1024 * 1024:  # > 100MB
            metadata.notes.append(f"大文件 ({file_size / 1024 / 1024:.1f} MB)，可能为高分辨质谱或 2D NMR")

        return metadata

    def _read_sample(self, filepath: str, max_bytes: int = 4096) -> bytes:
        """读取文件前 N 字节"""
        try:
            with open(filepath, "rb") as f:
                return f.read(max_bytes)
        except Exception:
            return b""

    def _detect_mnova(self, filepath: str, content: bytes, file_size: int) -> SpectrumMetadata:
        """检测 Mestrenova 文件"""
        metadata = SpectrumMetadata(
            spectrum_type=SpectrumType.NMR_1H,  # 默认为 1H NMR
            file_format="MestReNova",
            confidence=0.5,
            notes=[],
        )

        # 从文件名获取额外提示
        filename = Path(filepath).stem.upper()
        filename_hints = {
            "COSY": "COSY", "HSQC": "HSQC", "HMBC": "HMBC",
            "NOESY": "NOESY", "ROESY": "ROESY", "TOCSY": "TOCSY"
        }
        filename_2d_type = None
        for keyword, type_name in filename_hints.items():
            if keyword in filename:
                filename_2d_type = type_name
                break

        # Mestrenova 15+ 的文件可能是 ZIP 格式
        is_zip = False
        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                is_zip = True
                namelist = zf.namelist()
                # 尝试解析 XML 文件
                xml_files = [n for n in namelist if n.endswith(".xml") or n.endswith(".json")]
                metadata.raw_info["zip_files"] = namelist[:20]  # 前 20 个文件

                for xml_name in xml_files[:5]:
                    try:
                        with zf.open(xml_name) as f:
                            xml_content = f.read(8192).decode("utf-8", errors="ignore")
                            # 寻找 2D NMR 关键词
                            for keyword in self.NMRI_2D_KEYWORDS:
                                if keyword in xml_content:
                                    metadata.spectrum_type = SpectrumType.NMR_2D
                                    metadata.sub_type = keyword
                                    metadata.confidence = 0.95
                                    metadata.notes.append(f"检测到 2D NMR 类型: {keyword}")
                                    return metadata
                            break
                    except Exception:
                        continue
        except zipfile.BadZipFile:
            # 不是 ZIP，Mestrenova 15 的 mnova 是自定义二进制格式
            is_zip = False

        # 读取大块数据并尝试多种编码解析（Mestrenova 用 UTF-16 LE）
        try:
            with open(filepath, "rb") as f:
                # 大文件可能需要全读 - 至少 50MB
                raw_data = f.read(min(100 * 1024 * 1024, file_size))

            # 尝试 UTF-16 LE 解码（Mestrenova 15 默认）
            text_utf16 = raw_data.decode("utf-16-le", errors="ignore")

            # 寻找 2D NMR 关键词（按优先级）
            content_2d_type = None
            for keyword in self.NMRI_2D_KEYWORDS:
                if keyword in text_utf16:
                    content_2d_type = keyword
                    break

            # 如果文件名明确指定了 2D 类型，优先使用文件名
            # （因为文件内容可能包含多个谱图信息，但文件名是用户意图）
            if filename_2d_type:
                metadata.spectrum_type = SpectrumType.NMR_2D
                metadata.sub_type = filename_2d_type
                metadata.confidence = 0.95
                metadata.notes.append(f"从文件名识别 2D NMR: {filename_2d_type}")
                if content_2d_type and content_2d_type != filename_2d_type:
                    metadata.notes.append(f"文件内容也包含 2D 类型: {content_2d_type}")
                return metadata

            # 否则使用内容检测到的 2D 类型
            if content_2d_type:
                metadata.spectrum_type = SpectrumType.NMR_2D
                metadata.sub_type = content_2d_type
                metadata.confidence = 0.85
                metadata.notes.append(f"检测到 2D NMR: {content_2d_type}")
                return metadata

            # 文件名包含 1H/13C/19F 提示
            nuclei_filename = {
                "1H": "1H", "13C": "13C", "19F": "19F", "31P": "31P",
                "PROTON": "1H", "CARBON": "13C"
            }
            for kw, nucleus in nuclei_filename.items():
                if kw in filename:
                    if nucleus == "1H":
                        metadata.spectrum_type = SpectrumType.NMR_1H
                    elif nucleus == "13C":
                        metadata.spectrum_type = SpectrumType.NMR_13C
                    elif nucleus == "19F":
                        metadata.spectrum_type = SpectrumType.NMR_19F
                    elif nucleus == "31P":
                        metadata.spectrum_type = SpectrumType.NMR_31P
                    metadata.nucleus = nucleus
                    metadata.confidence = 0.8
                    metadata.notes.append(f"从文件名推断核类型: {nucleus}")
                    return metadata

            # 寻找核类型
            for nucleus in self.NMR_NUCLEI:
                if nucleus in text_utf16:
                    if nucleus == "1H":
                        metadata.spectrum_type = SpectrumType.NMR_1H
                    elif nucleus == "13C":
                        metadata.spectrum_type = SpectrumType.NMR_13C
                    elif nucleus == "19F":
                        metadata.spectrum_type = SpectrumType.NMR_19F
                    elif nucleus == "31P":
                        metadata.spectrum_type = SpectrumType.NMR_31P
                    metadata.nucleus = nucleus
                    metadata.confidence = 0.85
                    metadata.notes.append(f"核类型: {nucleus}")

            # 寻找溶剂
            solvents = ["CDCl3", "DMSO-d6", "CD3OD", "D2O", "acetone-d6", "C6D6", "CD2Cl2", "THF-d8"]
            for solvent in solvents:
                if solvent in text_utf16:
                    metadata.solvent = solvent
                    metadata.notes.append(f"溶剂: {solvent}")
                    break

            # 寻找 2D 特征关键词
            if "2D" in text_utf16 or "two-dimensional" in text_utf16.lower():
                if metadata.confidence < 0.7:
                    metadata.spectrum_type = SpectrumType.NMR_2D
                    metadata.confidence = 0.7
                    metadata.notes.append("检测到 2D 标识")
                    # 找 2D 子类型
                    for keyword in self.NMRI_2D_KEYWORDS:
                        if keyword in text_utf16:
                            metadata.sub_type = keyword
                            metadata.notes.append(f"2D 子类型: {keyword}")
                            break

        except Exception as e:
            self.logger.warning(f"mnova 文件解析失败: {e}")

        return metadata

    def _detect_mass_spec(self, filepath: str, fmt: str) -> SpectrumMetadata:
        """检测质谱文件"""
        file_size = os.path.getsize(filepath)
        # HRMS 通常 mzML 且文件较大
        is_highres = file_size > 5 * 1024 * 1024  # > 5MB

        metadata = SpectrumMetadata(
            spectrum_type=SpectrumType.MS_HIGHRES if is_highres else SpectrumType.MS_LOW_RES,
            file_format=fmt,
            confidence=0.85,
            notes=[
                f"质谱文件 ({'高分辨' if is_highres else '低分辨'})",
                f"文件格式: {fmt}",
            ]
        )

        # 尝试读取 mzML 头部
        if fmt in ["mzML", "mzXML"]:
            try:
                content = self._read_sample(filepath, max_bytes=8192).decode("utf-8", errors="ignore")
                # 寻找质量精度指示
                if "highRes" in content or "profile" in content:
                    metadata.spectrum_type = SpectrumType.MS_HIGHRES
                # 寻找电离方式
                ionizations = ["ESI", "EI", "CI", "MALDI", "FAB", "APCI", "APPI"]
                for ion in ionizations:
                    if ion in content:
                        metadata.notes.append(f"电离方式: {ion}")
                        break
            except Exception:
                pass

        return metadata

    def _detect_jcamp(self, filepath: str, content: bytes) -> SpectrumMetadata:
        """检测 JCAMP-DX 文件（IR/UV/NMR）"""
        metadata = SpectrumMetadata(
            spectrum_type=SpectrumType.IR,  # 默认
            file_format="JCAMP-DX",
            confidence=0.6,
        )

        try:
            text = content.decode("utf-8", errors="ignore")
            upper_text = text.upper()

            # JCAMP-DX 文件头部的 ##TITLE= 等字段
            title_match = re.search(r"##TITLE\s*=\s*(.+)", text, re.IGNORECASE)
            data_type_match = re.search(r"##DATATYPE\s*=\s*(.+)", text, re.IGNORECASE)

            if data_type_match:
                data_type = data_type_match.group(1).strip().upper()
                if "INFRARED" in data_type or "IR" in data_type:
                    metadata.spectrum_type = SpectrumType.IR
                    metadata.confidence = 0.95
                    metadata.notes.append(f"JCAMP-DX 数据类型: {data_type}")
                elif "ULTRAVIOLET" in data_type or "UV" in data_type:
                    metadata.spectrum_type = SpectrumType.UV_VIS
                    metadata.confidence = 0.95
                    metadata.notes.append(f"JCAMP-DX 数据类型: {data_type}")
                elif "NMR" in data_type:
                    # 区分 1D 和 2D
                    if "2D" in data_type or "COSY" in data_type or "HSQC" in data_type:
                        metadata.spectrum_type = SpectrumType.NMR_2D
                    else:
                        # 寻找核类型
                        for nucleus in self.NMR_NUCLEI:
                            if nucleus in data_type:
                                if nucleus == "1H":
                                    metadata.spectrum_type = SpectrumType.NMR_1H
                                elif nucleus == "13C":
                                    metadata.spectrum_type = SpectrumType.NMR_13C
                                metadata.nucleus = nucleus
                                break
                    metadata.confidence = 0.95
                    metadata.notes.append(f"JCAMP-DX NMR: {data_type}")
                elif "MASS" in data_type or "MS" in data_type:
                    metadata.spectrum_type = SpectrumType.MS_LOW_RES
                    metadata.confidence = 0.95
                    metadata.notes.append(f"JCAMP-DX MS: {data_type}")
            elif title_match:
                title = title_match.group(1).strip()
                metadata.notes.append(f"JCAMP-DX 标题: {title}")
                upper_title = title.upper()
                if "IR" in upper_title or "INFRARED" in upper_title:
                    metadata.spectrum_type = SpectrumType.IR
                    metadata.confidence = 0.7
                elif "UV" in upper_title:
                    metadata.spectrum_type = SpectrumType.UV_VIS
                    metadata.confidence = 0.7
                elif "NMR" in upper_title:
                    metadata.spectrum_type = SpectrumType.NMR_1H
                    metadata.confidence = 0.7
                elif "CD" in upper_title or "CIRCULAR DICHROISM" in upper_title:
                    metadata.spectrum_type = SpectrumType.CD
                    metadata.confidence = 0.7

            # 从数据范围判断
            xrange_match = re.search(r"##FIRSTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE)
            lastx_match = re.search(r"##LASTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE)
            if xrange_match and lastx_match:
                first_x = float(xrange_match.group(1))
                last_x = float(lastx_match.group(1))
                metadata.notes.append(f"数据范围: {first_x} - {last_x}")
                # IR 通常 4000-400 cm-1
                if 400 <= first_x <= 4500 and 200 <= last_x <= 500:
                    metadata.spectrum_type = SpectrumType.IR
                    metadata.confidence = max(metadata.confidence, 0.85)
                # UV 通常 200-800 nm
                elif 200 <= first_x <= 800 and 100 <= last_x <= 900:
                    metadata.spectrum_type = SpectrumType.UV_VIS
                    metadata.confidence = max(metadata.confidence, 0.85)
                # NMR 通常 -2 到 15 ppm
                elif -2 <= first_x <= 20 and -5 <= last_x <= 250:
                    if last_x > 50:
                        metadata.spectrum_type = SpectrumType.NMR_13C
                    else:
                        metadata.spectrum_type = SpectrumType.NMR_1H
                    metadata.confidence = max(metadata.confidence, 0.8)

        except Exception as e:
            self.logger.warning(f"JCAMP-DX 解析失败: {e}")

        return metadata

    def _detect_text_spectrum(self, filepath: str, content: bytes) -> SpectrumMetadata:
        """检测文本格式谱图（CSV/TXT/XY）"""
        metadata = SpectrumMetadata(
            spectrum_type=SpectrumType.UNKNOWN,
            file_format=Path(filepath).suffix.upper().lstrip("."),
            confidence=0.4,
            notes=[],
        )

        try:
            text = content.decode("utf-8", errors="ignore")
            lines = text.split("\n")[:20]  # 只看前 20 行

            # 寻找关键词
            text_lower = text.lower()
            if "wavenumber" in text_lower or "cm-1" in text_lower or "cm⁻¹" in text_lower:
                metadata.spectrum_type = SpectrumType.IR
                metadata.confidence = 0.8
                metadata.notes.append("检测到波数单位（IR）")
            elif "wavelength" in text_lower or "nm" in text_lower:
                # 可能是 UV 或 CD
                if "cd" in text_lower or "ellipticity" in text_lower or "mdeg" in text_lower:
                    metadata.spectrum_type = SpectrumType.CD
                    metadata.confidence = 0.8
                    metadata.notes.append("检测到圆二色谱特征")
                else:
                    metadata.spectrum_type = SpectrumType.UV_VIS
                    metadata.confidence = 0.8
                    metadata.notes.append("检测到波长单位（UV-Vis）")
            elif "ppm" in text_lower or "chemical shift" in text_lower:
                metadata.spectrum_type = SpectrumType.NMR_1H
                metadata.confidence = 0.8
                metadata.notes.append("检测到化学位移（ppm）")
            elif "m/z" in text_lower or "mass" in text_lower or "mz" in text_lower:
                metadata.spectrum_type = SpectrumType.MS_LOW_RES
                metadata.confidence = 0.7
                metadata.notes.append("检测到质荷比")
            elif "intensity" in text_lower or "absorbance" in text_lower:
                # 通用光谱，需要看数据范围
                pass

            # 解析数据看范围
            data_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
            if data_lines:
                # 尝试解析第一列
                x_values = []
                for line in data_lines[:10]:
                    parts = re.split(r"[\s,;\t]+", line.strip())
                    if parts and parts[0]:
                        try:
                            x_values.append(float(parts[0]))
                        except ValueError:
                            continue

                if x_values:
                    x_min, x_max = min(x_values), max(x_values)
                    metadata.notes.append(f"X 范围: {x_min} - {x_max}")

                    # 根据 X 范围推断类型
                    if x_min < 0 and x_max < 20:
                        metadata.spectrum_type = SpectrumType.NMR_1H
                        metadata.confidence = max(metadata.confidence, 0.7)
                    elif x_min >= 50 and x_max <= 250:
                        metadata.spectrum_type = SpectrumType.NMR_13C
                        metadata.confidence = max(metadata.confidence, 0.7)
                    elif x_min >= 200 and x_max <= 4000:
                        # 可能是 IR（4000-400）或 UV（200-800）
                        if x_max > 1000:
                            metadata.spectrum_type = SpectrumType.IR
                        else:
                            metadata.spectrum_type = SpectrumType.UV_VIS
                        metadata.confidence = max(metadata.confidence, 0.6)
                    elif x_min >= 50 and x_max <= 1000:
                        # 可能是 MS
                        metadata.spectrum_type = SpectrumType.MS_LOW_RES
                        metadata.confidence = max(metadata.confidence, 0.6)

        except Exception as e:
            self.logger.warning(f"文本谱图解析失败: {e}")

        return metadata

    def _detect_by_content(self, filepath: str, content: bytes) -> SpectrumMetadata:
        """根据内容判断（兜底）"""
        try:
            text = content.decode("utf-8", errors="ignore").lower()
        except:
            return SpectrumMetadata(
                spectrum_type=SpectrumType.UNKNOWN,
                file_format=Path(filepath).suffix,
                confidence=0.0,
            )

        # 各种关键词匹配
        if "nmr" in text and any(k in text for k in ["cosy", "hsqc", "hmbc", "noesy"]):
            return SpectrumMetadata(
                spectrum_type=SpectrumType.NMR_2D,
                file_format=Path(filepath).suffix,
                confidence=0.6,
                notes=["从内容检测到 2D NMR"]
            )
        elif "mestrenova" in text or "mnova" in text:
            return SpectrumMetadata(
                spectrum_type=SpectrumType.NMR_1H,
                file_format="MestReNova",
                confidence=0.5,
                notes=["从内容检测到 MestReNova"]
            )

        return SpectrumMetadata(
            spectrum_type=SpectrumType.UNKNOWN,
            file_format=Path(filepath).suffix,
            confidence=0.2,
            notes=["无法自动识别谱图类型"]
        )


# 便捷函数
def detect_spectrum_type(filepath: str) -> SpectrumMetadata:
    """便捷函数：识别谱图类型"""
    detector = SpectrumTypeDetector()
    return detector.detect(filepath)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        meta = detect_spectrum_type(sys.argv[1])
        print(f"谱图类型: {meta.spectrum_type.value}")
        print(f"文件格式: {meta.file_format}")
        print(f"置信度: {meta.confidence:.0%}")
        if meta.nucleus:
            print(f"核类型: {meta.nucleus}")
        if meta.solvent:
            print(f"溶剂: {meta.solvent}")
        if meta.sub_type:
            print(f"子类型: {meta.sub_type}")
        if meta.notes:
            print("备注:")
            for note in meta.notes:
                print(f"  - {note}")
    else:
        print("用法: python spectrum_type_detector.py <谱图文件>")

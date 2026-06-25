#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_spectrum_analyzer.py — 多类型谱图分析模块

支持以下谱图类型的分析：
  - 1D NMR (1H, 13C, 19F, 31P)
  - 2D NMR (COSY, HSQC, HMBC, NOESY, ROESY)
  - MS (低分辨/高分辨)
  - IR
  - UV-Vis
  - CD
  - X-ray CIF
  - 色谱 (HPLC, GC)
"""

import os
import re
import csv
import json
import logging
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict

from spectrum_type_detector import SpectrumTypeDetector, SpectrumType, SpectrumMetadata

logger = logging.getLogger("multi_spectrum_analyzer")


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    spectrum_type: str
    file_path: str
    confidence: float
    raw_data: Dict[str, Any] = field(default_factory=dict)
    peaks: List[Dict[str, Any]] = field(default_factory=list)
    structural_info: Dict[str, Any] = field(default_factory=dict)
    functional_groups: List[str] = field(default_factory=list)
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    notes: List[str] = field(default_factory=list)
    output_files: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiSpectrumAnalyzer:
    """多类型谱图分析器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.detector = SpectrumTypeDetector()
        self.logger = logging.getLogger("multi_spectrum_analyzer")

    def analyze(self, filepath: str, output_dir: Optional[str] = None) -> AnalysisResult:
        """
        自动识别谱图类型并分析

        Args:
            filepath: 谱图文件路径
            output_dir: 输出目录
        """
        if output_dir is None:
            output_dir = os.path.join(
                self.config.get("output_dir", "./outputs"),
                Path(filepath).stem
            )
        os.makedirs(output_dir, exist_ok=True)

        # Step 1: 识别类型
        metadata = self.detector.detect(filepath)
        self.logger.info(f"识别到谱图类型: {metadata.spectrum_type.value} "
                        f"(置信度: {metadata.confidence:.0%})")

        # Step 2: 分发到对应的分析方法
        result = None
        if metadata.spectrum_type in [SpectrumType.NMR_1H, SpectrumType.NMR_13C,
                                       SpectrumType.NMR_19F, SpectrumType.NMR_31P]:
            result = self._analyze_1d_nmr(filepath, metadata, output_dir)
        elif metadata.spectrum_type == SpectrumType.NMR_2D:
            result = self._analyze_2d_nmr(filepath, metadata, output_dir)
        elif metadata.spectrum_type in [SpectrumType.MS_LOW_RES, SpectrumType.MS_HIGHRES]:
            result = self._analyze_mass_spec(filepath, metadata, output_dir)
        elif metadata.spectrum_type == SpectrumType.IR:
            result = self._analyze_ir(filepath, metadata, output_dir)
        elif metadata.spectrum_type == SpectrumType.UV_VIS:
            result = self._analyze_uv_vis(filepath, metadata, output_dir)
        elif metadata.spectrum_type == SpectrumType.CD:
            result = self._analyze_cd(filepath, metadata, output_dir)
        elif metadata.spectrum_type == SpectrumType.XRAY_CIF:
            result = self._analyze_xray_cif(filepath, metadata, output_dir)
        elif metadata.spectrum_type in [SpectrumType.HPLC_CHROMATOGRAM, SpectrumType.GC_CHROMATOGRAM]:
            result = self._analyze_chromatogram(filepath, metadata, output_dir)
        else:
            result = self._analyze_generic(filepath, metadata, output_dir)

        return result

    # =========================================================================
    # 1D NMR 分析
    # =========================================================================
    def _analyze_1d_nmr(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析 1D NMR 谱图"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        result.molecular_formula = None
        if metadata.nucleus:
            result.structural_info["nucleus"] = metadata.nucleus
        if metadata.solvent:
            result.structural_info["solvent"] = metadata.solvent

        # 如果是 .mnova 文件，用 Mestrenova GUI 处理
        if filepath.lower().endswith(".mnova"):
            result = self._process_mnova_1d(filepath, metadata, output_dir)
        else:
            # 其他格式（jdx, csv 等）直接解析
            result = self._parse_1d_nmr_text(filepath, metadata, output_dir)

        return result

    def _process_mnova_1d(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """用 Mestrenova GUI 处理 1D NMR"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        if metadata.nucleus:
            result.structural_info["nucleus"] = metadata.nucleus
        if metadata.solvent:
            result.structural_info["solvent"] = metadata.solvent

        try:
            from mestrenova_gui import MestrenovaGUI
            config = self.config
            mnova_path = config.get("software_paths", {}).get("mestrenova")
            mnova = MestrenovaGUI(executable_path=mnova_path)

            if not mnova.launch():
                result.errors.append("Mestrenova 启动失败")
                return result

            time.sleep(2)
            mnova.open_file(filepath)
            time.sleep(3)

            # 1D 谱图：自动峰识别和积分
            mnova.auto_pick_peaks()
            time.sleep(2)
            mnova.auto_integrate()
            time.sleep(2)

            # 导出峰数据
            csv_path = os.path.join(output_dir, "peaks.csv")
            mnova.export_peaks_to_csv(csv_path)
            result.output_files["peaks_csv"] = csv_path

            # 导出谱图
            img_path = os.path.join(output_dir, "spectrum.png")
            mnova.export_spectrum_image(img_path)
            result.output_files["spectrum_image"] = img_path

            # 解析峰数据
            if os.path.exists(csv_path):
                result.peaks = self._parse_peaks_csv(csv_path)

            # 提取结构信息
            self._extract_1d_nmr_info(result, metadata)

            result.success = True

        except Exception as e:
            result.errors.append(f"1D NMR 分析失败: {e}")
            self.logger.exception("1D NMR 分析异常")

        return result

    def _parse_1d_nmr_text(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """解析文本格式的 1D NMR 数据"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            ext = Path(filepath).suffix.lower()
            if ext in [".jdx", ".dx", ".jcm"]:
                peaks = self._parse_jcamp_nmr(filepath, output_dir)
                result.peaks = peaks
                result.success = len(peaks) > 0
            elif ext in [".csv", ".txt", ".xy"]:
                peaks = self._parse_xy_nmr(filepath, output_dir)
                result.peaks = peaks
                result.success = len(peaks) > 0
        except Exception as e:
            result.errors.append(f"文本 NMR 解析失败: {e}")

        return result

    def _parse_jcamp_nmr(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 JCAMP-DX 格式 NMR"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            # 提取数据点
            data_section = re.search(r"##XYDATA\s*=\s*\(X\+\+\(Y\.\.\.\)\)(.*?)(?:##END|$)",
                                      text, re.DOTALL | re.IGNORECASE)
            if data_section:
                data_str = data_section.group(1)
                # 解析 (X++(Y..Y)) 格式
                numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", data_str)
                if numbers:
                    first_x = float(re.search(r"##FIRSTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE).group(1))
                    last_x = float(re.search(r"##LASTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE).group(1))
                    n_points = int(re.search(r"##NPOINTS\s*=\s*(\d+)", text, re.IGNORECASE).group(1))
                    x_step = (last_x - first_x) / (n_points - 1) if n_points > 1 else 0

                    # 通常 JCAMP 中 X++(Y..Y) 格式：第一个是 X 起点，后面是 Y 值
                    for i, y_str in enumerate(numbers[1:], 0):
                        if i >= n_points:
                            break
                        x = first_x + i * x_step
                        y = float(y_str)
                        peaks.append({
                            "shift_ppm": x,
                            "intensity": y,
                            "multiplicity": "unknown"
                        })

            # 保存解析后的数据
            if peaks:
                out_csv = os.path.join(output_dir, "peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["shift_ppm", "intensity", "multiplicity"])
                    for p in peaks:
                        writer.writerow([p["shift_ppm"], p["intensity"], p["multiplicity"]])

        except Exception as e:
            self.logger.error(f"JCAMP-DX 解析失败: {e}")

        return peaks

    def _parse_xy_nmr(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 X-Y 格式 NMR 数据"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"[\s,;\t]+", line)
                if len(parts) >= 2:
                    try:
                        x = float(parts[0])
                        y = float(parts[1])
                        peaks.append({
                            "shift_ppm": x,
                            "intensity": y,
                            "multiplicity": "unknown"
                        })
                    except ValueError:
                        continue

            # 保存为 CSV
            if peaks:
                out_csv = os.path.join(output_dir, "peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["shift_ppm", "intensity", "multiplicity"])
                    for p in peaks:
                        writer.writerow([p["shift_ppm"], p["intensity"], p["multiplicity"]])

        except Exception as e:
            self.logger.error(f"X-Y NMR 解析失败: {e}")

        return peaks

    def _extract_1d_nmr_info(self, result: AnalysisResult, metadata: SpectrumMetadata):
        """从 1D NMR 峰数据中提取结构信息"""
        if not result.peaks:
            return

        # 1H NMR 化学位移与官能团对应关系
        func_groups_1h = {
            (10.0, 12.0): "羧酸 -COOH / 醛 -CHO",
            (8.0, 10.0): "芳香氢 / 杂环氢 Ar-H",
            (6.5, 8.0): "芳香氢 Ar-H",
            (5.0, 6.5): "烯烃氢 =CH- / 酰胺 -NH",
            (3.0, 5.0): "与杂原子相连的 CH (O-CH, N-CH)",
            (2.0, 3.0): "α-羰基 CH (CH-CO, CH-N)",
            (1.0, 2.0): "脂肪族 CH2 (与 C=C、C=O 邻近)",
            (0.5, 1.0): "脂肪族 CH3 (远离官能团)",
            (0.0, 0.5): "TMS 标峰",
        }

        # 13C NMR 化学位移
        func_groups_13c = {
            (160, 220): "羰基碳 C=O",
            (100, 160): "芳香/烯烃 sp2 碳",
            (50, 100): "与杂原子相连的 sp3 碳 (C-O, C-N)",
            (20, 50): "脂肪族 sp3 碳 (CH2, CH)",
            (0, 20): "脂肪族甲基 CH3",
        }

        is_1h = metadata.nucleus == "1H" if metadata.nucleus else True
        table = func_groups_1h if is_1h else func_groups_13c

        groups = set()
        for peak in result.peaks:
            shift = peak.get("shift_ppm", 0)
            for (lo, hi), group in table.items():
                if lo <= shift <= hi:
                    groups.add(group)
                    break

        result.functional_groups = list(groups)
        result.structural_info["detected_groups"] = list(groups)

    # =========================================================================
    # 2D NMR 分析
    # =========================================================================
    def _analyze_2d_nmr(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析 2D NMR 谱图"""
        result = AnalysisResult(
            success=False,
            spectrum_type=f"2D-NMR ({metadata.sub_type or 'Unknown'})",
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        if metadata.nucleus:
            result.structural_info["nucleus"] = metadata.nucleus
        if metadata.solvent:
            result.structural_info["solvent"] = metadata.solvent
        if metadata.sub_type:
            result.structural_info["2d_type"] = metadata.sub_type

        try:
            from mestrenova_gui import MestrenovaGUI
            config = self.config
            mnova_path = config.get("software_paths", {}).get("mestrenova")
            mnova = MestrenovaGUI(executable_path=mnova_path)

            if not mnova.launch():
                result.errors.append("Mestrenova 启动失败")
                return result

            time.sleep(2)
            mnova.open_file(filepath)
            time.sleep(3)

            # 2D 谱图处理：导出整个 2D 谱图
            # 2D 谱图没有"自动峰识别"概念，需要导出整个 2D 谱图
            # 然后由用户/Agent 解读

            # 导出 2D 谱图为图片
            img_path = os.path.join(output_dir, "2d_spectrum.png")
            mnova.export_spectrum_image(img_path)
            result.output_files["spectrum_image"] = img_path

            # 导出 2D 峰表
            csv_path = os.path.join(output_dir, "2d_peaks.csv")
            try:
                mnova.export_peaks_to_csv(csv_path)
                result.output_files["peaks_csv"] = csv_path
                if os.path.exists(csv_path):
                    result.peaks = self._parse_peaks_csv(csv_path)
            except Exception as e:
                result.notes.append(f"导出 2D 峰列表失败: {e}")

            # 提取 2D 谱图解读信息
            self._extract_2d_nmr_info(result, metadata)

            result.success = True

        except Exception as e:
            result.errors.append(f"2D NMR 分析失败: {e}")
            self.logger.exception("2D NMR 分析异常")

        return result

    def _extract_2d_nmr_info(self, result: AnalysisResult, metadata: SpectrumMetadata):
        """从 2D NMR 谱图中提取结构信息"""
        if not metadata.sub_type:
            return

        sub_type = metadata.sub_type.upper()
        info = {
            "COSY": "相关谱 (Correlation Spectroscopy): 显示 J 耦合的氢-氢关系，用于识别相邻氢原子",
            "HSQC": "异核单量子相干 (Heteronuclear Single Quantum Coherence): 显示直接相连的 C-H 关系",
            "HMBC": "异核多键相关 (Heteronuclear Multiple Bond Correlation): 显示 2-3 键的 C-H 关系",
            "NOESY": "核欧豪斯效应谱 (Nuclear Overhauser Effect Spectroscopy): 显示空间上接近的氢原子，用于立体化学",
            "ROESY": "旋转框架 NOE: NOESY 的替代方法",
            "TOCSY": "全相关谱: 显示完整自旋系统",
        }

        if sub_type in info:
            result.structural_info["2d_info"] = info[sub_type]
            result.structural_info["interpretation_guide"] = info[sub_type]

        # 2D NMR 推导结构的典型应用
        if sub_type == "HMBC":
            result.functional_groups.append("HMBC: 远程 C-H 关联")
            result.notes.append("HMBC 用于连接不同结构片段，确定骨架连接方式")
        elif sub_type == "COSY":
            result.functional_groups.append("COSY: 邻位 H-H 耦合")
            result.notes.append("COSY 用于识别自旋系统，构建结构片段")
        elif sub_type == "HSQC":
            result.functional_groups.append("HSQC: 直接 C-H 关联")
            result.notes.append("HSQC 用于归属每个 H 所连的 C")
        elif sub_type == "NOESY":
            result.functional_groups.append("NOESY: 空间相邻 H")
            result.notes.append("NOESY 用于确定立体化学和空间构型")

    # =========================================================================
    # 质谱分析
    # =========================================================================
    def _analyze_mass_spec(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析质谱"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            ext = Path(filepath).suffix.lower()
            if ext in [".mzml", ".mzxml"]:
                peaks = self._parse_mzml(filepath, output_dir)
            elif ext in [".csv", ".txt", ".xy"]:
                peaks = self._parse_xy_mass_spec(filepath, output_dir)
            elif ext == ".mgf":
                peaks = self._parse_mgf(filepath, output_dir)
            elif ext in [".raw", ".dta"]:
                # 厂商二进制格式，需要用专业软件
                result.notes.append(f"{ext} 格式需要用相应厂商软件读取")
                result.notes.append("建议转换为 mzML 后再分析")
                peaks = []
            else:
                peaks = []

            result.peaks = peaks
            if peaks:
                # 提取分子离子峰
                self._extract_ms_info(result, metadata)
                result.success = True

        except Exception as e:
            result.errors.append(f"质谱分析失败: {e}")
            self.logger.exception("质谱分析异常")

        return result

    def _parse_mzml(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 mzML 格式质谱"""
        peaks = []
        try:
            # 简单 XML 解析 mzML
            import xml.etree.ElementTree as ET
            tree = ET.parse(filepath)
            root = tree.getroot()

            ns = {"mzml": "http://psi.hupo.org/ms/mzml"}

            # 找所有 peak
            for spec in root.iter("{http://psi.hupo.org/ms/mzml}spectrum"):
                mzs = []
                ints = []
                for binary in spec.iter("{http://psi.hupo.org/ms/mzml}binary"):
                    # 简化：只取数字
                    pass

                # 简化：直接找 m/z 和 intensity 数组
                for cvparam in spec.iter("{http://psi.hupo.org/ms/mzml}cvParam"):
                    name = cvparam.get("name", "")
                    if name == "m/z array":
                        # 这里需要 base64 解码 + 字节到 float
                        pass

            # 如果上面的解析没成功，尝试纯文本搜索
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            # 简化：直接找数字
            all_numbers = re.findall(r"\b\d+\.\d+\b", text)
            if all_numbers:
                # 每两个数作为一对 (m/z, intensity)
                for i in range(0, min(len(all_numbers), 1000), 2):
                    if i + 1 < len(all_numbers):
                        try:
                            mz = float(all_numbers[i])
                            intensity = float(all_numbers[i + 1])
                            if 10 < mz < 2000 and 0 < intensity < 1e12:
                                peaks.append({
                                    "mz": mz,
                                    "intensity": intensity,
                                })
                        except ValueError:
                            continue

            # 保存解析后的峰
            if peaks:
                out_csv = os.path.join(output_dir, "ms_peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["mz", "intensity"])
                    for p in peaks:
                        writer.writerow([p["mz"], p["intensity"]])
                self.logger.info(f"解析到 {len(peaks)} 个质谱峰")

        except Exception as e:
            self.logger.error(f"mzML 解析失败: {e}")

        return peaks

    def _parse_xy_mass_spec(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 X-Y 格式质谱"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = re.split(r"[\s,;\t]+", line)
                    if len(parts) >= 2:
                        try:
                            mz = float(parts[0])
                            intensity = float(parts[1])
                            peaks.append({"mz": mz, "intensity": intensity})
                        except ValueError:
                            continue

            if peaks:
                out_csv = os.path.join(output_dir, "ms_peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["mz", "intensity"])
                    for p in peaks:
                        writer.writerow([p["mz"], p["intensity"]])

        except Exception as e:
            self.logger.error(f"X-Y 质谱解析失败: {e}")

        return peaks

    def _parse_mgf(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 MGF 格式质谱"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                in_peak = False
                peak_data = []
                for line in f:
                    line = line.strip()
                    if line == "BEGIN IONS":
                        in_peak = True
                        peak_data = []
                    elif line == "END IONS":
                        in_peak = False
                    elif in_peak and line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                mz = float(parts[0])
                                intensity = float(parts[1])
                                peak_data.append({"mz": mz, "intensity": intensity})
                            except ValueError:
                                pass
                    if peak_data and not in_peak:
                        peaks.extend(peak_data)
                        peak_data = []
        except Exception as e:
            self.logger.error(f"MGF 解析失败: {e}")

        return peaks

    def _extract_ms_info(self, result: AnalysisResult, metadata: SpectrumMetadata):
        """从质谱数据中提取结构信息"""
        if not result.peaks:
            return

        # 按强度排序
        sorted_peaks = sorted(result.peaks, key=lambda x: x.get("intensity", 0), reverse=True)

        # 找分子离子峰 (M+)：通常是最高 m/z 的显著峰
        molecular_ion_candidates = []
        for peak in sorted_peaks:
            mz = peak.get("mz", 0)
            intensity = peak.get("intensity", 0)
            if 50 < mz < 2000:  # 合理范围
                molecular_ion_candidates.append(peak)

        if molecular_ion_candidates:
            # 取强度最高且 m/z 较大的
            mi = max(molecular_ion_candidates, key=lambda x: x.get("intensity", 0))
            mz = mi.get("mz", 0)

            # HRMS 模式下：尝试从 m/z 推断分子式
            if metadata.spectrum_type == SpectrumType.MS_HIGHRES:
                result.molecular_weight = mz
                result.structural_info["molecular_ion_mz"] = mz
                # 简单的分子式推断（需要更复杂的算法）
                result.notes.append(f"HRMS: [M+H]+ 或 M+ 推测为 m/z = {mz:.4f}")
            else:
                result.molecular_weight = round(mz)
                result.structural_info["molecular_ion_mz"] = round(mz)
                result.notes.append(f"MS: 分子离子峰 m/z = {round(mz)}")

        # 常见碎片离子
        common_losses = {
            15: "CH3 丢失",
            18: "H2O 丢失",
            28: "CO 丢失",
            29: "CHO 丢失",
            31: "OCH3 丢失",
            43: "C3H7 / CH3CO 丢失",
            57: "C4H9 丢失",
            91: "C7H7 (苄基) 丢失",
        }

        result.notes.append("前 5 个最强峰:")
        for i, peak in enumerate(sorted_peaks[:5], 1):
            mz = peak.get("mz", 0)
            intensity = peak.get("intensity", 0)
            result.notes.append(f"  {i}. m/z = {mz:.2f}, intensity = {intensity:.0f}")

    # =========================================================================
    # 红外光谱 (IR) 分析
    # =========================================================================
    def _analyze_ir(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析红外光谱"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            ext = Path(filepath).suffix.lower()
            if ext in [".jdx", ".dx", ".jcm"]:
                peaks = self._parse_jcamp_ir(filepath, output_dir)
            elif ext in [".csv", ".txt", ".xy", ".asc"]:
                peaks = self._parse_xy_ir(filepath, output_dir)
            else:
                peaks = []

            result.peaks = peaks
            if peaks:
                self._extract_ir_info(result, metadata)
                result.success = True

        except Exception as e:
            result.errors.append(f"IR 分析失败: {e}")
            self.logger.exception("IR 分析异常")

        return result

    def _parse_jcamp_ir(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 JCAMP-DX 格式 IR"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            # 提取数据
            data_section = re.search(r"##XYDATA\s*=\s*\(X\+\+\(Y\.\.\.\)\)(.*?)(?:##END|$)",
                                      text, re.DOTALL | re.IGNORECASE)
            if data_section:
                data_str = data_section.group(1)
                numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", data_str)
                if numbers:
                    first_x = float(re.search(r"##FIRSTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE).group(1))
                    last_x = float(re.search(r"##LASTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE).group(1))
                    n_points = int(re.search(r"##NPOINTS\s*=\s*(\d+)", text, re.IGNORECASE).group(1))
                    x_step = (last_x - first_x) / (n_points - 1) if n_points > 1 else 0

                    for i, y_str in enumerate(numbers[1:], 0):
                        if i >= n_points:
                            break
                        x = first_x + i * x_step
                        y = float(y_str)
                        peaks.append({"wavenumber": x, "absorbance": y})

            # 保存为 CSV
            if peaks:
                out_csv = os.path.join(output_dir, "ir_peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["wavenumber_cm-1", "absorbance"])
                    for p in peaks:
                        writer.writerow([p["wavenumber"], p["absorbance"]])

        except Exception as e:
            self.logger.error(f"JCAMP IR 解析失败: {e}")

        return peaks

    def _parse_xy_ir(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 X-Y 格式 IR"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = re.split(r"[\s,;\t]+", line)
                    if len(parts) >= 2:
                        try:
                            wn = float(parts[0])
                            ab = float(parts[1])
                            peaks.append({"wavenumber": wn, "absorbance": ab})
                        except ValueError:
                            continue

            if peaks:
                out_csv = os.path.join(output_dir, "ir_peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["wavenumber_cm-1", "absorbance"])
                    for p in peaks:
                        writer.writerow([p["wavenumber"], p["absorbance"]])

        except Exception as e:
            self.logger.error(f"X-Y IR 解析失败: {e}")

        return peaks

    def _extract_ir_info(self, result: AnalysisResult, metadata: SpectrumMetadata):
        """从 IR 数据中提取官能团信息"""
        if not result.peaks:
            return

        # IR 特征吸收与官能团对应关系
        ir_groups = {
            (3200, 3600): "O-H 伸缩（醇、酚）",
            (3300, 3500): "N-H 伸缩（胺、酰胺）",
            (3000, 3100): "不饱和 C-H 伸缩（=C-H，芳香）",
            (2850, 3000): "饱和 C-H 伸缩（sp3 C-H）",
            (2200, 2260): "C≡C 或 C≡N 伸缩",
            (1680, 1750): "C=O 伸缩（羰基）",
            (1620, 1680): "C=C 伸缩（烯烃）/ 酰胺 C=O",
            (1450, 1600): "芳环 C=C 骨架振动",
            (1350, 1470): "C-H 弯曲（甲基、亚甲基）",
            (1000, 1300): "C-O 伸缩（醇、醚、酯）",
            (700, 900): "芳环 C-H 面外弯曲 / 顺反烯烃",
        }

        # 找最高峰位置
        sorted_peaks = sorted(result.peaks, key=lambda x: x.get("absorbance", 0), reverse=True)
        top_peaks = sorted_peaks[:10]

        groups_found = set()
        for peak in top_peaks:
            wn = peak.get("wavenumber", 0)
            for (lo, hi), group in ir_groups.items():
                if lo <= wn <= hi:
                    groups_found.add(group)
                    break

        result.functional_groups = list(groups_found)
        result.structural_info["ir_bands"] = list(groups_found)
        result.notes.append("IR 主要吸收带:")
        for i, peak in enumerate(top_peaks[:5], 1):
            wn = peak.get("wavenumber", 0)
            ab = peak.get("absorbance", 0)
            result.notes.append(f"  {i}. {wn:.1f} cm-1 (吸光度: {ab:.3f})")

    # =========================================================================
    # 紫外-可见光谱 (UV-Vis) 分析
    # =========================================================================
    def _analyze_uv_vis(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析 UV-Vis 光谱"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            ext = Path(filepath).suffix.lower()
            if ext in [".csv", ".txt", ".xy", ".asc"]:
                peaks = self._parse_xy_spectrum(filepath, output_dir, "wavelength_nm", "absorbance")
            elif ext in [".jdx", ".dx", ".jcm"]:
                peaks = self._parse_jcamp_uv_vis(filepath, output_dir)
            else:
                peaks = []

            result.peaks = peaks
            if peaks:
                self._extract_uv_info(result)
                result.success = True

        except Exception as e:
            result.errors.append(f"UV-Vis 分析失败: {e}")
            self.logger.exception("UV-Vis 分析异常")

        return result

    def _parse_jcamp_uv_vis(self, filepath: str, output_dir: str) -> List[Dict[str, Any]]:
        """解析 JCAMP-DX 格式 UV-Vis"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            data_section = re.search(r"##XYDATA\s*=\s*\(X\+\+\(Y\.\.\.\)\)(.*?)(?:##END|$)",
                                      text, re.DOTALL | re.IGNORECASE)
            if data_section:
                data_str = data_section.group(1)
                numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", data_str)
                if numbers:
                    first_x = float(re.search(r"##FIRSTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE).group(1))
                    last_x = float(re.search(r"##LASTX\s*=\s*([\d\.\-eE]+)", text, re.IGNORECASE).group(1))
                    n_points = int(re.search(r"##NPOINTS\s*=\s*(\d+)", text, re.IGNORECASE).group(1))
                    x_step = (last_x - first_x) / (n_points - 1) if n_points > 1 else 0

                    for i, y_str in enumerate(numbers[1:], 0):
                        if i >= n_points:
                            break
                        x = first_x + i * x_step
                        y = float(y_str)
                        peaks.append({"wavelength_nm": x, "absorbance": y})

            if peaks:
                out_csv = os.path.join(output_dir, "uv_peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["wavelength_nm", "absorbance"])
                    for p in peaks:
                        writer.writerow([p["wavelength_nm"], p["absorbance"]])

        except Exception as e:
            self.logger.error(f"JCAMP UV 解析失败: {e}")

        return peaks

    def _parse_xy_spectrum(self, filepath: str, output_dir: str,
                           x_col: str, y_col: str) -> List[Dict[str, Any]]:
        """通用 X-Y 光谱解析"""
        peaks = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = re.split(r"[\s,;\t]+", line)
                    if len(parts) >= 2:
                        try:
                            x = float(parts[0])
                            y = float(parts[1])
                            peaks.append({x_col: x, y_col: y})
                        except ValueError:
                            continue

            if peaks:
                out_csv = os.path.join(output_dir, f"spectrum_peaks.csv")
                with open(out_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([x_col, y_col])
                    for p in peaks:
                        writer.writerow([p[x_col], p[y_col]])
        except Exception as e:
            self.logger.error(f"X-Y 光谱解析失败: {e}")
        return peaks

    def _extract_uv_info(self, result: AnalysisResult):
        """从 UV-Vis 数据中提取结构信息"""
        if not result.peaks:
            return

        # 找吸收峰
        sorted_peaks = sorted(result.peaks, key=lambda x: x.get("absorbance", 0), reverse=True)
        top_peaks = sorted_peaks[:5]

        # UV 吸收与结构对应
        uv_structures = {
            (200, 220): "n→σ* 跃迁（饱和化合物）",
            (220, 250): "共轭二烯 / 苯的 E2 带",
            (250, 290): "苯的 B 带 / 简单芳香化合物",
            (290, 350): "n→π* 跃迁（羰基化合物）",
            (350, 400): "扩展共轭体系",
        }

        groups = set()
        result.notes.append("UV-Vis 吸收峰:")
        for i, peak in enumerate(top_peaks, 1):
            wl = peak.get("wavelength_nm", 0)
            ab = peak.get("absorbance", 0)
            result.notes.append(f"  {i}. λ_max = {wl:.1f} nm (A = {ab:.3f})")
            for (lo, hi), struct in uv_structures.items():
                if lo <= wl <= hi:
                    groups.add(struct)
                    break

        result.functional_groups = list(groups)
        result.structural_info["uv_features"] = list(groups)

    # =========================================================================
    # 圆二色谱 (CD) 分析
    # =========================================================================
    def _analyze_cd(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析 CD 谱图"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            peaks = self._parse_xy_spectrum(filepath, output_dir, "wavelength_nm", "ellipticity")
            result.peaks = peaks
            if peaks:
                # CD 谱图分析手性
                self._extract_cd_info(result)
                result.success = True
        except Exception as e:
            result.errors.append(f"CD 分析失败: {e}")

        return result

    def _extract_cd_info(self, result: AnalysisResult):
        """从 CD 数据中提取手性信息"""
        if not result.peaks:
            return

        sorted_peaks = sorted(result.peaks, key=lambda x: abs(x.get("ellipticity", 0)), reverse=True)
        result.notes.append("CD 谱图特征:")
        for i, peak in enumerate(sorted_peaks[:5], 1):
            wl = peak.get("wavelength_nm", 0)
            el = peak.get("ellipticity", 0)
            sign = "+" if el > 0 else "-"
            result.notes.append(f"  {i}. λ = {wl:.1f} nm, θ = {sign}{abs(el):.2f}")

        result.structural_info["cd_type"] = "用于立体化学和构型分析"

    # =========================================================================
    # X-ray CIF 分析
    # =========================================================================
    def _analyze_xray_cif(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析 X 射线晶体学 CIF 文件"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                cif_text = f.read()

            # 提取关键信息
            cif_info = {}
            patterns = {
                "cell_length_a": r"_cell_length_a\s+([\d\.\-]+)",
                "cell_length_b": r"_cell_length_b\s+([\d\.\-]+)",
                "cell_length_c": r"_cell_length_c\s+([\d\.\-]+)",
                "cell_angle_alpha": r"_cell_angle_alpha\s+([\d\.\-]+)",
                "cell_angle_beta": r"_cell_angle_beta\s+([\d\.\-]+)",
                "cell_angle_gamma": r"_cell_angle_gamma\s+([\d\.\-]+)",
                "space_group": r"_space_group_name_H-M_alt\s+['\"]?([\w\s/\-]+)['\"]?",
                "chemical_formula": r"_chemical_formula_sum\s+['\"]?([^'\"]+)['\"]?",
            }

            for key, pattern in patterns.items():
                m = re.search(pattern, cif_text, re.IGNORECASE)
                if m:
                    cif_info[key] = m.group(1).strip()

            if "chemical_formula" in cif_info:
                result.molecular_formula = cif_info["chemical_formula"]

            result.structural_info["crystal_info"] = cif_info
            result.notes.append("X 射线晶体学数据:")
            for k, v in cif_info.items():
                result.notes.append(f"  {k}: {v}")

            # 保存解析结果
            out_json = os.path.join(output_dir, "cif_info.json")
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(cif_info, f, ensure_ascii=False, indent=2)
            result.output_files["cif_info"] = out_json

            result.success = True

        except Exception as e:
            result.errors.append(f"CIF 分析失败: {e}")

        return result

    # =========================================================================
    # 色谱分析
    # =========================================================================
    def _analyze_chromatogram(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """分析色谱图 (HPLC/GC)"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy(),
        )

        try:
            peaks = self._parse_xy_spectrum(filepath, output_dir, "retention_time", "intensity")
            result.peaks = peaks
            if peaks:
                # 找峰
                result.notes.append("色谱峰:")
                top_peaks = sorted(peaks, key=lambda x: x.get("intensity", 0), reverse=True)[:5]
                for i, peak in enumerate(top_peaks, 1):
                    rt = peak.get("retention_time", 0)
                    intensity = peak.get("intensity", 0)
                    result.notes.append(f"  {i}. tR = {rt:.2f}, intensity = {intensity:.0f}")
                result.success = True
        except Exception as e:
            result.errors.append(f"色谱分析失败: {e}")

        return result

    # =========================================================================
    # 通用兜底
    # =========================================================================
    def _analyze_generic(self, filepath: str, metadata: SpectrumMetadata, output_dir: str) -> AnalysisResult:
        """通用分析（兜底）"""
        result = AnalysisResult(
            success=False,
            spectrum_type=metadata.spectrum_type.value,
            file_path=filepath,
            confidence=metadata.confidence,
            notes=metadata.notes.copy() + ["未能识别具体谱图类型，尝试通用解析"],
        )

        try:
            # 尝试解析为 X-Y 数据
            peaks = self._parse_xy_spectrum(filepath, output_dir, "x", "y")
            result.peaks = peaks
            if peaks:
                result.success = True
        except Exception as e:
            result.errors.append(f"通用解析失败: {e}")

        return result

    def _parse_peaks_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """解析峰列表 CSV"""
        peaks = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 尝试识别列名
                    peak = {}
                    for k, v in row.items():
                        if v is None or v == "":
                            continue
                        try:
                            peak[k] = float(v)
                        except ValueError:
                            peak[k] = v
                    if peak:
                        peaks.append(peak)
        except Exception as e:
            self.logger.warning(f"峰列表 CSV 解析失败: {e}")
        return peaks


# 导入 time 用于延时
import time


# 便捷函数
def analyze_spectrum_auto(filepath: str, output_dir: Optional[str] = None,
                          config: Optional[Dict[str, Any]] = None) -> AnalysisResult:
    """便捷函数：自动识别并分析谱图"""
    analyzer = MultiSpectrumAnalyzer(config=config)
    return analyzer.analyze(filepath, output_dir)

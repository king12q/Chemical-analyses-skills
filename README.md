# 🧪 Chemical-analyses-skills

[English](README.md) | **中文**

> AI 智能识谱工具 — 自动识别 NMR/IR/MS/UV/ECD 等谱图数据，调用专业软件推导化合物结构

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20|%20macOS%20|%20Linux-yellow.svg)](https://github.com/king12q/Chemical-analyses-skills)

---

## ✨ 功能特性

- 🔬 **全自动谱图分析**：自动识别 ¹H-NMR / ¹³C-NMR / IR / MS / UV / ECD / ORD 等数据类型
- 🤖 **专业软件集成**：调用 Mestrenova / Spartan / Specdis / **ChemDraw** / Chem3D 等本地软件
- 🌐 **在线数据库查询**：自动查询 PubChem / SDBS / ChemSpider 辅助结构确定
- 🧬 **天然药物化学推理**：模拟专业研究者的思路推导分子式与结构
- 🎨 **多后端绘制引擎**：支持 RDKit / ChemDraw / Chem3D / OpenBabel，智能选择最优先可用后端
- 📊 **多格式结构导出**：PNG / SVG / SDF / MOL / PDB / CML / **CDXML**（ChemDraw 原生格式）
- 📈 **置信度评估**：多维度评分 + 数据补充建议

---

## 📖 工作流程

```
输入谱图数据
      │
      ▼
┌────────────────────┐
│  数据类型识别       │  自动识别格式：.mnova / .jdx / .csv / .txt / 图片等
│  (spectrum_parser) │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Mestrenova 处理    │  自动峰识别、化学位移、积分、耦合常数
│  (mestrenova_api)  │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  数据库查询         │  PubChem / SDBS / ChemSpider
│  (db_query)        │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  结构推导核心       │  分子式确定 → 不饱和度计算 → 官能团识别
│  (structure_elucidator)  │  骨架构建 → 候选结构生成与排序
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Spartan 量化计算   │  DFT/B3LYP/6-31G* / NMR 位移预测
│  (spartan_api)     │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Specdis 手性分析   │  ECD/ORD 计算谱与实验谱比对
│  (specdis_api)     │  确定绝对构型（置信度评分）
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  结构绘制与导出     │  自动选择可用后端：ChemDraw > RDKit > Chem3D > OpenBabel
│  (chemistry_drawing_api) │  PNG / SVG / SDF / MOL / PDB / CML / CDXML / SMILES
└────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows / macOS / Linux

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/king12q/Chemical-analyses-skills.git
cd Chemical-analyses-skills

# 安装核心依赖（RDKit 用于默认绘制）
pip install rdkit-pypi requests

# 可选：Windows 上使用 ChemDraw 绘制
pip install pywin32
```

### 使用示例

#### 示例 1：使用示例数据验证功能

```bash
python main_controller.py \
    --data sample_spectra.json \
    --output ./outputs
```

#### 示例 2：直接输入谱图数据

```bash
python main_controller.py \
    --formula C10H12O3 \
    --hnmr 8.00 6.93 4.34 3.86 1.38 \
    --cnmr 166.8 162.5 131.6 122.5 114.0 60.7 55.5 14.3 \
    --mass 180.0786 \
    --output ./outputs
```

#### 示例 3：交互式输入

```bash
python main_controller.py --interactive
```

#### 示例 4：指定 ChemDraw 作为绘制后端

```bash
python main_controller.py \
    --smiles "CCOC(=O)c1ccc(cc1)OC" \
    --name "Ethyl p-methoxybenzoate" \
    --backend CHEMDRAW \
    --output ./outputs
```

---

## 📁 输出文件说明

运行完成后，输出目录包含以下文件：

| 文件 | 说明 | 兼容软件 |
|------|------|---------|
| `report.md` | 综合分析报告 | Markdown 阅读器 |
| `structure_2D.png` | 2D 结构式（高分辨率） | Word / PPT / 网页 |
| `structure_2D.svg` | 2D 矢量图（无限放大） | LaTeX / InDesign |
| `structure_2D_labeled.png` | 带原子编号的结构图 | 用于 NMR 归属 |
| `structure.cdxml` | **ChemDraw XML 格式** | **ChemDraw** (双击打开) |
| `structure.sdf` | 3D 结构文件（含坐标） | Chem3D / Spartan / PyMOL |
| `structure.mol` | MDL MOL V2000 格式 | Gaussian / Maestro |
| `structure.pdb` | PDB 格式 | PyMOL / VMD / ChimeraX |
| `structure.cml` | Chemical Markup Language | Avogadro / Jmol |
| `structure.smiles` | SMILES 字符串 | 文本编辑器 |
| `nmr_assignments.csv` | NMR 信号归属表 | Excel / CSV 阅读器 |
| `confidence_scores.json` | 置信度评分 | JSON 阅读器 |

---

## ⚙️ 配置文件

编辑 `config.json` 自定义配置：

```json
{
  "software_paths": {
    "mestrenova": "",
    "spartan": "",
    "specdis": "",
    "chem3d": "",
    "chemdraw": "C:/Program Files/ChemOffice2024/ChemDraw/ChemDraw.exe"
  },
  "preferred_drawing_backend": "RDKIT",
  "use_online_database": true,
  "hmass_tolerance_ppm": 10.0
}
```

### 绘制后端选择

| 后端 | 适用场景 | 前提条件 |
|------|---------|---------|
| `CHEMDRAW` | 专业结构式，与 ChemDraw 风格一致 | Windows + ChemDraw |
| `RDKIT` | 默认推荐，纯 Python | `pip install rdkit-pypi` |
| `CHEM3D` | 高质量 3D 坐标 | Windows + Chem3D |
| `OPENBABEL` | 通用格式转换 | 安装 OpenBabel CLI |
| `TEXT` | 无图形软件时备用 | 始终可用 |

---

## 🧬 核心技术

### 天然药物化学推理流程

1. **分子式确定**：HRMS 精确质量 → 计算可能分子式 → 元素组成
2. **不饱和度计算**：Ω = (2C + 2 + N - H - X) / 2
3. **官能团识别**：
   - IR：~1710 cm⁻¹ (C=O), ~1600/1500 cm⁻¹ (芳环), ~3300 cm⁻¹ (O-H)
   - ¹³C-NMR：δ 160-220 (羰基), δ 100-160 (芳香), δ 0-100 (sp³ 碳)
   - ¹H-NMR：δ 6.5-8.5 (芳香), δ 4.5-6.5 (烯氢), δ 3.3-4.5 (连氧氢)
4. **结构片段组装**：基于 2D-NMR (COSY/HMBC/HMQC) 相关信号
5. **数据库匹配**：PubChem/SDBS → 候选结构 → 化学位移比对

### 置信度评估

| 因素 | 权重 |
|------|------|
| 数据完整性 | 30% |
| 分子式置信度 | 25% |
| 官能团识别 | 20% |
| 数据库支持 | 15% |
| 手性分析 | 10% |

---

## ❓ 常见问题

### Q: 提示 "未检测到图形绘制后端"

安装 RDKit 即可：
```bash
pip install rdkit-pypi
```

### Q: 如何配置 ChemDraw 路径？

在 `config.json` 中填写：
```json
{
  "software_paths": {
    "chemdraw": "C:/Program Files/ChemOffice2024/ChemDraw/ChemDraw.exe"
  },
  "preferred_drawing_backend": "CHEMDRAW"
}
```

### Q: 如何使用 ChemDraw COM 自动化？

安装 pywin32：
```bash
pip install pywin32
```

### Q: 数据不完整怎么办？

工具会自动评估并给出补测建议，例如：
- "建议补充 ¹³C-NMR 数据，提高碳骨架推断可靠性"
- "建议提供 HRMS 精确确定分子式"

---

## 📂 项目结构

```
Chemical-analyses-skills/
├── .gitignore              # Git 忽略文件
├── LICENSE                # MIT 开源协议
├── README.md              # 项目说明
├── SKILL.md               # TRAE Skill 定义文件
├── __init__.py            # Python 包初始化
├── config.json            # 配置文件
├── main_controller.py     # 主控制器（端到端自动化流程）
├── sample_spectra.json    # 示例谱图数据
├── test_syntax.py         # 语法检查工具
│
├── spectrum_parser.py      # [模块1] 谱图类型识别与解析
├── mestrenova_api.py       # [模块2] Mestrenova NMR 处理
├── db_query.py             # [模块3] PubChem/SDBS/ChemSpider 查询
├── structure_elucidator.py # [模块4] 结构推导核心引擎
├── spartan_api.py          # [模块5] Spartan 量化计算
├── specdis_api.py          # [模块6] Specdis 手性分析
└── chemistry_drawing_api.py # [模块7] 多后端绘制引擎
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📜 许可证

本项目基于 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [RDKit](https://www.rdkit.org/) - 开源化学信息学工具包
- [PubChem](https://pubchem.ncbi.nlm.nih.gov/) - NIH 化合物数据库
- [SDBS](https://sdbs.db.aist.go.jp/) - 日本 NIMC 有机化合物谱图数据库
- 所有参与测试和反馈的天然药物化学研究者

---

**Made with ❤️ by [king12q](https://github.com/king12q)**

*如果你觉得这个项目有帮助，请给个 ⭐ Star！*

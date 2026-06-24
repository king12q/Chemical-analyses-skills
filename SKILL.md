---
name: "spectrum-analyzer"
description: "AI智能识谱工具：自动识别谱图数据类型，调用本地专业软件(Mestrenova/Spartan/Specdis/ChemDraw/Chem3D)，查询PubChem/SDBS等数据库，模拟天然药物化学研究思路，全自动推导并绘制完整化合物结构（支持 ChemDraw / RDKit / Chem3D / OpenBabel 多后端绘制）。Invoke when user provides spectral data (NMR/IR/MS/UV/ECD) and asks for compound structure determination or automated spectral analysis."
---

# AI 智能识谱工具 (Spectrum Analyzer)

## 一、功能概述

本工具模拟**天然药物化学研究者的完整工作流程**，实现从谱图数据到化合物结构的全自动推导。核心能力包括：

- 自动识别谱图类型（¹H-NMR / ¹³C-NMR / IR / MS / UV / ECD / ORD）
- 调用本地专业软件（Mestrenova / Spartan / Specdis / **ChemDraw** / Chem3D）处理原始数据
- 自动查询 PubChem / SDBS / ChemSpider 等在线数据库
- 模拟天然药物化学研究者的推理思路，推导分子式、结构片段、候选结构
- 生成最终 **2D 结构式**（PNG / SVG / **CDXML 格式，用 ChemDraw 打开**）/ 3D 构型文件 / 完整推导报告
- **多后端绘制**：智能检测系统可用绘制工具（RDKit / ChemDraw / Chem3D / OpenBabel / Text 文本备份）

## 二、完整工作流程（天然药物化学研究思路）

```
输入谱图数据
      │
      ▼
┌────────────────────┐
│  数据类型识别      │  自动识别：¹H-NMR / ¹³C-NMR / DEPT / IR / MS / UV / ECD / ORD
│  (spectrum_parser) │  自动检测文件格式（.mnova / .sp / .jdx / .csv / 图片等）
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Mestrenova 处理   │  自动谱图分析：峰识别、化学位移、积分、耦合常数
│  (mestrenova_api)  │  输出：NMR 信号表（δ, 积分, J, 多重性）
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  数据库查询        │  PubChem → 分子式 / 精确质量 / 已知结构
│  (db_query)        │  SDBS    → 标准谱图比对 / 候选化合物
│                     │  ChemSpider → 结构检索 / 文献信息
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  结构推导核心      │  1. 分子式确定（高分辨 MS + 元素分析）
│  (structure_elucidator) │  2. 不饱和度计算 Ω = (2C+2+N-H-X)/2
│                     │  3. 结构片段识别（¹H-NMR 信号模式识别）
│                     │  4. 骨架构建（¹³C-NMR + 2D-NMR: COSY/HMBC/HMQC）
│                     │  5. 官能团与取代基定位
│                     │  6. 候选结构生成与排序（文献支持+化学合理性评分）
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Spartan 优化      │  分子力学预优化（MMFF/MM3）
│  (spartan_api)     │  量化计算（DFT/B3LYP/6-31G*）
│                     │  NMR 化学位移预测验证（GIAO）
│                     │  构象搜索（MD/Monte Carlo）
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Specdis 手性分析  │  ECD / ORD 计算谱（TD-DFT）
│  (specdis_api)     │  实验谱 vs 计算谱比对（R² 相关系数）
│                     │  Boltzmann 加权；绝对构型确定（置信度评分）
└─────────┬──────────┘
          │
          ▼
┌──────────────────────────┐
│  结构绘制（多后端智能选择）│  chemistry_drawing_api
│  (chemistry_drawing_api) │  ✓ RDKit（Python 库，无需额外安装）
│  优先后端：               │  ✓ ChemDraw（Windows COM 自动化）
│    1. ChemDraw            │  ✓ Chem3D（3D 坐标生成 / MMFF94 优化）
│    2. RDKit               │  ✓ OpenBabel（格式转换）
│    3. Chem3D              │  ✗ 不可用时 → 纯文本模式
│    4. OpenBabel           │
│    5. Text(文本备份)       │  生成文件：PNG / SVG / SDF / MOL / PDB / CML / CDXML / SMILES
└─────────┬──────────────────┘
          │
          ▼
    最终结果：
    ┌────────────────────────────────────────────┐
    │ 化合物名称 / 系统命名 / IUPAC                  │
    │ 分子式 / 精确分子量 / CAS号                    │
    │ 完整 2D 结构式 + 3D 构型图                     │
    │ 关键 NMR 信号归属表（含编号）                   │
    │ 绝对构型（含置信度评分，如有 ECD/ORD）         │
    │ 参考文献 / 数据库匹配信息                       │
    │ 整体置信度评分 + 数据补充建议                   │
    │ structure.cdxml（双击用 ChemDraw 打开编辑）   │
    └────────────────────────────────────────────┘
```

## 三、目录结构

```
.trae/skills/spectrum-analyzer/
├── SKILL.md                        # 本文件（技能定义与使用指南）
├── __init__.py                     # Python 包初始化
├── config.json                     # 配置文件（软件路径、API Key、绘制后端选择）
├── sample_spectra.json             # 示例谱图数据（可直接运行测试）
├── test_syntax.py                  # 语法检查工具
│
├── spectrum_parser.py              # [模块1] 谱图类型识别与数据解析
├── mestrenova_api.py               # [模块2] Mestrenova NMR 处理接口
├── db_query.py                     # [模块3] PubChem/SDBS/ChemSpider 在线查询
├── structure_elucidator.py         # [模块4] 化合物结构推导核心引擎
├── spartan_api.py                  # [模块5] Spartan 量化计算接口
├── specdis_api.py                  # [模块6] Specdis 手性光谱分析接口
├── chemistry_drawing_api.py        # [模块7] 综合绘制引擎（RDKit / ChemDraw / Chem3D / OpenBabel）
└── main_controller.py              # [主控] 端到端自动化流程（主入口）
```

## 四、配置文件 config.json

```jsonc
{
  "software_paths": {
    "mestrenova": "",
    "spartan": "",
    "specdis": "",
    "chem3d": "",
    "chemdraw": "",            // ← ChemDraw.exe 路径
    "chemdraw_exe": ""         // ← 备用 ChemDraw 路径
  },
  "api_keys": {
    "pubchem": "",
    "chemspider": ""
  },
  "preferred_drawing_backend": "RDKIT",   // ← 可选：CHEMDRAW / CHEM3D / OPENBABEL / TEXT
  "output_dir": "./outputs",
  "log_level": "INFO",
  "use_online_database": true,
  "max_candidates": 20,
  "hmass_tolerance_ppm": 10.0,
  "tutorial_mode": true
}
```

**绘制后端优先级说明**：

| 后端 | 适用场景 | 前提条件 |
|------|---------|---------|
| `CHEMDRAW` | 化学研究者的常用工具，生成专业级结构式 | Windows 系统 + 安装 ChemDraw（需 COM 自动化权限） |
| `RDKIT`    | 默认推荐，纯 Python，免安装依赖（需 pip install rdkit-pypi） | 仅需 Python |
| `CHEM3D`   | 需要高质量 3D 坐标文件（供 Spartan / GaussView 进一步计算） | Windows 系统 + 安装 Chem3D |
| `OPENBABEL`| 仅需通用化学格式转换（需安装 OpenBabel CLI） | 安装 openbabel 并在 PATH 中 |
| `TEXT`     | 无图形化软件可用，仍可生成 SMILES / MOL 文本 | 始终可用 |

> 未指定 `preferred_drawing_backend` 时，工具会**自动探测**可用后端并选择最优先者。
> 若只需要生成图片用在论文里，**RDKIT 已经足够**（会自动生成 PNG + SVG）。
> 若要获得可在 ChemDraw 中继续编辑的 `.cdxml` 文件，请配置 `chemdraw` 路径或将后端设为 `CHEMDRAW`。

## 五、快速开始（3 种常用方式）

### 方式 1：使用示例数据（推荐先跑这个验证功能）

```bash
python .trae/skills/spectrum-analyzer/main_controller.py \
    --data .trae/skills/spectrum-analyzer/sample_spectra.json \
    --output ./outputs
```

> **示例数据**：对甲氧基苯甲酸乙酯（Ethyl p-methoxybenzoate, C₁₀H₁₂O₃）
> 包含 ¹H-NMR / ¹³C-NMR / MS / IR / UV 全套数据。

### 方式 2：只提供化学位移和分子式（最简输入）

```bash
python .trae/skills/spectrum-analyzer/main_controller.py \
    --formula C10H12O2 \
    --hnmr 8.00 6.93 4.34 3.86 1.38 \
    --cnmr 166.8 162.5 131.6 122.5 114.0 60.7 55.5 14.3 \
    --mass 180.0786 \
    --backend CHEMDRAW \
    --output ./outputs
```

### 方式 3：交互式输入（适合临时分析）

```bash
python .trae/skills/spectrum-analyzer/main_controller.py --interactive
```

程序会依次询问：
- ¹H-NMR 化学位移（每行一个，空行结束）
- ¹³C-NMR 化学位移（每行一个，空行结束）
- 高分辨质谱精确质量（可选）

## 六、在 TRAE 中使用的自然语言调用

### 例 1：提供文件路径

```
请帮我分析这个化合物的谱图并推导结构：

谱图文件位置：
- D:/spectra/sample_A_1H_NMR.mnova
- D:/spectra/sample_A_13C_NMR.mnova
- D:/spectra/sample_A_HRMS.txt
- D:/spectra/sample_A_IR.jdx

请使用 spectrum-analyzer 工具，将结果输出到 D:/spectra/outputs/A/ 目录。
优先使用 ChemDraw 生成结构式。
```

### 例 2：直接提供数据

```
请帮我分析：
分子式 C10H12O3
¹H-NMR (δ ppm): 8.00 (2H, d, J=8.8), 6.93 (2H, d, J=8.8), 4.34 (2H, q, J=7.1),
                 3.86 (3H, s), 1.38 (3H, t, J=7.1)
¹³C-NMR (δ ppm): 166.8, 162.5, 131.6, 122.5, 114.0, 60.7, 55.5, 14.3
HRMS: m/z 180.0786 [M]⁺

生成报告到 ./outputs/。
```

### 例 3：只给关键信息，让工具自动推断

```
请帮我推断一个未知化合物结构：
HRMS 精确质量 180.0786 Da
¹H-NMR 5 组峰，δ 8.00 (2H), 6.93 (2H), 4.34 (2H), 3.86 (3H), 1.38 (3H)
¹³C-NMR 8 个碳信号，含一个 δ 166.8 的羰基碳
含 4 个芳香氢，提示对位取代苯环
IR: 1710 cm⁻¹ (C=O), 1605/1510 cm⁻¹ (芳环)
```

### 例 4：已确定结构，只需要用 ChemDraw 绘制

```
化合物：对甲氧基苯甲酸乙酯（Ethyl p-methoxybenzoate）
SMILES：CCOC(=O)c1ccc(cc1)OC

请生成一份完整结构文件（CDXML + PNG + SDF + MOL），
准备用于论文投稿和后续量化计算。
输出目录：./outputs/paper-ready/
```

## 七、支持的输入格式

| 数据类型 | 支持格式 | 说明 |
|---------|---------|-----|
| ¹H-NMR | .mnova, .jdx, .csv, .txt | 可接受原始数据或已处理谱图 |
| ¹³C-NMR | .mnova, .jdx, .csv, .txt | 包括 DEPT-90, DEPT-135 |
| 2D-NMR | .mnova, .sp | COSY, HMBC, HMQC, NOESY |
| MS / HRMS | .mnova, .txt, .csv | 低分辨 / 高分辨质谱 |
| IR | .jdx, .csv, .txt, .mnova | 红外光谱 |
| UV | .csv, .txt, .mnova | 紫外-可见光谱 |
| ECD / ORD | .txt, .csv, .jdx | 圆二色谱 / 旋光色散 |

## 八、输出结果说明

完成分析后，将在输出目录生成以下文件：

```
outputs/
├── report.md                    # 综合分析报告（核心结论 + 信号表 + 候选列表 + 建议）
│
├── structure_2D.png             # 2D 结构式图像（高分辨率 PNG）
├── structure_2D.svg             # 2D 结构式矢量图（可无限放大，用于论文/专利）
├── structure_2D_labeled.png     # 带原子编号的 2D 图（用于 NMR 信号归属）
│
├── structure.sdf                # 3D 结构文件（所有化学软件兼容，含 3D 坐标）
├── structure.mol                # MDL MOL V2000 格式
├── structure.cdxml              # ★ ChemDraw XML（双击即可用 ChemDraw 打开编辑）★
├── structure.cml                # Chemical Markup Language（CML，XML 标准）
├── structure.pdb                # PDB 格式（生物信息学 / 分子对接 / PyMOL）
├── structure.smiles             # SMILES 字符串（文本格式）
│
├── nmr_assignments.csv          # NMR 信号归属表
├── confidence_scores.json       # 置信度评分 + 改进建议
└── spectrum_raw.json            # 原始解析数据备份
```

### 特别说明：ChemDraw 集成

- **`structure.cdxml`** 是 ChemDraw 原生 XML 格式，可双击用 ChemDraw 直接打开。
- 打开后可以：调整布局 / 添加编号 / 优化键角 / 输出到论文 / 导出 MS Office 对象。
- 如果本地已安装 ChemDraw 且配置了路径，工具会尝试通过 COM 自动化直接调用 ChemDraw 绘图，
  这样生成的图像与用户手工在 ChemDraw 中绘制的风格完全一致。
- 即使本地没有 ChemDraw，工具也会生成标准 CDXML 文件，用户在任何有 ChemDraw 的电脑上均可打开。

### 其他格式的兼容性

| 文件 | 兼容软件 | 用途 |
|-----|---------|-----|
| `.png / .svg` | Word, PPT, LaTeX, InDesign, 网页 | 论文插图、报告 |
| `.cdxml`      | **ChemDraw, ChemOffice 2020-2024** | 继续编辑、再加工 |
| `.sdf / .mol` | Chem3D, Spartan, Gaussian, GaussView, Maestro, PyMOL, VMD, Discovery Studio | 进一步量化计算 / 分子对接 / 分子动力学 |
| `.pdb`        | PyMOL, VMD, ChimeraX | 生物大分子 / 对接可视化 |
| `.cml`        | Avogadro, Jmol, ChemDraw 18+ | XML 化学数据交换 |

## 九、核心技术原理

### 9.1 天然药物化学推理流程

1. **分子式确定**：HRMS 精确质量 → 计算可能分子式 → 元素组成（C/H/O/N/S/Cl/Br）
2. **不饱和度计算**：Ω = (2C + 2 + N - H - X) / 2，判断双键/苯环/稠环数量
3. **官能团识别**：
   - IR：~1710 cm⁻¹ 羰基 / ~1600/1500 cm⁻¹ 芳环 / ~3300 cm⁻¹ 羟基
   - ¹³C-NMR：δ 160-220 羰基 / δ 100-160 芳香/烯碳 / δ 0-100 sp³ 碳
   - ¹H-NMR：δ 6.5-8.5 芳香氢 / δ 4.5-6.5 烯氢 / δ 3.3-4.5 连氧碳氢
4. **结构片段组装**：基于 2D-NMR (COSY/HMBC/HMQC) 相关信号
5. **数据库匹配**：PubChem/SDBS 分子式 → 候选结构 → 化学位移比对

### 9.2 多后端绘制引擎（chemistry_drawing_api）

```
输入 SMILES / 分子式
      │
      ▼
┌────────────────────┐
│  探测可用绘制后端   │ 1. 检查 config.json 配置
│  (Backend Detection)│ 2. 检查常见安装路径（Program Files/ChemOffice*）
│                     │ 3. 检查 Windows Registry (ChemDraw.Document)
│                     │ 4. 检查 Python 是否导入 rdkit
│                     │ 5. 检查 openbabel 命令是否在 PATH
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  2D 坐标生成       │ 优先使用用户首选后端：
│  (2D Layout)       │ • RDKit：GetDrawingText() / rdMolDraw2D
│                     │ • ChemDraw：COM / CDXML 生成
│                     │ • OpenBabel：obabel --gen2D
│                     │ • Text：ASCII 文本 SMILES
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  3D 坐标生成       │ • RDKit ETKDG 或 MMFF94 优化
│  (3D Geometry)     │ • OpenBabel obabel -O3 --gen3D
│                     │ • 纯文本模式：保留 2D 坐标到 SDF
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  多格式导出        │ PNG / SVG / MOL / SDF / PDB / CML / CDXML / SMILES
│  (Multi-Export)    │ 同步写入所有格式文件
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  标注 & 编号       │ 生成带原子编号的 labeled PNG 用于 NMR 归属
│  (Atom Numbering)  │
└────────────────────┘
```

### 9.3 置信度评估

置信度评估由以下因素加权得到：
- **数据完整性**（30%）：是否有完整的 ¹H/¹³C/HRMS/IR 数据
- **分子式置信度**（25%）：HRMS 匹配精度 + 数据库命中数量
- **官能团识别**（20%）：识别到的官能团数量与化学合理性
- **数据库支持**（15%）：PubChem/SDBS 匹配结果数量
- **手性分析**（10%）：ECD/ORD 配置分析

## 十、常见问题

### Q1: 工具提示 "未检测到图形绘制后端"

**A**: 这是正常的 — 已自动降级为文本模式，会生成 `structure.smiles` 和文本报告。
要获得图形化结构，以下任一方式均可：
```bash
pip install rdkit-pypi          # 方式一：安装 RDKit（推荐，纯 Python）
# 或在 Windows 上安装 ChemDraw/Chem3D，并在 config.json 填写路径
```

### Q2: 生成的 CDXML 用 ChemDraw 打开后，图像风格不太对

**A**: 首次使用时建议在 ChemDraw 中执行一次 `File → Save As` 保存为 `.cdx` 二进制格式，
这样可以确保 ChemDraw 内部样式完全生效。或在 config.json 设置 `"preferred_drawing_backend": "CHEMDRAW"`，
让工具直接通过 COM 调用 ChemDraw 生成图像。

### Q3: 本地没有 Chem3D，会影响 3D 结构文件吗？

**A**: 不会。RDKit 或 OpenBabel 会自动用 ETKDG/MMFF94 方法生成 3D 坐标，输出 `.sdf/.pdb/.mol`
供 Spartan、Gaussian、PyMOL、GaussView 等后续计算使用。

### Q4: 数据不完整（只有 ¹H-NMR，没有 ¹³C 和 MS）

**A**: 工具会在 `confidence_scores.json` 中明确标注哪些数据缺失，并在 `report.md` 中给出具体的补测建议，如 "¹³C-NMR 缺失，建议补测以确认碳骨架"。

### Q5: 如何在 Windows 上配置 ChemDraw 路径？

**A**: 在 config.json 中填写：
```json
{
  "software_paths": {
    "chemdraw": "C:/Program Files/ChemOffice2024/ChemDraw/ChemDraw.exe",
    "chemdraw_exe": ""
  },
  "preferred_drawing_backend": "CHEMDRAW"
}
```
保存后重新运行主程序即可。工具会自动检测路径是否存在，并优先使用 ChemDraw 进行绘制。

### Q6: 提示 "pywin32 未安装"

**A**: `pywin32` 是 Python 调用 Windows COM 自动化的库（用于直接驱动 ChemDraw）。
如需要使用 ChemDraw COM 自动化，执行：
```bash
pip install pywin32
```
如未安装，工具仍能生成标准的 CDXML 文件，但无法直接调用 ChemDraw 图形化渲染。

## 十一、版本信息

- spectrum-analyzer v1.1.0
- 新增：ChemDraw 集成（CDXML 输出、COM 自动化探测、多后端优先级）
- 新增：chemistry_drawing_api 多后端绘制引擎
- 新增：PDB / CML 格式输出
- 改进：交互式输入、置信度评分系统

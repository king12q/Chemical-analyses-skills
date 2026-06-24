# 🧪 Chemical-analyses-skills

[English](README.md) | **中文**

> AI 智能识谱工具 — 通过 GUI 自动化直接控制化学软件（Mestrenova 15 / ChemDraw 2022 / Spartan '14）

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-yellow.svg)](https://github.com/king12q/Chemical-analyses-skills)

---

## ✨ 功能特性

### 🤖 GUI 自动化 — 直接控制化学软件

本工具通过 **GUI 自动化** 直接操作电脑上的化学软件，实现真正的自动化工作流程：

| 软件 | 版本 | 支持的功能 |
|------|------|-----------|
| **Mestrenova** | 15+ | 自动打开谱图、自动峰识别、自动积分、导出数据/图片 |
| **ChemDraw** | 2022+ | 从 SMILES 绘制结构、自动美化、导出多格式（CDXML/PNG/SVG/SDF） |
| **Spartan** | '14+ | 几何优化、NMR 化学位移预测、ECD 手性光谱计算 |

### 🌟 核心能力

- 🔬 **全自动谱图分析**：自动峰识别 + 积分 + 数据导出
- 🎨 **专业结构绘制**：从 SMILES 自动生成高质量结构图
- 🧪 **量化计算**：几何优化 + NMR/ECD 光谱预测
- 🌐 **数据库查询**：PubChem / SDBS / ChemSpider 辅助结构确定
- 📊 **多格式输出**：PNG / SVG / CDXML / SDF / MOL / PDB

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# GUI 自动化核心依赖
pip install pywinauto pyautogui pyperclip Pillow

# 化学信息学依赖
pip install rdkit-pypi requests
```

### 2. 配置软件路径

编辑 `config.json`：

```json
{
  "software_paths": {
    "mestrenova": "C:/Program Files/MestReNova/MestReNova.exe",
    "chemdraw": "C:/Program Files/ChemOffice2022/ChemDraw/ChemDraw.exe",
    "spartan": "C:/Program Files/Wavefunction/Spartan14/Spartan14.exe"
  }
}
```

### 3. 命令行使用

```bash
# 检查软件可用性
python main_controller_gui.py --check

# 分析谱图
python main_controller_gui.py --analyze spectra/sample.mnova

# 绘制结构
python main_controller_gui.py --draw --smiles "CCOC(=O)c1ccc(cc1)OC"

# 完整工作流程
python main_controller_gui.py --workflow spectra/sample.mnova
```

---

## 📁 项目结构

```
Chemical-analyses-skills/
├── config.json                     # 配置文件
├── README.md                      # 本文件
├── SKILL.md                       # 详细文档
│
├── gui_automation.py              # GUI 自动化核心
├── mestrenova_gui.py              # Mestrenova 15 操作
├── chemdraw_gui.py                # ChemDraw 2022 操作
├── spartan_gui.py                 # Spartan '14 操作
├── main_controller_gui.py         # 统一控制器 ⭐
│
├── core_modules/                  # 核心分析模块
│   ├── spectrum_parser.py
│   ├── structure_elucidator.py
│   ├── db_query.py
│   └── ...
│
└── LICENSE                        # MIT 协议
```

---

## 🎯 使用示例

### 示例 1：分析 NMR 谱图

```python
from main_controller_gui import ChemicalSoftwareController

controller = ChemicalSoftwareController()

# 检查软件
controller.check_software_availability()

# 分析谱图
result = controller.analyze_spectrum(
    spectrum_file="D:/spectra/sample.mnova",
    output_dir="D:/outputs/analysis"
)

print(f"识别峰数: {len(result['peaks'])}")
print(f"峰数据: {result['peaks_csv']}")
```

### 示例 2：绘制分子结构

```python
result = controller.draw_structure(
    smiles="CCOC(=O)c1ccc(cc1)OC",
    output_dir="D:/outputs/structures",
    format="all",
    add_numbers=True
)

print(f"输出格式: {list(result['output_files'].keys())}")
# ['png', 'svg', 'cdxml', 'sdf', 'mol']
```

### 示例 3：完整工作流程

```bash
python main_controller_gui.py --workflow spectra/sample.mnova
```

自动完成：
1. 启动 Mestrenova → 打开谱图 → 峰识别 → 积分 → 导出数据
2. 分析峰数据 → 推导结构
3. 启动 ChemDraw → 绘制结构 → 导出多格式
4. 生成完整分析报告

---

## 🔧 支持的操作

### Mestrenova 15

| 功能 | 快捷键 |
|------|--------|
| 打开文件 | `Ctrl+O` |
| 自动峰识别 | `Ctrl+Shift+G` |
| 自动积分 | `Ctrl+Shift+I` |
| 适应窗口 | `Ctrl+0` |
| 导出 CSV | `Ctrl+Shift+S` |

### ChemDraw 2022

| 功能 | 快捷键 |
|------|--------|
| 新建文档 | `Ctrl+N` |
| 从 SMILES 绘制 | `Ctrl+E` → 粘贴 SMILES → Enter |
| 美化结构 | `Ctrl+Shift+K` |
| 添加原子编号 | `Alt+S` → `A` → `N` |
| 导出 CDXML | `Ctrl+Shift+S` |

### Spartan '14

| 功能 | 快捷键 |
|------|--------|
| 导入分子 | `Ctrl+O` |
| 几何优化 | `Ctrl+Shift+E` |
| NMR 计算 | `Ctrl+Shift+E` |
| ECD 计算 | `Ctrl+Shift+E` |

---

## ❓ 常见问题

### Q: 如何调试 GUI 操作？

```python
# 截图调试
controller.gui_core.take_screenshot("debug.png")

# 查看窗口信息
info = controller.gui_core.get_window_info()
```

### Q: 操作失败怎么办？

1. 确保软件窗口在前台
2. 增加延时：`time.sleep(2)`
3. 检查快捷键是否与软件版本匹配

---

## 📜 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

**Made with ❤️ by [king12q](https://github.com/king12q)**

*如果你觉得这个项目有帮助，请给个 ⭐ Star！*

---
name: "spectrum-analyzer"
description: "AI智能识谱工具（GUI自动化版）：通过GUI自动化直接操作Mestrenova 15/ChemDraw 2022/Spartan '14等化学软件，自动完成谱图分析、峰识别、积分、NMR预测、结构绘制等任务。支持通过快捷键和菜单操作模拟人工操作，实现真正的软件联动。Invoke when user needs to analyze NMR/IR/MS spectra or generate chemical structures using installed software."
---

# AI 智能识谱工具 (Spectrum Analyzer) — GUI 自动化版

## 一、功能概述

本工具是**GUI 自动化版本的智能识谱工具**，通过直接操作电脑上的化学软件来实现真实的自动化分析，而不仅仅是模拟接口。

### 核心能力

- 🤖 **GUI 自动化操作**：通过模拟键盘快捷键和菜单操作，直接控制化学软件
- 📊 **Mestrenova 15**：自动打开谱图、自动峰识别、自动积分、导出数据
- 🎨 **ChemDraw 2022**：从 SMILES 自动绘制结构、自动美化、自动导出多格式
- 🧪 **Spartan '14**：几何优化、NMR 化学位移预测、ECD 手性光谱计算
- 🌐 **数据库查询**：自动查询 PubChem / SDBS / ChemSpider
- 🧬 **结构推导**：模拟天然药物化学研究者的推理思路
- 📈 **多格式输出**：PNG / SVG / CDXML / SDF / MOL / PDB

### 与传统版本的区别

| 功能 | 传统版本 | GUI 自动化版本 |
|------|---------|--------------|
| 软件控制方式 | API 接口模拟 | **真实 GUI 操作** |
| 需要安装软件 | 可选 | **必须安装** |
| 操作准确性 | 依赖 API 稳定性 | **与人工操作一致** |
| 适用场景 | 快速分析 | **生产环境/论文数据** |

## 二、工作流程

```
用户请求（如"分析 NMR 谱图"）
        │
        ▼
┌─────────────────────────┐
│  Agent 分析任务需求     │  判断需要使用哪些软件
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  ChemicalSoftwareController │  统一控制器
│  (main_controller_gui)  │  管理所有软件的生命周期
└───────────┬─────────────┘
            │
    ┌───────┼───────┬────────────┐
    │       │       │            │
    ▼       ▼       ▼            ▼
Mestrenova ChemDraw Spartan    Specdis
  15       2022     '14
    │       │       │            │
    ▼       ▼       ▼            ▼
峰识别   结构绘制  量化计算    手性分析
积分     美化      NMR预测
导出     导出      ECD计算
```

## 三、快速开始

### 1. 安装依赖

```bash
# GUI 自动化核心依赖
pip install pywinauto pyautogui pyperclip Pillow

# 化学信息学依赖
pip install rdkit-pypi requests

# 可选：增强功能
pip install opencv-python numpy pandas
```

### 2. 配置软件路径

编辑 `config.json`：

```jsonc
{
  "software_paths": {
    "mestrenova": "C:/Program Files/MestReNova/MestReNova.exe",
    "chemdraw": "C:/Program Files/ChemOffice2022/ChemDraw/ChemDraw.exe",
    "spartan": "C:/Program Files/Wavefunction/Spartan14/Spartan14.exe"
  },
  "output_dir": "./outputs",
  "use_online_database": true
}
```

### 3. 命令行使用

```bash
# 检查软件可用性
python main_controller_gui.py --check

# 分析谱图（Mestrenova）
python main_controller_gui.py --analyze spectra/sample.mnova

# 绘制结构（ChemDraw）
python main_controller_gui.py --draw --smiles "CCOC(=O)c1ccc(cc1)OC"

# 完整工作流程
python main_controller_gui.py --workflow spectra/sample.mnova

# 关闭所有软件
python main_controller_gui.py --close-all
```

## 四、支持的软件与操作

### 4.1 Mestrenova 15

| 功能 | 实现方式 | 快捷键/菜单 |
|------|---------|------------|
| 打开文件 | 文件对话框 | `Ctrl+O` |
| 自动峰识别 | 命令执行 | `Ctrl+Shift+G` |
| 自动积分 | 命令执行 | `Ctrl+Shift+I` |
| 导出峰列表 | 另存为 | `Ctrl+Shift+S` → 选择 CSV |
| 导出图片 | 导出图像 | `Alt+F` → `E` → `I` |
| 美化谱图 | 适应窗口 | `Ctrl+0` |
| 缩放 | 快捷键 | `Ctrl++` / `Ctrl+-` |

### 4.2 ChemDraw 2022

| 功能 | 实现方式 | 快捷键/菜单 |
|------|---------|------------|
| 新建文档 | 新建命令 | `Ctrl+N` |
| 从 SMILES 绘制 | 自动化结构绘制 | `Ctrl+E` → 粘贴 SMILES → Enter |
| 美化结构 | 布局美化 | `Ctrl+Shift+K` |
| 添加原子编号 | 菜单操作 | `Alt+S` → `A` → `N` |
| 导出 CDXML | 另存为 | `Ctrl+Shift+S` → 选择 CDXML |
| 导出 PNG | 另存为 | `Ctrl+Shift+S` → 选择 PNG |
| 导出 SVG | 另存为 | `Ctrl+Shift+S` → 选择 SVG |
| 导出 SDF | 另存为 | `Ctrl+Shift+S` → 选择 SDF |

### 4.3 Spartan '14

| 功能 | 实现方式 | 快捷键/菜单 |
|------|---------|------------|
| 导入分子 | 文件打开 | `Ctrl+O` |
| 几何优化 | 计算设置 | `Ctrl+Shift+E` → Optimize |
| NMR 计算 | 计算设置 | `Ctrl+Shift+E` → NMR |
| ECD 计算 | 计算设置 | `Ctrl+Shift+E` → ECD |
| 导出结构 | 另存为 | `Ctrl+Shift+S` |
| 导出光谱数据 | 导出 | `Alt+F` → `E` |

## 五、目录结构

```
spectrum-analyzer/
├── SKILL.md                      # 本文件
├── config.json                   # 配置文件
├── README.md                     # 使用说明
│
├── core_modules/                 # 核心分析模块
│   ├── spectrum_parser.py        # 谱图类型识别
│   ├── structure_elucidator.py   # 结构推导引擎
│   ├── db_query.py               # 数据库查询
│   └── ...
│
├── gui_modules/                  # GUI 自动化模块 ⭐
│   ├── gui_automation.py         # 核心自动化引擎
│   ├── mestrenova_gui.py          # Mestrenova 15 操作
│   ├── chemdraw_gui.py            # ChemDraw 2022 操作
│   ├── spartan_gui.py             # Spartan '14 操作
│   └── main_controller_gui.py     # 统一控制器 ⭐
│
└── example_usage.py              # 使用示例
```

## 六、使用示例

### 示例 1：分析 NMR 谱图

```python
from main_controller_gui import ChemicalSoftwareController

controller = ChemicalSoftwareController()

# 检查软件可用性
status = controller.check_software_availability()
print(f"Mestrenova: {'可用' if status['mestrenova'] else '不可用'}")

# 分析谱图
result = controller.analyze_spectrum(
    spectrum_file="D:/spectra/sample.mnova",
    output_dir="D:/outputs/analysis"
)

print(f"成功: {result['success']}")
print(f"识别峰数: {len(result['peaks'])}")
print(f"峰数据: {result['peaks_csv']}")
print(f"谱图图片: {result['spectrum_image']}")
```

### 示例 2：绘制分子结构

```python
# 从 SMILES 绘制
result = controller.draw_structure(
    smiles="CCOC(=O)c1ccc(cc1)OC",
    output_dir="D:/outputs/structures",
    format="all",  # 生成所有格式
    add_numbers=True
)

print(f"输出文件: {list(result['output_files'].keys())}")
# ['png', 'svg', 'cdxml', 'sdf', 'mol']
```

### 示例 3：NMR 预测计算

```python
# 完整 NMR 预测工作流程
result = controller.run_nmr_prediction(
    input_mol="CCOC(=O)c1ccc(cc1)OC",
    output_dir="D:/outputs/nmr_calculation",
    method="DFT",
    basis="6-311G*",
    solvent="chloroform"
)
```

### 示例 4：Agent 自然语言调用

```
用户：请帮我分析 D:/spectra/compound_A.mnova 这个 NMR 谱图，
      然后根据分析结果推导可能的结构，并画出结构图。

Agent 执行：
  1. 启动 Mestrenova 15
  2. 打开谱图文件
  3. 自动峰识别和积分
  4. 导出峰数据
  5. 分析峰数据，推导结构
  6. 启动 ChemDraw 2022
  7. 绘制推导出的结构
  8. 导出多种格式（PNG、CDXML、SDF）
  9. 生成完整分析报告
```

## 七、Agent 调用接口

### ChemicalSoftwareController 方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `check_software_availability()` | 检查软件可用性 | - |
| `launch_software(name)` | 启动指定软件 | name: "mestrenova"/"chemdraw"/"spartan" |
| `analyze_spectrum(file)` | 分析谱图 | file: 谱图文件路径 |
| `draw_structure(smiles)` | 绘制结构 | smiles: SMILES 字符串 |
| `run_nmr_prediction(mol)` | NMR 预测 | mol: 分子结构 |
| `full_analysis_workflow(file)` | 完整工作流程 | file: 谱图文件路径 |

### MestrenovaGUI 方法

| 方法 | 说明 | 快捷键 |
|------|------|--------|
| `open_file(path)` | 打开文件 | `Ctrl+O` |
| `auto_pick_peaks()` | 自动峰识别 | `Ctrl+Shift+G` |
| `auto_integrate()` | 自动积分 | `Ctrl+Shift+I` |
| `export_peaks_to_csv(path)` | 导出峰列表 | - |
| `export_spectrum_image(path)` | 导出谱图图片 | - |
| `fit_to_window()` | 适应窗口 | `Ctrl+0` |

### ChemDrawGUI 方法

| 方法 | 说明 | 快捷键 |
|------|------|--------|
| `draw_from_smiles(smiles)` | 从 SMILES 绘制 | `Ctrl+E` |
| `clean_up_structure()` | 美化结构 | `Ctrl+Shift+K` |
| `add_atom_numbers()` | 添加原子编号 | `Alt+S` → `A` → `N` |
| `export_cdxml(path)` | 导出 CDXML | `Ctrl+Shift+S` |
| `export_png(path)` | 导出 PNG | `Ctrl+Shift+S` |
| `export_svg(path)` | 导出 SVG | `Ctrl+Shift+S` |

## 八、常见问题

### Q1: 提示 "软件未找到"

**A**: 确保软件已安装，并在 `config.json` 中配置正确路径：

```json
{
  "software_paths": {
    "mestrenova": "C:/Program Files/MestReNova/MestReNova.exe",
    "chemdraw": "C:/Program Files/ChemOffice2022/ChemDraw/ChemDraw.exe"
  }
}
```

### Q2: GUI 操作不准确或失败

**A**: 可能的原因和解决方案：

1. **窗口未获得焦点**：确保目标窗口在前台
2. **操作速度太快**：增加 `time.sleep()` 延时
3. **软件版本差异**：检查快捷键是否与版本匹配
4. **屏幕分辨率**：确保屏幕分辨率一致，避免硬编码坐标

### Q3: 如何调试 GUI 操作？

**A**: 使用以下方法调试：

```python
# 截图调试
controller.gui_core.take_screenshot("debug.png")

# 查看当前窗口信息
info = controller.gui_core.get_window_info()
print(f"标题: {info.title}")
print(f"位置: {info.rect}")

# 查看鼠标位置
pos = controller.gui_core.get_current_mouse_position()
print(f"鼠标: {pos}")
```

### Q4: 如何添加新的软件支持？

**A**: 参考现有的 `xxx_gui.py` 模块，创建新模块：

1. 创建 `newsoftware_gui.py`
2. 继承 `GUIAutomation` 类
3. 实现常用操作的快捷键方法
4. 在 `main_controller_gui.py` 中集成

### Q5: 计算任务如何异步执行？

**A**: Spartan 等量化计算任务耗时较长，建议：

```python
# 不等待计算完成，立即返回
result = controller.run_nmr_prediction(
    input_mol="CCOC(=O)c1ccc(cc1)OC",
    wait_for_complete=False  # 不等待
)

# Agent 可以同时执行其他任务
# 用户可通过 Spartan's GUI 监控计算进度
```

## 九、技术原理

### 9.1 GUI 自动化架构

```
┌─────────────────────────────────────────┐
│     ChemicalSoftwareController          │  统一调度器
│     - 软件生命周期管理                    │  - 启动/关闭软件
│     - 任务分配                          │  - 状态跟踪
└───────────────┬─────────────────────────┘
                │
┌───────────────┴─────────────────────────┐
│          GUIAutomation                 │  核心自动化引擎
│  - 键盘模拟 (pywinauto/pyautogui)       │  - 窗口管理
│  - 鼠标操作                             │  - 剪贴板
│  - 菜单导航                             │  - 截图
└───────────────┬─────────────────────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
Mestrenova  ChemDraw   Spartan
 GUI 类      GUI 类    GUI 类
```

### 9.2 快捷键映射机制

```python
# 统一转换为 pywinauto 格式
def press_keys(self, *keys):
    key_str = ""
    for key in keys:
        if key.lower() == "ctrl":
            key_str += "^"  # pywinauto: Ctrl = ^
        elif key.lower() == "alt":
            key_str += "%"  # pywinauto: Alt = %
        elif key.lower() == "shift":
            key_str += "+"  # pywinauto: Shift = +
        else:
            key_str += key
    
    send_keys(key_str)  # pywinauto 发送按键
```

### 9.3 稳定性保障

1. **超时机制**：每个操作都有超时保护
2. **状态检查**：操作前后检查软件状态
3. **错误恢复**：失败时尝试备用方案
4. **日志记录**：完整记录操作序列便于调试

## 十、版本信息

- spectrum-analyzer v2.0.0 (GUI 自动化版)
- 新增：GUI 自动化模块，真正的软件控制
- 新增：Mestrenova 15 / ChemDraw 2022 / Spartan '14 支持
- 新增：`main_controller_gui.py` 统一控制器
- 新增：Agent 调用接口，自然语言操作软件

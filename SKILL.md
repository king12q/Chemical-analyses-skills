---
name: "spectrum-analyzer"
description: "AI智能识谱工具（GUI自动化版）：通过GUI自动化直接操作电脑上的化学软件（Mestrenova 15 / ChemDraw 2022 / Spartan '14），自动打开谱图文件、峰识别、积分、导出数据、推导结构、绘制化合物结构图。用户提供谱图文件后，Agent必须启动软件用GUI操作完成所有分析，不能要求用户手动提供数据。核心入口文件：spectrum_analyzer.py，只有3个函数：analyze_spectrum(), draw_structure(), check_software()。Invoke when user provides spectral data files (.mnova, .jdx, .csv, etc.) and asks for compound structure determination or spectral analysis."
---

# 🚀 第零步：直接复制下面的代码用！

**【最重要！】不要自己写代码解析 .mnova！直接调用这个函数！**

```python
# 就一行导入
from spectrum_analyzer import analyze_spectrum, draw_structure, check_software

# 【最常用】分析 .mnova 谱图
result = analyze_spectrum(r"C:\路径\你的文件.mnova")
# result 里有 peaks_csv, spectrum_image, output_dir

# 画结构图
result = draw_structure("CCOC(=O)c1ccc(cc1)OC")
# result 里有各种格式的结构图

# 检查软件
result = check_software()
```

**就这 3 个函数！不要自己造轮子！**

---

# AI 智能识谱工具 — GUI 自动化版

## ⚠️ 核心原则（Agent 必须遵守）

**本 Skill 的核心能力是 GUI 自动化操作真实化学软件，不是模拟或代码解析。**

当用户提供谱图文件（.mnova 等）时：
- ✅ **正确做法**：启动 Mestrenova → 打开文件 → 自动峰识别 → 自动积分 → 导出数据 → 继续分析
- ❌ **错误做法**：告诉用户 .mnova 是二进制无法解析，要求用户手动提供化学位移数据
- ❌ **绝对禁止**：因为"没有命令行接口"就放弃，转而向用户要数据

---

## 一、功能概述

本工具通过 **GUI 自动化**（pywinauto + pyautogui）直接控制电脑上安装的化学软件，模拟人工操作完成完整的谱图分析流程。

### 支持的软件

| 软件 | 版本 | 功能 |
|------|------|------|
| **Mestrenova** | 15+ | 打开 .mnova 文件、自动峰识别、自动积分、导出峰列表、导出谱图图片 |
| **ChemDraw** | 2022+ | 从 SMILES 绘制结构、自动美化、原子编号、导出 CDXML/PNG/SVG/SDF |
| **Spartan** | '14+ | 几何优化、NMR 化学位移预测、ECD 手性光谱计算 |

### 支持的输入格式

| 格式 | 处理方式 |
|------|---------|
| `.mnova` | **用 Mestrenova GUI 打开** → 自动峰识别 → 导出数据 |
| `.jdx` / `.dx` | 用 Mestrenova 打开处理 |
| `.csv` / `.txt` | 直接解析文本数据 |
| SMILES 字符串 | 用 ChemDraw 绘制结构图 |

---

## 二、Agent 标准工作流程（必须按此执行）

### 场景 1：用户提供 .mnova 谱图文件

**Agent 必须执行以下步骤，不能跳过任何一步，不能向用户要数据：**

```
用户上传 .mnova 文件
    │
    ▼
[Step 1] 检查软件可用性
  调用：controller.check_software_availability()
  - 如果 Mestrenova 不可用 → 提示用户安装或配置路径
  - 如果可用 → 继续
    │
    ▼
[Step 2] 启动 Mestrenova 并打开文件
  调用：controller.analyze_spectrum(spectrum_file="路径/文件.mnova")
  这个函数内部会自动完成：
  - 启动 Mestrenova 15
  - 打开谱图文件
  - 自动峰识别 (Ctrl+Shift+G)
  - 自动积分 (Ctrl+Shift+I)
  - 导出峰列表到 CSV
  - 导出谱图图片
    │
    ▼
[Step 3] 分析峰数据
  - 从导出的 peaks.csv 读取峰数据
  - 识别核类型（1H / 13C 等）
  - 计算分子式（如有 HRMS 数据）
    │
    ▼
[Step 4] 数据库查询（可选）
  - 查询 PubChem / SDBS 获取候选结构
    │
    ▼
[Step 5] 结构推导
  - 不饱和度计算
  - 官能团识别
  - 候选结构排序
    │
    ▼
[Step 6] 用 ChemDraw 绘制结构图
  调用：controller.draw_structure(smiles="...", format="all")
  - 启动 ChemDraw 2022
  - 从 SMILES 绘制结构 (Ctrl+E)
  - 自动美化 (Ctrl+Shift+K)
  - 添加原子编号
  - 导出 CDXML / PNG / SVG / SDF
    │
    ▼
[Step 7] 生成报告
  - 综合分析报告 (.md)
  - 峰数据 CSV
  - 谱图图片
  - 结构图文件
```

### 场景 2：用户提供 SMILES 或化合物名称

```
用户提供 SMILES / 化合物名称
    │
    ▼
[Step 1] 用 ChemDraw 绘制结构
  调用：controller.draw_structure(
    smiles="CCOC(=O)c1ccc(cc1)OC",
    output_dir="...",
    format="all",
    add_numbers=True
  )
    │
    ▼
[Step 2] 返回所有格式的结构文件
  - PNG 图片
  - SVG 矢量图
  - CDXML（ChemDraw 格式）
  - SDF / MOL
```

### 场景 3：用户需要量化计算

```
用户需要 NMR 预测 / ECD 计算
    │
    ▼
[Step 1] 用 Spartan 运行计算
  调用：controller.run_nmr_prediction(
    input_mol="结构文件或 SMILES",
    method="DFT",
    basis="6-311G*"
  )
    │
    ▼
[Step 2] 计算完成后导出结果
```

---

## 三、核心 API 接口

### 主控制器：ChemicalSoftwareController

**文件位置**：`main_controller_gui.py`

```python
from main_controller_gui import ChemicalSoftwareController

controller = ChemicalSoftwareController(config={
    "output_dir": "./outputs",
    "software_paths": {
        "mestrenova": "C:/Program Files/MestReNova/MestReNova.exe",
        "chemdraw": "C:/Program Files/ChemOffice2022/ChemDraw/ChemDraw.exe",
        "spartan": "C:/Program Files/Wavefunction/Spartan14/Spartan14.exe"
    }
})
```

#### 1. 检查软件可用性

```python
availability = controller.check_software_availability()
# 返回：{"mestrenova": True, "chemdraw": True, "spartan": False}
```

#### 2. 分析谱图（最常用）

```python
result = controller.analyze_spectrum(
    spectrum_file="D:/spectra/sample.mnova",
    output_dir="D:/outputs/analysis"
)
```

**返回结果结构：**
```python
{
    "success": True,
    "spectrum_file": "D:/spectra/sample.mnova",
    "spectrum_info": {
        "nucleus": "1H",       # 核类型
        "solvent": "CDCl3",    # 溶剂
        "filename": "sample"
    },
    "peaks": [                  # 峰列表
        {"shift_ppm": 8.00, "intensity": 2.0, "multiplicity": "d"},
        ...
    ],
    "peaks_csv": "D:/outputs/analysis/sample_peaks.csv",
    "spectrum_image": "D:/outputs/analysis/sample_spectrum.png",
    "errors": []
}
```

#### 3. 绘制结构图

```python
result = controller.draw_structure(
    smiles="CCOC(=O)c1ccc(cc1)OC",      # SMILES 字符串
    compound_name=None,                   # 或化合物名称
    output_dir="D:/outputs/structures",   # 输出目录
    format="all",                         # "png", "svg", "cdxml", "sdf", "mol", "all"
    add_numbers=True                      # 是否添加原子编号
)
```

**返回结果结构：**
```python
{
    "success": True,
    "smiles": "CCOC(=O)c1ccc(cc1)OC",
    "output_files": {
        "png": "D:/outputs/structures/structure.png",
        "svg": "D:/outputs/structures/structure.svg",
        "cdxml": "D:/outputs/structures/structure.cdxml",
        "sdf": "D:/outputs/structures/structure.sdf",
        "mol": "D:/outputs/structures/structure.mol"
    },
    "errors": []
}
```

#### 4. 完整工作流程

```python
result = controller.full_analysis_workflow(
    spectrum_file="D:/spectra/sample.mnova",
    output_dir="D:/outputs/full_analysis"
)
```

自动完成：谱图分析 → 结构推导 → 结构图绘制 → 生成报告

#### 5. 批量分析

```python
result = controller.batch_analyze_spectra(
    spectrum_files=["file1.mnova", "file2.mnova", "file3.mnova"],
    output_dir="D:/outputs/batch"
)
```

#### 6. 软件管理

```python
controller.launch_software("mestrenova")   # 启动指定软件
controller.close_software("chemdraw")       # 关闭指定软件
controller.close_all_software()             # 关闭所有软件
```

---

## 四、各软件操作详解

### 4.1 MestrenovaGUI — 谱图分析

**文件**：`mestrenova_gui.py`

| 方法 | 功能 | 快捷键 |
|------|------|--------|
| `open_file(path)` | 打开 .mnova 文件 | `Ctrl+O` |
| `auto_pick_peaks()` | 自动峰识别 | `Ctrl+Shift+G` |
| `auto_integrate()` | 自动积分 | `Ctrl+Shift+I` |
| `export_peaks_to_csv(path)` | 导出峰列表到 CSV | `Ctrl+Shift+S` → CSV |
| `export_spectrum_image(path)` | 导出谱图图片 | `Alt+F` → `E` → `I` |
| `export_peaks_to_clipboard()` | 导出峰数据到剪贴板 | `Ctrl+C` → 解析 |
| `fit_to_window()` | 适应窗口显示 | `Ctrl+0` |
| `get_spectrum_info()` | 获取谱图信息 | 从窗口标题解析 |
| `process_spectrum(file, out)` | 完整处理流程 | 以上所有 |

### 4.2 ChemDrawGUI — 结构绘制

**文件**：`chemdraw_gui.py`

| 方法 | 功能 | 快捷键 |
|------|------|--------|
| `draw_from_smiles(smiles)` | 从 SMILES 绘制 | `Ctrl+E` → 粘贴 → Enter |
| `draw_from_name(name)` | 从化合物名称绘制 | `Ctrl+E` |
| `clean_up_structure()` | 美化结构 | `Ctrl+Shift+K` |
| `add_atom_numbers()` | 添加原子编号 | `Alt+S` → `A` → `N` |
| `export_cdxml(path)` | 导出 CDXML | `Ctrl+Shift+S` |
| `export_png(path)` | 导出 PNG | `Ctrl+Shift+S` |
| `export_svg(path)` | 导出 SVG | `Ctrl+Shift+S` |
| `export_sdf(path)` | 导出 SDF | `Ctrl+Shift+S` |
| `create_structure_image(...)` | 完整绘制流程 | 以上所有 |

### 4.3 SpartanGUI — 量化计算

**文件**：`spartan_gui.py`

| 方法 | 功能 | 快捷键 |
|------|------|--------|
| `import_from_mol(path)` | 导入分子文件 | `Ctrl+O` |
| `run_optimization(...)` | 几何优化 | `Ctrl+Shift+E` → Optimize |
| `run_nmr_prediction(...)` | NMR 化学位移预测 | `Ctrl+Shift+E` → NMR |
| `run_ecd_calculation(...)` | ECD 手性光谱计算 | `Ctrl+Shift+E` → ECD |
| `export_molecule(path)` | 导出分子结构 | `Ctrl+Shift+S` |
| `export_spectrum_data(path)` | 导出光谱数据 | `Alt+F` → `E` |
| `full_nmr_prediction_workflow(...)` | 完整 NMR 预测流程 | 以上所有 |

### 4.4 GUIAutomation — 核心自动化引擎

**文件**：`gui_automation.py`

底层的 GUI 自动化核心，封装了 pywinauto 和 pyautogui。

| 方法 | 功能 |
|------|------|
| `open_application(path)` | 启动应用程序 |
| `wait_for_window(title)` | 等待窗口出现 |
| `activate_window()` | 激活窗口（获取焦点） |
| `press_keys(*keys)` | 模拟按键（支持组合键） |
| `type_text(text)` | 输入文本 |
| `click(x, y)` | 鼠标点击 |
| `copy_to_clipboard(text)` | 复制到剪贴板 |
| `paste_from_clipboard()` | 从剪贴板粘贴 |
| `take_screenshot()` | 截图 |
| `handle_dialog(action)` | 处理对话框 |
| `open_file(path)` | 通用文件打开（Ctrl+O） |

---

## 五、使用示例

### 示例 1：分析 .mnova 谱图（最常用）

```python
from main_controller_gui import ChemicalSoftwareController

# 初始化控制器
controller = ChemicalSoftwareController()

# 检查软件
avail = controller.check_software_availability()
print(f"Mestrenova: {'可用' if avail['mestrenova'] else '不可用'}")

# 分析谱图（全自动）
result = controller.analyze_spectrum(
    spectrum_file="D:/spectra/compound_A.mnova",
    output_dir="D:/outputs/compound_A"
)

# 输出结果
if result["success"]:
    print(f"✓ 识别到 {len(result['peaks'])} 个峰")
    print(f"✓ 核类型: {result['spectrum_info']['nucleus']}")
    print(f"✓ 峰数据: {result['peaks_csv']}")
    print(f"✓ 谱图图片: {result['spectrum_image']}")
    
    # 用 ChemDraw 画结构
    draw_result = controller.draw_structure(
        smiles="CCOC(=O)c1ccc(cc1)OC",
        output_dir="D:/outputs/compound_A/structure",
        format="all"
    )
    print(f"✓ 结构图: {list(draw_result['output_files'].keys())}")
else:
    print(f"✗ 分析失败: {result['errors']}")

# 关闭所有软件
controller.close_all_software()
```

### 示例 2：批量绘制结构图

```python
from main_controller_gui import ChemicalSoftwareController

controller = ChemicalSoftwareController()

structures = [
    {"smiles": "CCO", "name": "ethanol"},
    {"smiles": "c1ccccc1", "name": "benzene"},
    {"smiles": "CC(=O)O", "name": "acetic_acid"},
]

for struct in structures:
    result = controller.draw_structure(
        smiles=struct["smiles"],
        output_dir=f"D:/outputs/{struct['name']}",
        format="png"
    )
    print(f"{struct['name']}: {'✓' if result['success'] else '✗'}")

controller.close_all_software()
```

---

## 六、配置文件

`config.json` 配置说明：

```json
{
  "software_paths": {
    "mestrenova": "C:/Program Files/MestReNova/MestReNova.exe",
    "chemdraw": "C:/Program Files/ChemOffice2022/ChemDraw/ChemDraw.exe",
    "spartan": "C:/Program Files/Wavefunction/Spartan14/Spartan14.exe",
    "specdis": ""
  },
  "preferred_drawing_backend": "CHEMDRAW",
  "output_dir": "./outputs",
  "use_gui_automation": true,
  "use_online_database": true,
  "hmass_tolerance_ppm": 10.0,
  "log_level": "INFO"
}
```

**重要**：`use_gui_automation` 必须为 `true`（默认），表示使用 GUI 自动化操作真实软件。

---

## 七、命令行使用

```bash
# 检查软件可用性
python main_controller_gui.py --check

# 分析单个谱图
python main_controller_gui.py --analyze spectra/sample.mnova

# 批量分析
python main_controller_gui.py --batch file1.mnova file2.mnova

# 绘制结构
python main_controller_gui.py --draw --smiles "CCOC(=O)c1ccc(cc1)OC"

# 完整工作流程
python main_controller_gui.py --workflow spectra/sample.mnova

# 关闭所有软件
python main_controller_gui.py --close-all
```

---

## 八、常见问题与排错

### Q: 软件启动失败

**A**: 检查 `config.json` 中的路径是否正确，或手动指定：
```python
controller = ChemicalSoftwareController({
    "software_paths": {
        "mestrenova": "C:/你的路径/MestReNova.exe"
    }
})
```

### Q: GUI 操作不准确

**可能原因及解决：**
1. 软件窗口未获得焦点 → 确保目标窗口在前台
2. 操作速度太快 → 增加延时：`time.sleep(2)`
3. 软件版本快捷键不同 → 检查并修改对应模块中的快捷键
4. 屏幕分辨率差异 → 避免硬编码坐标，尽量用快捷键

### Q: 如何调试 GUI 操作？

```python
# 截图查看当前状态
controller.gui_core.take_screenshot("debug_step1.png")

# 查看窗口信息
info = controller.gui_core.get_window_info()
print(f"标题: {info.title}")
print(f"位置: {info.rect}")

# 查看鼠标位置
pos = controller.gui_core.get_current_mouse_position()
print(f"鼠标: {pos}")
```

### Q: 操作被弹窗打断

**A**: 使用弹窗处理方法：
```python
controller.gui_core.handle_dialog(action="ok")  # 点确定
controller.gui_core.handle_dialog(action="cancel")  # 点取消
controller.gui_core.handle_dialog(action="yes")  # 点是
```

### Q: 计算任务需要等很久怎么办？

**A**: 量化计算（Spartan）可以不等待完成，提交后返回：
```python
controller.run_nmr_prediction(
    input_mol="...",
    wait_for_complete=False  # 不等待，立即返回
)
# 用户可以在 Spartan 中监控进度
```

---

## 九、技术架构

```
用户请求
   │
   ▼
ChemicalSoftwareController (main_controller_gui.py)
   │  统一调度、状态管理、错误恢复
   │
   ├─► MestrenovaGUI ──► GUIAutomation ──► pywinauto/pyautogui ──► Mestrenova 15
   │
   ├─► ChemDrawGUI ───► GUIAutomation ──► pywinauto/pyautogui ──► ChemDraw 2022
   │
   └─► SpartanGUI ────► GUIAutomation ──► pywinauto/pyautogui ──► Spartan '14
```

---

## 十、版本信息

- **Version**: 2.0.0 (GUI Automation Edition)
- **核心变化**: 从 API 模拟升级为真实 GUI 自动化操作
- **支持软件**: Mestrenova 15 / ChemDraw 2022 / Spartan '14
- **核心依赖**: pywinauto, pyautogui, pyperclip, Pillow

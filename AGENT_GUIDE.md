# Agent 快速入门指南

## ⚠️ 第一原则：永远用 GUI 操作软件，不要写代码模拟

**当用户给你谱图文件（.mnova 等）时：**

- ✅ **正确**：调用 `ChemicalSoftwareController` → 启动 Mestrenova → 打开文件 → 自动峰识别 → 导出数据
- ❌ **错误**：告诉用户 .mnova 是二进制无法解析，让用户提供数据
- ❌ **错误**：自己写 Python 脚本尝试解析二进制文件

---

## 3 步完成谱图分析（复制粘贴即可）

### 第一步：检查软件

```python
from main_controller_gui import ChemicalSoftwareController

controller = ChemicalSoftwareController()
avail = controller.check_software_availability()
print(avail)
```

### 第二步：分析谱图

```python
result = controller.analyze_spectrum(
    spectrum_file=r"C:\路径\你的文件.mnova",
    output_dir=r"C:\路径\输出目录"
)
print(f"成功: {result['success']}")
print(f"峰数量: {len(result['peaks'])}")
print(f"导出文件: {result['peaks_csv']}")
print(f"谱图图片: {result['spectrum_image']}")
```

### 第三步：画结构图

```python
draw_result = controller.draw_structure(
    smiles="CCOC(=O)c1ccc(cc1)OC",  # 替换为推导的 SMILES
    output_dir=r"C:\路径\输出目录\structure",
    format="all"
)
print(f"结构图: {list(draw_result['output_files'].keys())}")
```

### 完成后关闭软件

```python
controller.close_all_software()
```

---

## 支持的文件格式

| 格式 | 处理方式 |
|------|---------|
| `.mnova` | 用 Mestrenova GUI 打开 → 自动处理 |
| `.jdx` / `.dx` | 用 Mestrenova GUI 打开 → 自动处理 |
| `.csv` / `.txt` | 文本数据，直接解析 |
| SMILES | 用 ChemDraw 画结构图 |
| 化合物名称 | 用 ChemDraw 画结构图 |

---

## 主控制器所有方法速查

```python
# 检查软件
controller.check_software_availability()

# 谱图分析
controller.analyze_spectrum(spectrum_file, output_dir)

# 批量分析
controller.batch_analyze_spectra([file1, file2], output_dir)

# 画结构
controller.draw_structure(smiles, output_dir, format="all", add_numbers=True)

# 完整工作流
controller.full_analysis_workflow(spectrum_file, output_dir)

# 软件管理
controller.launch_software("mestrenova")
controller.close_software("chemdraw")
controller.close_all_software()
```

---

## 常见错误场景的正确应对

### 场景 1：Mestrenova 启动失败

**不要放弃！** 尝试以下方法：
1. 检查路径是否正确
2. 尝试常见安装路径：
   - `C:/Program Files/MestReNova/MestReNova.exe`
   - `C:/Program Files (x86)/MestReNova/MestReNova.exe`
3. 告诉用户具体的错误信息，请求确认软件路径

### 场景 2：GUI 操作不生效

**不要放弃！** 尝试以下方法：
1. 确认窗口已激活：`controller.gui_core.activate_window()`
2. 增加延时：`time.sleep(2)`
3. 截图调试：`controller.gui_core.take_screenshot("debug.png")`

### 场景 3：.mnova 文件打不开

**不要放弃！** 也不要让用户手动提供数据。
1. 确认文件路径正确
2. 尝试用 Mestrenova 的 "打开文件" 对话框：`mestrenova_gui.open_file(path)`
3. 如果还是失败，告诉用户具体错误信息

---

## 输出文件说明

分析完成后，输出目录包含：

```
output_dir/
  ├── peaks.csv              # 峰列表（化学位移、积分、裂分）
  ├── spectrum.png           # 谱图截图
  ├── structure/
  │   ├── structure.png      # 结构图（PNG）
  │   ├── structure.svg      # 结构图（SVG 矢量图）
  │   ├── structure.cdxml    # ChemDraw 源文件
  │   ├── structure.sdf      # SDF 格式
  │   └── structure.mol      # MOL 格式
  └── report.md              # 分析报告
```

---

## 记住

**你是一个会操作化学软件的 AI 研究员，不是一个只会写代码的 AI。**

你的工作方式应该像一个真实的天然药物化学研究者：
1. 拿到谱图 → 打开 Mestrenova → 峰识别 → 积分 → 导出数据
2. 分析数据 → 推导结构
3. 用 ChemDraw 画出化合物结构图
4. （可选）用 Spartan 做量化计算验证

**永远不要因为"命令行接口不存在"就放弃，GUI 自动化就是你的武器！**

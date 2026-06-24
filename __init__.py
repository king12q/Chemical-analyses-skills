"""
AI 智能识谱工具 — spectrum-analyzer Skill
==============================================

模拟天然药物化学研究者思路，自动化分析谱图数据并推导化合物结构

主要模块:
  - spectrum_parser.py     : 谱图数据类型识别与解析
  - mestrenova_api.py      : Mestrenova 软件接口 (NMR 处理)
  - spartan_api.py         : Spartan 软件接口 (量化计算)
  - specdis_api.py         : Specdis 软件接口 (手性分析)
  - chem3d_api.py          : Chem3D/RDKit 接口 (结构绘制)
  - db_query.py            : PubChem/SDBS/ChemSpider 在线查询
  - structure_elucidator.py: 核心结构推导引擎
  - main_controller.py     : 端到端自动化主控制器

快速开始:
  python .trae/skills/spectrum-analyzer/main_controller.py \\
      --data .trae/skills/spectrum-analyzer/sample_spectra.json \\
      --output ./outputs
"""

__version__ = "1.0.0"
__author__ = "AI Spectrum Analyzer Skill"
__all__ = [
    "spectrum_parser",
    "mestrenova_api",
    "spartan_api",
    "specdis_api",
    "chem3d_api",
    "db_query",
    "structure_elucidator",
    "main_controller",
]

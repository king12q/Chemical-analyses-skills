"""验证所有模块的 Python 语法正确性"""
import ast
import sys
import pathlib

files = [
    "spectrum_parser.py",
    "mestrenova_api.py",
    "spartan_api.py",
    "specdis_api.py",
    "chem3d_api.py",
    "db_query.py",
    "structure_elucidator.py",
    "main_controller.py",
    "__init__.py",
]

base = pathlib.Path(__file__).parent
all_ok = True
for f in files:
    path = base / f
    if path.exists():
        try:
            ast.parse(open(path, encoding="utf-8").read())
            print(f"  ✓ {f}")
        except SyntaxError as e:
            print(f"  ✗ {f}: {e}")
            all_ok = False
    else:
        print(f"  ? {f} — 文件不存在")

if all_ok:
    print("\n[通过] 所有模块语法正确！")
    sys.exit(0)
else:
    print("\n[失败] 存在语法错误")
    sys.exit(1)

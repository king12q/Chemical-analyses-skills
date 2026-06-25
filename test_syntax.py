#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_syntax.py — 语法完整性验证

安装 Skill 后运行此脚本，验证所有 Python 文件语法正确且完整。
如果有文件被截断或损坏，会立即报错。

用法:
    python test_syntax.py
"""

import ast
import os
import sys
import json
from pathlib import Path

def check_all_python_files(skill_dir: str = None) -> dict:
    """检查 skill 目录下所有 Python 文件的语法"""
    if skill_dir is None:
        skill_dir = str(Path(__file__).parent.resolve())

    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "files": {},
        "all_ok": False
    }

    py_files = sorted([f for f in os.listdir(skill_dir) if f.endswith('.py') and not f.startswith('_') and not f.startswith('test_')])

    print(f"在 {skill_dir} 中检查 Python 文件语法...")
    print(f"共找到 {len(py_files)} 个 Python 文件\n")

    for filename in py_files:
        filepath = os.path.join(skill_dir, filename)
        results["total"] += 1
        file_info = {
            "size": os.path.getsize(filepath),
            "lines": 0,
            "status": "unknown",
            "error": None
        }

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            file_info["lines"] = len(content.splitlines())

            # 语法检查
            ast.parse(content)
            file_info["status"] = "ok"
            results["passed"] += 1
            print(f"  ✓ {filename:35s} ({file_info['lines']:>4d} 行, {file_info['size']:>6d} 字节)")

            # 额外检查：文件是否完整（最后一行不是未完成的语句）
            last_lines = [l for l in content.strip().split('\n')[-5:] if l.strip()]
            if last_lines:
                last_line = last_lines[-1].strip()
                # 常见未完成的模式
                incomplete_patterns = [
                    'def ', 'class ', 'if ', 'for ', 'while ', 
                    'try:', 'except', 'else:', 'elif ',
                    'return ', ' = ', ' + ', ' - ', ' * ', ' / '
                ]
                is_incomplete = False
                for pat in incomplete_patterns:
                    if last_line.startswith(pat) or last_line.endswith(pat):
                        is_incomplete = True
                        break
                if is_incomplete:
                    print(f"    ⚠️  警告: 最后一行可能不完整: {last_line[:60]}")

        except SyntaxError as e:
            file_info["status"] = "syntax_error"
            file_info["error"] = str(e)
            results["failed"] += 1
            print(f"  ✗ {filename:35s} 语法错误: {e}")

        except Exception as e:
            file_info["status"] = "error"
            file_info["error"] = str(e)
            results["failed"] += 1
            print(f"  ✗ {filename:35s} 读取失败: {e}")

        results["files"][filename] = file_info

    results["all_ok"] = results["failed"] == 0

    print()
    print("=" * 60)
    print(f"结果: {results['passed']}/{results['total']} 个文件通过")
    if results["all_ok"]:
        print("✅ 所有文件语法正确！Skill 安装完整。")
    else:
        print(f"❌ 有 {results['failed']} 个文件有错误，请检查。")
    print("=" * 60)

    return results


def check_key_modules(skill_dir: str = None) -> bool:
    """检查关键模块能否正常导入"""
    if skill_dir is None:
        skill_dir = str(Path(__file__).parent.resolve())

    if skill_dir not in sys.path:
        sys.path.insert(0, skill_dir)

    print("\n检查关键模块导入...")

    key_modules = [
        "gui_automation",
        "mestrenova_gui",
        "chemdraw_gui",
        "spartan_gui",
        "spectrum_type_detector",
        "multi_spectrum_analyzer",
        "spectrum_analyzer",
        "spectrum_parser",
        "structure_elucidator",
        "db_query",
    ]

    all_ok = True
    for mod_name in key_modules:
        try:
            __import__(mod_name)
            print(f"  ✓ {mod_name}")
        except Exception as e:
            print(f"  ✗ {mod_name}: {e}")
            all_ok = False

    print()
    if all_ok:
        print("✅ 所有关键模块可正常导入！")
    else:
        print("❌ 部分模块导入失败")

    return all_ok


if __name__ == "__main__":
    print("=" * 60)
    print("AI 智能识谱工具 — 语法完整性验证")
    print("=" * 60)
    print()

    syntax_ok = check_all_python_files()["all_ok"]
    import_ok = check_key_modules()

    print()
    if syntax_ok and import_ok:
        print("🎉 Skill 安装完整，所有文件正常！")
        sys.exit(0)
    else:
        print("⚠️  请检查上面的错误信息")
        sys.exit(1)

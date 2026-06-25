#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试多类型谱图识别
"""

import os
import sys

skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, skill_dir)

from spectrum_analyzer import detect_spectrum_type

print("=" * 70)
print("测试 1: 二维 NMR (COSY)")
print("=" * 70)
result = detect_spectrum_type(r"C:\Users\Administrator\Desktop\新文件夹\化合物1 二维NMR.mnova")
print(f"类型: {result['spectrum_type']}")
print(f"置信度: {result['confidence']:.0%}")
if result.get('sub_type'):
    print(f"子类型: {result['sub_type']}")
print()

print("=" * 70)
print("测试 2: NOESY")
print("=" * 70)
result = detect_spectrum_type(r"C:\Users\Administrator\Desktop\新文件夹\化合物2  NOESY.mnova")
print(f"类型: {result['spectrum_type']}")
print(f"置信度: {result['confidence']:.0%}")
if result.get('sub_type'):
    print(f"子类型: {result['sub_type']}")
print()

print("=" * 70)
print("测试 3: 化合物2 二维 NMR")
print("=" * 70)
result = detect_spectrum_type(r"C:\Users\Administrator\Desktop\新文件夹\化合物2  二维 NMR.mnova")
print(f"类型: {result['spectrum_type']}")
print(f"置信度: {result['confidence']:.0%}")
if result.get('sub_type'):
    print(f"子类型: {result['sub_type']}")
if result.get('nucleus'):
    print(f"核类型: {result['nucleus']}")
if result.get('solvent'):
    print(f"溶剂: {result['solvent']}")

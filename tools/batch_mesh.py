# -*- coding: utf-8 -*-
"""工具 ⭐ BatchMesher — 清理+去特征+中面+壳网格 一步完成"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import api_batchmesh2
from utils.logger import logger

print("=" * 60)
print("  BatchMesher — 一键清理+去特征+中面+壳网格")
print("=" * 60)

# ★ 参数设置 ★
ELEM_SIZE = 5.0      # 目标单元尺寸 (mm)
ELEM_TYPE = 2        # 2=mixed
PARAM_MODE = "midmesh"  # midmesh / shell / generic / solid
# 使用默认的 crash_5mm_midmesh.param 和 crash_5mm.criteria

print(f"  单元尺寸: {ELEM_SIZE}mm")
print(f"  模式: {PARAM_MODE}")
print(f"  参数: crash_5mm_midmesh.param")
print()

api_batchmesh2(
  None, None,    # session=None → 自动获取, comp_ids=None → 全部
  elem_size=ELEM_SIZE,
  elem_type=ELEM_TYPE,
  param_mode=PARAM_MODE,
)

print()
print("BatchMesher 完成")

# -*- coding: utf-8 -*-
"""工具 ①.5 几何清理（在导入和中面之间执行）"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import get_model_name
from utils.logger import logger

print("=== 几何清理 ===")

# ★ 参数 ★
CLEANUP_TOLERANCE = 0.5   # 清理容差 (mm)
HOLE_MAX_SIZE = 5.0       # 最大填孔尺寸 (mm)
FILLET_MAX_RADIUS = 3.0   # 最大去圆角半径 (mm)

model = hm.Model(get_model_name())

# Step 1: 缝合自由边
print("[1/5] 缝合自由边...")
model.evaltclstring(
  f"*createmark surfs 1 all; *edgestitch surfs 1 {CLEANUP_TOLERANCE}", 0
)

# Step 2: 等效节点/边
print("[2/5] 等效处理...")
model.evaltclstring(
  f"*createmark comps 1 all; *equivalence comps 1 0.1 1 0 0 0 0 0", 0
)

# Step 3: 合并相邻曲面
print("[3/5] 合并曲面...")
model.evaltclstring(
  f"*createmark surfs 1 all; *surfacemarkmerge surfs 1 30.0 0.0 100.0", 0
)

# Step 4: 填孔
print(f"[4/5] 填充小孔 (max={HOLE_MAX_SIZE}mm)...")
model.evaltclstring(
  f"*createmark surfs 1 all; *defeatureholes surfs 1 {HOLE_MAX_SIZE}", 0
)

# Step 5: 去圆角
print(f"[5/5] 去除小圆角 (max={FILLET_MAX_RADIUS}mm)...")
model.evaltclstring(
  f"*createmark surfs 1 all; *surfacefilletremove surfs 1 {FILLET_MAX_RADIUS} 0", 0
)

exec(open(os.path.join(os.path.dirname(__file__), "redraw.py") if os.path.exists(os.path.join(os.path.dirname(__file__), "redraw.py")) else "", encoding="utf-8").read()) if False else None
model.evaltclstring("*autofitview; *redraw", 0)
print("几何清理完成")

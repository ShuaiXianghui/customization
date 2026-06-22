# -*- coding: utf-8 -*-
"""工具④ 参数化网格划分（默认全部组件）"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import exec_tcl, get_model_name
from utils.logger import logger

print("=== ④ 参数化网格划分 ===")

# ★ 默认参数 ★
DEFAULT_SIZE = 5.0       # 单元尺寸(mm)
DEFAULT_TYPE = "mixed"   # mixed / quads / tria / tetra

# ★ 特殊组件: {组件ID: (尺寸, 类型)}
OVERRIDES = {
  # 1: (3.0, "mixed"),
  # 2: (8.0, "tetra"),
}

model = hm.Model(get_model_name())

if OVERRIDES:
  skip_ids = " ".join(str(i) for i in OVERRIDES)
  model.evaltclstring(f"*createmark comps 1 all; *createmark comps 2 {skip_ids}; *markdifference comps 1 comps 2", 0)
else:
  model.evaltclstring("*createmark comps 1 all", 0)

tcl = f"*automesh comps 1 {DEFAULT_SIZE} 1 {DEFAULT_TYPE} 0 0 0 0 3 0 0"
model.evaltclstring(tcl, 0)
print(f"默认: 全部组件 size={DEFAULT_SIZE} type={DEFAULT_TYPE}")

for cid, (size, etype) in OVERRIDES.items():
  model.evaltclstring(f"*createmark comps 1 {cid}; *automesh comps 1 {size} 1 {etype} 0 0 0 0 3 0 0", 0)
  print(f"  特殊: comp {cid} size={size} type={etype}")

exec_tcl("*autofitview; *redraw")
print("完成")

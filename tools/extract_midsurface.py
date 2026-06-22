# -*- coding: utf-8 -*-
"""工具② 中面批量抽取（可选，复杂几何可能失败）"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import get_model_name
from utils.logger import logger

print("=== ② 中面抽取 ===")

# ★ 排除的组件ID（不抽中面）
SKIP_IDS = []

model = hm.Model(get_model_name())
model.evaltclstring("*createmark comps 1 all", 0)

if SKIP_IDS:
  skip = " ".join(str(i) for i in SKIP_IDS)
  model.evaltclstring(f"*createmark comps 2 {skip}; *markdifference comps 1 comps 2", 0)

# 参数: outbound_normals=3(实体) thickness_bound=0(自动) extract_by_comp=0 rerun_type=9(offset+planes+sweeps最强模式) stitch_tol_mode=1
r = model.evaltclstring("*midsurface_extract_10 comps 1 3 0 0 0 9 1 2 0 0 10 2 30 0.5 0 0 1", 0)
msg = getattr(r, 'message', '') if hasattr(r, 'message') else str(r)
if "Unable" in msg:
  print("中面抽取失败: 几何太复杂，建议在 HM 中手动抽取，或跳过此步")
  model.evaltclstring("*redraw", 0)
else:
  model.evaltclstring("*redraw", 0)
  print("中面抽取完成")

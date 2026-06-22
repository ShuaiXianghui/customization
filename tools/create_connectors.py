# -*- coding: utf-8 -*-
"""工具⑤ 连接器自动化（默认全部组件两两配对）"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import exec_tcl, get_model_name
from utils.logger import logger

print("=== ⑤ 连接器 ===")

# ★ 参数 ★
SEAM_GAP = 1.5       # 缝焊间隙(mm)
SEAM_ENABLED = True

model = hm.Model(get_model_name())

if SEAM_ENABLED:
  tcl = f"*createmark comps 1 all; *findedges comps 1 {SEAM_GAP} 1 0; *connectorcreate seam lines 1 {SEAM_GAP}"
  model.evaltclstring(tcl, 0)
  print("缝焊: 全部组件间已创建")

exec_tcl("*redraw")
print("完成")

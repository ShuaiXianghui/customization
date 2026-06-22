# -*- coding: utf-8 -*-
"""
工具函数加载器 — 一次性加载所有函数到当前命名空间
用法: exec(open(r"tools/load_all.py", encoding="utf-8").read())
"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.logger import logger
from utils.hw_api import (
  api_extract_midsurface,
  api_assign_property,
  api_auto_mesh,
  api_create_seam_weld,
  api_create_bolt,
  api_clear_all,
  exec_tcl,
  get_model_name,
)

print("快捷函数已加载:")

def midsurface(*comp_ids):
  """批量抽取中面: midsurface(1, 2, 3)"""
  ids = list(comp_ids) if comp_ids else []
  api_extract_midsurface(ids)
  print(f"中面抽取完成: {len(ids)} 个")

def assign_prop(comp_id, material="Q235", thickness=6, mesh_type="shell"):
  """赋值属性: assign_prop(1, 'Q355', 10, 'shell')"""
  MATS = {
    "Q235": {"E":210000,"nu":0.3,"rho":7.85e-9,"yield":235},
    "Q355": {"E":210000,"nu":0.3,"rho":7.85e-9,"yield":355},
    "Q460": {"E":210000,"nu":0.3,"rho":7.85e-9,"yield":460},
    "QSTE420":{"E":210000,"nu":0.3,"rho":7.85e-9,"yield":420},
  }
  card = "PSHELL" if mesh_type == "shell" else "PSOLID"
  api_assign_property(comp_id, MATS.get(material, MATS["Q235"]), thickness, card)
  print(f"comp={comp_id}: {material}, {thickness}mm, {card}")

def mesh(comp_id, size=5.0, etype="mixed"):
  """网格划分: mesh(1, 5.0, 'mixed')"""
  api_auto_mesh(comp_id, size, etype)
  print(f"comp={comp_id}: size={size}, type={etype}")
  exec_tcl("*autofitview; *redraw")

def seam_weld(a, b, gap=1.5):
  """缝焊: seam_weld(1, 2, 1.5)"""
  api_create_seam_weld(a, b, gap)
  print(f"缝焊: comp {a} ↔ {b}")

def bolt(a, b, dia=10.0):
  """螺栓: bolt(1, 2, 10.0)"""
  api_create_bolt(a, b, dia)
  print(f"螺栓: comp {a} ↔ {b}")

def clear():
  """清空模型"""
  api_clear_all()
  print("模型已清理")

print("快捷函数已加载:")
print("  midsurface(1, 2, ...)          批量中面")
print("  assign_prop(1, 'Q355', 10)     赋属性")
print("  mesh(1, 5.0, 'mixed')          网格划分")
print("  seam_weld(1, 2, 1.5)           缝焊")
print("  bolt(1, 2, 10.0)               螺栓")
print("  clear()                        清空模型")
print(f"  当前模型: {get_model_name()}")
print("")

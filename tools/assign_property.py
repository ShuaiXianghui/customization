# -*- coding: utf-8 -*-
"""工具③ 属性赋参（默认全部组件）"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import exec_tcl, get_model_name
from utils.logger import logger

print("=== ③ 属性赋参 ===")

# ★ 全局默认 ★
DEFAULT_MATERIAL = "Q235"
DEFAULT_THICKNESS = 6      # mm (板厚)
DEFAULT_MESH_TYPE = "shell"  # shell 或 solid

# ★ 材料库 ★
MATERIALS = {
  "Q235": {"E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 235},
  "Q355": {"E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 355},
  "Q460": {"E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 460},
  "QSTE420": {"E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 420},
}

# ★ 特殊组件（覆盖默认）: {组件ID: (材料, 厚度, 类型)}
OVERRIDES = {
  # 1: ("Q355", 10, "shell"),
  # 2: ("Q460", 16, "shell"),
}

model = hm.Model(get_model_name())

# 对所有组件
model.evaltclstring("*createmark comps 1 all", 0)

mat_data = MATERIALS[DEFAULT_MATERIAL]
card = "PSHELL" if DEFAULT_MESH_TYPE == "shell" else "PSOLID"
mat_name = f"MAT_{DEFAULT_MATERIAL}"
prop_name = "prop_all"

# 创建材料
model.evaltclstring(f"*collectorcreateonly materials \"{mat_name}\" \"\" 11; *setvalue materials id=1 STATUS=1 1=1; *materialupdate materials 1 E={mat_data['E']} NU={mat_data['nu']} RHO={mat_data['rho']}", 0)

# 创建属性
if card == "PSHELL":
  model.evaltclstring(f"*collectorcreateonly properties \"{prop_name}\" \"PSHELL\" 11; *setvalue props id=1 STATUS=1 95=1 1={DEFAULT_THICKNESS}", 0)
else:
  model.evaltclstring(f"*collectorcreateonly properties \"{prop_name}\" \"PSOLID\" 11; *setvalue props id=1 STATUS=1 95=1", 0)

# 绑定
model.evaltclstring(f"*componentupdate comps 1 1 0 \"{prop_name}\" 1 0 \"{mat_name}\"", 0)

# 特殊覆盖
for cid, (mat, thk, tp) in OVERRIDES.items():
  md = MATERIALS.get(mat, mat_data)
  mn = f"MAT_{mat}"
  pn = f"prop_{cid}"
  c = "PSHELL" if tp == "shell" else "PSOLID"
  model.evaltclstring(f"*collectorcreateonly materials \"{mn}\" \"\" 11; *setvalue materials id=1 STATUS=1 1=1; *materialupdate materials 1 E={md['E']} NU={md['nu']} RHO={md['rho']}", 0)
  if c == "PSHELL":
    model.evaltclstring(f"*collectorcreateonly properties \"{pn}\" \"PSHELL\" 11; *setvalue props id=1 STATUS=1 95=1 1={thk}", 0)
  else:
    model.evaltclstring(f"*collectorcreateonly properties \"{pn}\" \"PSOLID\" 11; *setvalue props id=1 STATUS=1 95=1", 0)
  model.evaltclstring(f"*createmark comps 1 {cid}; *componentupdate comps 1 1 0 \"{pn}\" 1 0 \"{mn}\"", 0)
  print(f"  覆盖: comp {cid} → {mat} {thk}mm {c}")

print(f"完成: 全部组件 → {DEFAULT_MATERIAL} {DEFAULT_THICKNESS}mm {card}")
if OVERRIDES:
  print(f"      {len(OVERRIDES)} 个特殊组件已覆盖")

# -*- coding: utf-8 -*-
"""一键全流程: 中面 → 赋参 → 网格 → 连接器 (几何手动导入)"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

print("=" * 50)
print("叉车建模全流程: BatchMesher → 属性 → 连接器")
print("提示: 请先用 HM 手动导入几何")
print("=" * 50)

try: _tools = os.path.dirname(os.path.abspath(__file__))
except NameError: _tools = os.path.join(os.getcwd(), "tools")

for fn in ["batch_mesh.py", "assign_property.py", "create_connectors.py"]:
  exec(open(os.path.join(_tools, fn), encoding="utf-8").read())

print("\n" + "=" * 50)
print("全流程完成")
print("=" * 50)

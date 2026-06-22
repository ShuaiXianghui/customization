# -*- coding: utf-8 -*-
"""
HyperMesh Python 控制台启动脚本
在 HM 控制台中执行:
  exec(open(r"D:/Working/OnGoing/customization/startup.py", encoding="utf-8").read())
"""
import sys, os, importlib

_PROJECT_DIR = os.path.dirname(os.path.join(os.getcwd(), "startup.py"))
try:
  _PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
  _PROJECT_DIR = os.getcwd()
  print(f"[INFO] exec() 模式, 当前目录: {_PROJECT_DIR}")

if _PROJECT_DIR not in sys.path:
  sys.path.insert(0, _PROJECT_DIR)

if not os.path.isfile(os.path.join(_PROJECT_DIR, "config", "settings.py")):
  print(f"[错误] 当前目录不是项目根目录: {_PROJECT_DIR}")
  print("请先: import os; os.chdir(r'D:/Working/OnGoing/customization')")
  raise SystemExit

# 强制刷新所有模块
for m in list(sys.modules.keys()):
  if m.startswith(("utils.", "modules.", "tools.")):
    del sys.modules[m]

# 确保 hm 可用
try:
  hm
  print("[OK] 已连接到 HyperMesh 会话")
except NameError:
  print("[WARN] 未检测到 hm 对象")

from utils.logger import logger
from utils.hw_api import (
  api_extract_midsurface, api_assign_property,
  api_auto_mesh, api_create_seam_weld, api_create_bolt, api_clear_all,
  api_geometry_cleanup, api_surface_merge, api_fill_holes,
  api_stitch_free_edges, api_equivalence,
  api_batchmesh2, api_tetmesh, api_elemoffset_thinsolid, exec_tcl, get_model_name,
  api_diag_thickness, api_get_solid_thickness,
  get_hm, get_model,
)

logger.info("===== 叉车建模工具已加载 =====")
logger.info(f"当前模型: {get_model_name()}")

# 标准板厚 & 材料库
ST = [3,4,5,6,8,10,12,14,16,20,25,30]
MATS = {
  "Q235":{"E":210000,"nu":0.3,"rho":7.85e-9,"yield":235},
  "Q355":{"E":210000,"nu":0.3,"rho":7.85e-9,"yield":355},
  "Q460":{"E":210000,"nu":0.3,"rho":7.85e-9,"yield":460},
  "QSTE420":{"E":210000,"nu":0.3,"rho":7.85e-9,"yield":420},
}

def midsurface(*ids): api_extract_midsurface(list(ids)); print(f"中面: {len(ids)}个")
def assign_shell(comp, material="Q235", thickness=6):
  """薄壁件赋属性: assign_shell(comp_id, 'Q235', 6)"""
  cid = int(comp) if comp else 0
  mat = MATS.get(material, MATS["Q235"])
  api_assign_property(cid, mat, thickness, "PSHELL")
  print(f"comp{cid}: {material} {thickness}mm PSHELL")

def assign_solid(comp, material="Q235"):
  """厚实体赋材料: assign_solid(comp_id, 'Q235')"""
  cid = int(comp) if comp else 0
  mat = MATS.get(material, MATS["Q235"])
  api_assign_property(cid, mat, 0, "PSOLID")
  print(f"comp{cid}: {material} PSOLID")

def assign_all():
  """批量赋属性: assign_all()
  根据缓存的 classify 结果: 薄壁件→分组 PSHELL T{thk}_Q235, 中厚+厚实体→PSOLID SW

  使用 geometry_defeature.py 的共享材料/属性方案
  """
  global _classify_result
  if _classify_result is None: print("请先运行 classify()"); return

  import json, os
  from config.settings import STANDARD_THICKNESS

  # 加载材料数据库
  db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else os.getcwd(),
    "config", "material_db.json"
  )
  try:
    with open(db_path, "r", encoding="utf-8") as f:
      material_db = json.load(f)
  except:
    material_db = {
      "Q235": {"E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 235},
      "Q355": {"E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 355},
    }

  # 薄壁件按厚度分组
  thin_by_thickness = {}
  for p in _classify_result.thin_parts:
    thick = api_get_solid_thickness(None, p.comp_id) or 6.0
    # 取整到标准板厚
    std_thk = min(STANDARD_THICKNESS, key=lambda x: abs(x - thick))
    thin_by_thickness.setdefault(std_thk, []).append(p.comp_id)

  # 构建 thin_groups: [(comp_ids, thickness, mat_name), ...]
  thin_groups = []
  for thk, comp_ids in sorted(thin_by_thickness.items()):
    mat_name = "Q235"  # default, could match by name later
    thin_groups.append((comp_ids, thk, mat_name))

  thick_ids = (
    [int(p.comp_id) for p in _classify_result.mid_thick_parts] +
    [int(p.comp_id) for p in _classify_result.thick_parts]
  )

  from utils.hw_api import api_assign_property_shared
  api_assign_property_shared(thin_groups, thick_ids, material_db)

  print(f"属性完成: {len(thin_groups)} 组 PSHELL + {len(thick_ids)} 个 PSOLID SW")

def mesh(comp,size=5.0,etype="mixed"): api_auto_mesh(comp,size,etype); print(f"comp{comp}: {size}mm {etype}")
def weld(a,b,gap=1.5): api_create_seam_weld(a,b,gap); print(f"缝焊: {a}↔{b}")
def bolt_conn(a,b,dia=10): api_create_bolt(a,b,dia); print(f"螺栓: {a}↔{b}")
def cls(): api_clear_all(); print("已清理")

# ========== 分类 & 网格命令 ==========

_classify_result = None

def _count_solids(comp_id):
  """统计组件内 solid 数量"""
  try:
    hm_mod = get_hm()
    model = get_model()
    import hm.entities as ent
    comp_sel = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(comp_id)]))
    solid_col = hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Solid, ent.Component), comp_sel)
    return len(solid_col)
  except:
    return 0


def classify(show_details=False):
  """三维零件分类: classify() 简要 / classify(True) 详细列表"""
  global _classify_result
  from modules.geometry_classify import GeometryClassifier
  c = GeometryClassifier()
  result = c.run()
  _classify_result = result
  if result.success:
    print(f"\n{'='*60}")
    print(f"  薄壁件组(T{thk}_shell): {len(result.thin_parts)} 组")
    for p in result.thin_parts:
      n_solids = _count_solids(p.comp_id)
      print(f"    {p.name}: {n_solids}个实体")
    print(f"  中厚件组(T{thk}_solid): {len(result.mid_thick_parts)} 组")
    for p in result.mid_thick_parts:
      n_solids = _count_solids(p.comp_id)
      print(f"    {p.name}: {n_solids}个实体")
    print(f"  厚实体组(T{thk}_solid): {len(result.thick_parts)} 组")
    for p in result.thick_parts:
      n_solids = _count_solids(p.comp_id)
      print(f"    {p.name}: {n_solids}个实体")
    print(f"  微小件: {len(result.small_parts)} 组")
    print(f"{'='*60}")
    print(f"\n  下一步: del_small() 删除微小件 → batchmesh()(薄壁) + solid_mesh()(中厚/厚)")
    print(f"  手动纠正: move_to_thick(*ids) 或 move_to_thin(*ids)")
  return c

def move_to_thick(*comp_ids):
  """手动纠正: 把指定 comp_id 从薄壁件/中厚件移到厚实体: move_to_thick(1, 2, 3)"""
  global _classify_result
  if _classify_result is None: print("请先运行 classify()"); return
  moved = []
  for cid in comp_ids:
    cid = int(cid)
    for lst in [_classify_result.thin_parts, _classify_result.small_parts, _classify_result.mid_thick_parts]:
      for p in list(lst):
        if p.comp_id == cid:
          lst.remove(p)
          p.category = "thick"
          _classify_result.thick_parts.append(p)
          moved.append(cid)
          break
  if moved:
    print(f"已移动 {len(moved)} 个到厚实体")
    print(f"  薄壁件: {len(_classify_result.thin_parts)} → batchmesh()")
    print(f"  中厚件: {len(_classify_result.mid_thick_parts)}")
    print(f"  厚实体: {len(_classify_result.thick_parts)} → solid_mesh()")
  else:
    print("未找到匹配的零件")

def move_to_thin(*comp_ids):
  """手动纠正: 把指定 comp_id 从厚实体/中厚件移到薄壁件: move_to_thin(1, 2, 3)"""
  global _classify_result
  if _classify_result is None: print("请先运行 classify()"); return
  moved = []
  for cid in comp_ids:
    cid = int(cid)
    for lst in [_classify_result.thick_parts, _classify_result.mid_thick_parts]:
      for p in list(lst):
        if p.comp_id == cid:
          lst.remove(p)
          p.category = "thin"
          _classify_result.thin_parts.append(p)
          moved.append(cid)
          break
  if moved:
    print(f"已移动 {len(moved)} 个到薄壁件")
    print(f"  薄壁件: {len(_classify_result.thin_parts)} → batchmesh()")
    print(f"  中厚件: {len(_classify_result.mid_thick_parts)}")
    print(f"  厚实体: {len(_classify_result.thick_parts)} → solid_mesh()")
  else:
    print("未找到匹配的厚实体/中厚件")

def del_small():

  """删除微小件"""
  global _classify_result
  from modules.geometry_classify import GeometryClassifier
  c = GeometryClassifier()
  if _classify_result:
    c._result = _classify_result
    deleted = c.delete_small_parts()
  else:
    result = c.run()
    deleted = c.delete_small_parts()
    _classify_result = c.result
  print(f"已删除 {len(deleted)} 个微小件")

def batchmesh(size=5.0):
  """薄壁件壳网格: batchmesh(size=5.0)
  只对薄壁件运行 batchmesh2（midmesh 模式: 中面+壳网格）
  厚实体需单独用 solid_mesh() 划分体网格
  """
  global _classify_result
  if _classify_result is None: print("请先运行 classify()"); return
  thin_ids = [int(p.comp_id) for p in _classify_result.thin_parts]
  if not thin_ids: print("没有薄壁件"); return
  print(f"BatchMesher 壳网格: {len(thin_ids)} 组薄壁件(T厚_shell) → midmesh")
  api_batchmesh2(None, thin_ids, elem_size=size, param_mode="midmesh")
  print(f"壳网格完成: size={size}mm")

def solid_mesh(size=5.0):
  """厚实体六面体网格: solid_mesh(size=5.0)
  中厚件(10-15mm): elemoffset_thinsolid 六面体, 3层
  厚实体(≥15mm): elemoffset_thinsolid 六面体, t/5层
  """
  global _classify_result
  if _classify_result is None: print("请先运行 classify()"); return

  mid_ids = [int(p.comp_id) for p in _classify_result.mid_thick_parts]
  thick_ids = [int(p.comp_id) for p in _classify_result.thick_parts]

  # 中厚件: 固定 3 层
  if mid_ids:
    print(f"中厚件六面体: {len(mid_ids)} 个 → elemoffset_thinsolid (3层, {size}mm)")
    api_elemoffset_thinsolid(None, mid_ids, num_layers=3, elem_size=size)

  # 厚实体: 层数 = ceil(t / 5)
  if thick_ids:
    for p in _classify_result.thick_parts:
      thick = api_get_solid_thickness(None, p.comp_id)
      if thick <= 0:
        thick = 2.0 * p.volume / p.surface_area if p.surface_area > 0 else 20.0
      layers = max(2, int(thick / 5.0 + 0.5))
      print(f"  厚实体 comp{p.comp_id} '{p.name}': t≈{thick:.1f}mm → {layers}层")
      api_elemoffset_thinsolid(None, [p.comp_id], num_layers=layers, elem_size=size)

  print(f"六面体网格完成: 中厚{len(mid_ids)}个 + 厚{len(thick_ids)}个")

# ========== 诊断 & 工具 ==========

def diag(comp_id):
  """诊断组件真实厚度: diag(comp_id)"""
  api_diag_thickness(int(comp_id))

def cleanup(tol=0.5, hole=5.0):
  """几何清理: cleanup(tol=0.5, hole=5.0)"""
  api_stitch_free_edges(None, tol); print(f"[1/4] 缝合自由边 tol={tol}")
  api_equivalence(None, 0.1); print("[2/4] 等效节点")
  api_surface_merge(None, 30.0, 0.0, 100.0); print("[3/4] 合并曲面")
  api_fill_holes(None, hole); print(f"[4/4] 填孔 max={hole}mm")
  print("几何清理完成")

def panel():
  """打开控制面板（非阻塞）"""
  import threading, time
  def _run():
    import tkinter as tk
    from tkinter import ttk
    from utils.hw_api import get_model_name as _gn

    class _P(tk.Tk):
      def __init__(self):
        super().__init__()
        self.title(f"Forklift Tools - {_gn()}")
        self.geometry("320x350")
        self.resizable(False, False)
        ttk.Label(self, text="Forklift Structure Modeling", font=("", 12, "bold")).pack(pady=(10, 3))
        ttk.Label(self, text="Chassis | Overhead Guard", foreground="gray").pack(pady=(0, 8))
        ttk.Separator(self).pack(fill=tk.X, padx=20)
        ttk.Label(self, text="Step 1: Import geometry manually in HyperMesh", foreground="gray").pack(pady=(5, 1))
        ttk.Label(self, text="File > Import > Geometry", foreground="gray").pack(pady=(0, 5))
        ttk.Separator(self).pack(fill=tk.X, padx=20)
        ttk.Label(self, text="Automation Tools", font=("", 10)).pack(pady=(8, 3))
        tools_dir = os.path.join(_PROJECT_DIR, "tools")
        btns = [
          ("[1] Extract Midsurface",    "extract_midsurface.py"),
          ("[2] Assign Properties",     "assign_property.py"),
          ("[3] Auto Meshing",          "auto_mesh.py"),
          ("[4] Create Connectors",     "create_connectors.py"),
        ]
        for label, fn in btns:
          fp = os.path.join(tools_dir, fn)
          ttk.Button(self, text=label, width=32,
            command=lambda f=fp: exec(open(f, encoding="utf-8").read())).pack(pady=3, padx=20)
        ttk.Separator(self).pack(fill=tk.X, padx=20, pady=(10, 3))
        fp = os.path.join(tools_dir, "run_all.py")
        ttk.Button(self, text=">> Full Pipeline", width=32,
          command=lambda: exec(open(fp, encoding="utf-8").read())).pack(pady=3)
        fp = os.path.join(tools_dir, "clear_all.py")
        ttk.Button(self, text="Clear All", width=32,
          command=lambda: exec(open(fp, encoding="utf-8").read())).pack(pady=3)
        ttk.Separator(self).pack(fill=tk.X, padx=20, pady=(10, 3))
        ttk.Label(self, text="Edit script params before clicking", foreground="gray").pack()
    _P().mainloop()

  t = threading.Thread(target=_run, daemon=True)
  t.start()
  time.sleep(0.5)
  print("面板已打开（非阻塞，控制台仍可用）")

print("\n快捷命令: classify() del_small() batchmesh() solid_mesh() move_to_thick() move_to_thin()")
print("         cleanup() assign_shell() assign_solid() assign_all() weld() cls() panel()")
print("厚实体: solid_mesh() → 中厚件(10-15mm)3层六面体 + 厚实体(≥15mm)t/5层六面体")
print("诊断命令: diag(comp_id) — 查看任意组件的几何厚度")
logger.info("就绪")

"""
HyperWorks API 抽象层（HM 2026）
通过 hm.Model("@模型名") 获取实例，evaltclstring 执行 Tcl
"""
import sys, os

_HM = None
_HM_AVAILABLE = False
_DETECTED = False
_MODEL = None


def _detect_hm():
  global _HM, _HM_AVAILABLE, _MODEL, _DETECTED
  if _DETECTED:
    return
  _DETECTED = True

  try:
    import __main__
    if not hasattr(__main__, "hm"):
      raise RuntimeError("HM 不可用")
    hm_mod = __main__.hm
    _HM = hm_mod

    session = hm_mod.Session()
    model_name = session.get_current_model()
    if isinstance(model_name, str) and model_name:
      _MODEL = hm_mod.Model(model_name)
      _HM_AVAILABLE = True
      from utils.logger import logger
      logger.info(f"已连接 HyperWorks 2026, Model: {model_name}")
      return
  except Exception:
    pass

  _HM_AVAILABLE = False


def is_available() -> bool:
  _detect_hm()
  return _HM_AVAILABLE


def get_hm():
  _detect_hm()
  if not _HM_AVAILABLE:
    raise RuntimeError("HyperMesh 不可用，请在 HM Python 控制台中运行")
  return _HM


def get_model():
  _detect_hm()
  return _MODEL


class HwSession:
  def __init__(self):
    self._hm = None
    self.connected = False
  def connect(self):
    try:
      self._hm = get_hm()
      self.connected = True
    except RuntimeError:
      self.connected = False
      raise
  def disconnect(self):
    self._hm = None
    self.connected = False
  @property
  def hm(self):
    if not self.connected or self._hm is None:
      raise RuntimeError("未连接到 HyperMesh 会话")
    return self._hm


def get_session() -> HwSession:
  s = HwSession()
  s.connect()
  return s


# ===================== Tcl 执行（核心） =====================

def exec_tcl(tcl_cmd: str):
  """执行 Tcl 命令（不读返回值）"""
  global _MODEL
  if _MODEL is None:
    _detect_hm()
  if _MODEL is not None:
    return _MODEL.evaltclstring(tcl_cmd, 0)


def exec_tcl_quiet(tcl_cmd: str):
  """执行 Tcl 命令，忽略错误（不抛异常）"""
  global _MODEL
  if _MODEL is None:
    _detect_hm()
  if _MODEL is not None:
    try:
      return _MODEL.evaltclstring(tcl_cmd, 0)
    except Exception:
      return None
  return None


def exec_tcl_ret(tcl_cmd: str) -> str:
  """执行 Tcl 并尝试读回字符串"""
  r = exec_tcl(tcl_cmd)
  if r is None:
    return ""
  try:
    return str(r.message) if hasattr(r, 'message') else str(r)
  except:
    return ""


# ===================== 几何导入 =====================

def api_import_parasolid(*args):
  """导入 Parasolid 几何文件
  用法1 (tools): api_import_parasolid(filepath, scale=1.0)
  用法2 (modules): api_import_parasolid(session, filepath, scale=1.0)
  """
  if len(args) >= 1 and hasattr(args[0], 'connected'):
    # 模块调用模式: (session, filepath, scale)
    session, filepath, scale = args[0], str(args[1]), float(args[2]) if len(args) > 2 else 1.0
  else:
    # 脚本调用模式: (filepath, scale)
    filepath, scale = str(args[0]), float(args[1]) if len(args) > 1 else 1.0
  fp = filepath.replace("\\", "/")
  # 设置编码为 GBK 以支持中文名（防止乱码）
  tcl = (
    f"*hwencoding gbk; "
    f"*createstringarray 1 \"{fp}\"; *feinput parasolid files 1 format 3 scale {scale}; *autofitview"
  )
  exec_tcl(tcl)


# ===================== BatchMesher（核心） =====================

def api_batchmesh2(
  session=None, comp_ids=None,
  criteria_file: str = None, param_file: str = None,
  elem_size: float = 5.0, elem_type: int = 2,
  param_mode: str = "midmesh",
  no_geom_cleanup: int = 0, no_remove_holes: int = 0,
  **kwargs
):
  """BatchMesher - 几何清理 + 去特征 + 中面 + 2D 壳网格 一步完成
  核心函数，替代 api_extract_midsurface + api_auto_mesh
  仅支持 Python API（在 HM 控制台中运行）

  参数:
    session:          HwSession 对象（可省略）
    comp_ids:         组件 ID 列表，None=全部
    criteria_file:    .criteria 文件路径，None=用默认 crash_5mm.criteria
    param_file:       .param 文件路径，None=用默认 crash_5mm_midmesh.param
    elem_size:        目标单元尺寸 (mm)
    elem_type:        0=trias, 1=quads, 2=mixed
    param_mode:       "midmesh" / "shell" / "generic" / "solid"
    no_geom_cleanup:  0=允许几何清理, 1=跳过
    no_remove_holes:  0=允许去小孔, 1=保留所有孔
  """
  from utils.logger import logger

  # 确定 param/criteria 文件路径
  _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  if param_file is None:
    param_file = os.path.join(_root, "batchmesh", "crash_5mm.param")
  if criteria_file is None:
    criteria_file = os.path.join(_root, "batchmesh", "crash_5mm.criteria")

  param_file = param_file.replace("\\", "/")
  criteria_file = criteria_file.replace("\\", "/")

  # 获取 HM 模块和模型
  hm_mod = get_hm()
  model = get_model()
  if model is None:
    raise RuntimeError("未找到 HyperMesh Model，请在 HM 控制台中运行")

  # 获取 hm.entities 子模块
  ent = None
  try:
    import hm.entities as _ent
    ent = _ent
  except ImportError:
    ent = hm_mod.entities

  # 统计组件信息
  if comp_ids:
    comp_count = len(comp_ids)
    comp_list = comp_ids
  else:
    _, result = model.hm_entitylist(entity=ent.Component, listType="id")
    comp_list = list(result.entityList) if hasattr(result.entityList, 'tolist') else list(result.entityList)
    comp_count = len(comp_list)

  logger.info("=" * 50)
  logger.info(f"BatchMesher 开始")
  logger.info(f"  组件总数: {comp_count}")
  logger.info(f"  单元尺寸: {elem_size}mm")
  logger.info(f"  模式: {param_mode}")
  logger.info(f"  param: {os.path.basename(param_file)}")
  logger.info(f"  criteria: {os.path.basename(criteria_file)}")
  logger.info(f"  预计操作: 几何清理 -> 去特征(孔/圆角/凸台) -> 中面抽取 -> 壳网格")
  logger.info(f"  (复杂模型可能需要数分钟，请等待...)")
  logger.info("=" * 50)

  # 构建实体集合 - batchmesh2 只接受 Component
  if comp_ids:
    surf_col = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, comp_ids))
  else:
    surf_col = hm_mod.Collection(model, ent.Component)
  model.batchmesh2(
    collection=surf_col,
    criteria_file=criteria_file,
    param_file=param_file,
    elemSize=elem_size,
    elemType=elem_type,
    paramsGenerateMode=param_mode,
    noGeomCleanup=no_geom_cleanup,
    noRemoveHoles=no_remove_holes,
    keepPlotElems=1,
    **kwargs,
  )
  logger.info("BatchMesher 完成")


def api_tetmesh(comp_ids: list, elem_size: float = 8.0, **kwargs):
  """厚实体四面体网格

  参数:
    comp_ids: 组件 ID 列表
    elem_size: 目标单元尺寸 (mm)
  """
  from utils.logger import logger

  if not comp_ids:
    logger.warn("tetmesh: 没有组件")
    return

  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities

  # 构建 solid collection
  solid_ids = []
  for cid in comp_ids:
    try:
      comp_sel = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(cid)]))
      solid_col = hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Solid, ent.Component), comp_sel)
      for solid in solid_col:
        solid_ids.append(int(solid.id))
    except Exception:
      pass

  if not solid_ids:
    logger.warn("未找到 Solid 实体")
    return

  logger.info(f"tetmesh 开始: {len(solid_ids)} 个 Solid, size={elem_size}mm")

  solid_collection = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Solid, solid_ids))

  # 2D surface mesh first, then tet mesh
  model.tetmesh(collection=solid_collection, mode=0,
                element_size=elem_size, type=2)


def api_elemoffset_thinsolid(session=None, comp_ids=None, num_layers=3, elem_size=5.0):
  """六面体网格 — elemoffset_thinsolid（板类实体）
  自动检测源面/目标面/侧面，生成六面体为主的实体网格。

  参数:
    session:    HwSession（可选）
    comp_ids:   组件 ID 列表
    num_layers: 厚度方向层数
    elem_size:  面内单元尺寸 (mm)
  """
  if not comp_ids:
    return

  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities

  for cid in comp_ids:
    try:
      comp_sel = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(cid)]))
      solid_col = hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Solid, ent.Component), comp_sel)
      empty_surfs = hm_mod.Collection(model, ent.Surface, populate=False)

      string_array = hm.hwStringList()
      # "2d: <elem_type> <elem_order> <method> <size> <min_size> <feature_angle> <mesh_flow>"
      # elem_type=2(Mixed), elem_order=1(First), method=2(free)
      string_array.append(f"2d: 2 1 2 {elem_size} 1.5 25.0 1")

      model.elemoffset_thinsolid(
        collection_source=solid_col,
        collection_target=empty_surfs,
        collection_along=empty_surfs,
        modes=128,              # Bit6-7=10: 自动检测源面/目标面/侧面
        density=num_layers,
        biasing=0.0,
        string_array=string_array,
        batchmesh_source=1,
      )
      logger.info(f"elemoffset_thinsolid: comp{cid} done ({num_layers} layers, {elem_size}mm)")
    except Exception as e:
      logger.warn(f"elemoffset_thinsolid comp{cid} failed: {e}")


def api_group_solids_by_thickness(session=None) -> dict:
  """遍历模型中所有 Solid，按 hm_getgeometricthinsolidinfo 厚度分组

  返回:
    {
      "solid_info": [(solid_id, thickness), ...],    # 所有有效的 solid
      "shell_groups":  {thickness_key: [solid_id, ...]},   # ≤10mm
      "mid_groups":    {thickness_key: [solid_id, ...]},   # 10-15mm
      "thick_groups":  {thickness_key: [solid_id, ...]},   # ≥15mm
    }
  """
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities

  all_solids = hm_mod.Collection(model, ent.Solid)
  if len(all_solids) == 0:
    return {"solid_info": [], "shell_groups": {}, "mid_groups": {}, "thick_groups": {}}

  _, result_list = model.hm_getgeometricthinsolidinfo(collection=all_solids, mode="simple")
  if not result_list:
    return {"solid_info": [], "shell_groups": {}, "mid_groups": {}, "thick_groups": {}}

  solid_info = []
  shell_groups = {}
  mid_groups = {}
  thick_groups = {}

  for r in result_list:
    sid = int(r.entity.id)
    t = float(r.thickness)
    if t <= 0:
      continue

    solid_info.append((sid, t))
    t_key = f"{t:.1f}"

    if t <= 10.0:
      shell_groups.setdefault(t_key, []).append(sid)
    elif t < 15.0:
      mid_groups.setdefault(t_key, []).append(sid)
    else:
      thick_groups.setdefault(t_key, []).append(sid)

  return {
    "solid_info": solid_info,
    "shell_groups": shell_groups,
    "mid_groups": mid_groups,
    "thick_groups": thick_groups,
  }


def api_move_solids_to_new_component(comp_name: str, solid_ids: list) -> int:
  """创建新 Component 并将指定 Solid 移入，返回新 comp_id

  用 Tcl 命令实现: *collectorcreate → *createmark → *movemark
  """
  ids_str = " ".join(str(int(s)) for s in solid_ids)
  exec_tcl(
    f"*collectorcreate components \"{comp_name}\" \"\" 11; "
    f"*createmark solids 1 {ids_str}; "
    f"*movemark solids 1 \"{comp_name}\""
  )

  # 获取新创建 component 的 ID
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities
  try:
    comp = model.get(ent.Component, f'name="{comp_name}"')
    cid = int(comp.id)
    from utils.logger import logger
    logger.info(f"创建组件 '{comp_name}' (id={cid}), 移入 {len(solid_ids)} 个 Solid")
    return cid
  except Exception:
    return 0


# ===================== 中面抽取 =====================

def api_extract_midsurface(*args):
  """批量抽取中面
  用法1 (tools): api_extract_midsurface([1, 2, 3])
  用法2 (modules): api_extract_midsurface(session, [1, 2, 3])
  """
  if len(args) >= 1 and hasattr(args[0], 'connected'):
    comp_ids = list(args[1]) if len(args) > 1 else []
  else:
    comp_ids = list(args[0]) if args else []
  ids_str = " ".join(str(i) for i in comp_ids)
  # 参数说明:
  #   outbound_normals=3 (实体), thickness_bound=0 (自动无限制)
  #   align_steps=0, extract_by_comp=0 (任意匹配对)
  #   rerun_type=9 (offset+planes+sweeps — 最强方法)
  #   stitch_tol_mode=1 (用清理容差缝合), max_R_t_ratio=2
  #   max_thickness_ratio=10, min_thickness=2, max_thickness=30
  #   mid_position=0.5, new_or_curr_comp=1 (新 Middle Surface 组件)
  tcl = (
    f"*createmark comps 1 {ids_str}; "
    f"*midsurface_extract_10 comps 1 3 0 0 0 9 1 2 0 0 10 2 30 0.5 0 0 1; "
    f"*redraw"
  )
  exec_tcl(tcl)


# ===================== 网格划分 =====================

def api_auto_mesh(*args):
  """自动网格划分
  用法1 (tools): api_auto_mesh(comp_id, size=5.0, elem_type="mixed")
  用法2 (modules): api_auto_mesh(session, comp_id, size=5.0, elem_type="mixed")
  """
  if len(args) >= 1 and hasattr(args[0], 'connected'):
    comp_id = int(args[1]) if len(args) > 1 else 0
    size = float(args[2]) if len(args) > 2 else 5.0
    elem_type = str(args[3]) if len(args) > 3 else "mixed"
  else:
    comp_id = int(args[0]) if args else 0
    size = float(args[1]) if len(args) > 1 else 5.0
    elem_type = str(args[2]) if len(args) > 2 else "mixed"
  tcl = f"*createmark comps 1 {comp_id}; *automesh comps 1 {size} 1 {elem_type} 0 0 0 0 3 0 0"
  exec_tcl(tcl)


# ===================== 属性赋参 =====================

def api_assign_property(*args):
  """属性赋参
  用法1 (tools): api_assign_property(comp_id, material_dict, thickness=6.0, card_type="PSHELL")
  用法2 (modules): api_assign_material(session, comp_id, material_dict, thickness=6.0, card_type="PSHELL")
  """
  if len(args) >= 1 and hasattr(args[0], 'connected'):
    comp_id = int(args[1]) if len(args) > 1 else 0
    material = args[2] if len(args) > 2 else {}
    thickness = float(args[3]) if len(args) > 3 else 6.0
    card_type = str(args[4]) if len(args) > 4 else "PSHELL"
  else:
    comp_id = int(args[0]) if args else 0
    material = args[1] if len(args) > 1 else {}
    thickness = float(args[2]) if len(args) > 2 else 6.0
    card_type = str(args[3]) if len(args) > 3 else "PSHELL"
  mat_name = f"MAT_{material.get('yield','X')}"
  prop_name = f"prop_{comp_id}"

  exec_tcl(
    f"*collectorcreate materials \"{mat_name}\" \"\" 11; "
    f"*setvalue materials id=1 STATUS=1 1=1; "
    f"*materialupdate materials 1 E={material['E']} NU={material['nu']} RHO={material['rho']}"
  )

  if card_type == "PSHELL":
    exec_tcl(
      f"*collectorcreate properties \"{prop_name}\" \"PSHELL\" 11; "
      f"*setvalue props id=1 STATUS=1 95=1 1={thickness}"
    )
  else:
    exec_tcl(
      f"*collectorcreate properties \"{prop_name}\" \"PSOLID\" 11; "
      f"*setvalue props id=1 STATUS=1 95=1"
    )

  exec_tcl(
    f"*createmark comps 1 {comp_id}; "
    f"*componentupdate comps 1 1 0 \"{prop_name}\" 1 0 \"{mat_name}\""
  )


# ===================== 连接器 =====================

def _normalize_connector_args(args, default_gap=1.5):
  """统一处理连接器函数的参数
  返回 (comp_a, comp_b, value)，comp_a 为 None 表示调用无效
  支持:
    (comp_a, comp_b, value)
    (session, comp_a, comp_b, value)
    (session, entity_list, value)     → 从列表提取 comp_a/comp_b
  """
  if not args:
    return None, None, default_gap

  # 移除非法的 session 参数（第一个 arg 是 HwSession 或有 connected 属性）
  _args = list(args)
  if hasattr(_args[0], 'connected'):
    _args = _args[1:]

  if not _args:
    return None, None, default_gap

  arg0 = _args[0]

  # 列表/字典模式 (entity data from connectors module)
  if isinstance(arg0, (list, dict)):
    entity_data = arg0
    comp_a = comp_b = 0
    if isinstance(entity_data, list) and len(entity_data) > 0:
      item = entity_data[0]
      if isinstance(item, dict):
        comp_a = int(item.get("source", 0))
        comp_b = int(item.get("target", 0))
    elif isinstance(entity_data, dict):
      comp_a = int(entity_data.get("source", 0))
      comp_b = int(entity_data.get("target", 0))
    value = float(_args[1]) if len(_args) > 1 else default_gap
    return comp_a, comp_b, value

  # 数值模式 (component IDs directly)
  comp_a = int(arg0) if arg0 is not None else 0
  comp_b = int(_args[1]) if len(_args) > 1 else 0
  value = float(_args[2]) if len(_args) > 2 else default_gap
  return comp_a, comp_b, value


def api_create_seam_weld(*args):
  """创建缝焊连接器
  简单: api_create_seam_weld(comp_a, comp_b, gap_tol)
  模块: api_create_seam_weld(session, comp_data_or_list, comp_b_or_gap, gap_tol)
  连接器模块: api_create_seam_weld(session, [{"source":1, "target":2}], gap_tol)
  """
  comp_a, comp_b, gap_tol = _normalize_connector_args(args, default_gap=1.5)
  if comp_a is None:
    return
  exec_tcl(
    f"*createmark comps 1 {comp_a} {comp_b}; "
    f"*findedges comps 1 {gap_tol} 1 0; "
    f"*connectorcreate seam lines 1 {gap_tol}"
  )


def api_create_bolt(*args):
  """创建螺栓连接器
  简单: api_create_bolt(comp_a, comp_b, diameter)
  模块: api_create_bolt(session, comp_data_or_list, comp_b_or_dia, diameter)
  """
  comp_a, comp_b, diameter = _normalize_connector_args(args, default_gap=10.0)
  if comp_a is None:
    return
  exec_tcl(
    f"*createmark comps 1 {comp_a} {comp_b}; "
    f"*findholes comps 1 8 30 0.5 0.5; "
    f"*connectorcreate bolt lines 1 {diameter}"
  )


def api_create_spot_weld(*args):
  """创建焊点连接器
  简单: api_create_spot_weld(comp_a, comp_b, spacing)
  模块: api_create_spot_weld(session, comp_data_or_list, comp_b_or_spacing, spacing)
  """
  comp_a, comp_b, spacing = _normalize_connector_args(args, default_gap=40.0)
  if comp_a is None:
    return
  exec_tcl(
    f"*createmark comps 1 {comp_a} {comp_b}; "
    f"*connectorcreate spot comps 1 {spacing}"
  )


# ===================== 导出 =====================

def api_export_optistruct(filepath: str):
  fp = filepath.replace("\\", "/")
  exec_tcl(f"*feoutput OptiStruct \"{fp}\" 1 0 0 0 1 0 0 0")


def api_clear_all():
  exec_tcl("*createmark comps 1 all; *deletemark comps 1; *autofitview")


# ===================== 几何清理 =====================

def api_geometry_cleanup(session=None, comp_ids=None, cleanup_tolerance: float = 0.5):
  """自动拓扑清理 — 修复自由边、缝合间隙、简化特征
  这是几何清理的核心函数，对应 HM GUI 的 Surface Repair → Validate 自动修复
  """
  if comp_ids:
    ids_str = " ".join(str(i) for i in comp_ids)
    tcl = f"*createmark comps 1 {ids_str}"
  else:
    tcl = "*createmark comps 1 all"
  # autotopocleanup: 自动拓扑清理 — 修复自由边、缝隙、重复面
  tcl += f"; *autotopocleanup comps 1 {cleanup_tolerance}"
  exec_tcl(tcl)


def api_surface_merge(session=None, break_angle: float = 30.0, min_radius: float = 0.0, max_radius: float = 100.0):
  """合并相邻曲面（去除冗余边）"""
  tcl = (
    f"*createmark surfs 1 all; "
    f"*surfacemarkmerge surfs 1 {break_angle} {min_radius} {max_radius}"
  )
  exec_tcl(tcl)


def api_fill_holes(session=None, hole_max_size: float = 5.0):
  """填充曲面上的孔/缝隙
  hole_max_size: 最大孔尺寸 (mm)，小于此值的孔会被填掉
  """
  tcl = (
    f"*createmark surfs 1 all; "
    f"*defeatureholes surfs 1 {hole_max_size}"
  )
  exec_tcl(tcl)


def api_remove_small_fillets(session=None, fillet_max_radius: float = 3.0):
  """去除小圆角特征"""
  tcl = (
    f"*createmark surfs 1 all; "
    f"*surfacefilletremove surfs 1 {fillet_max_radius} 0"
  )
  exec_tcl(tcl)


def api_equivalence(session=None, tolerance: float = 0.1):
  """等效节点/边 — 在容差范围内合并重合的节点和边"""
  tcl = f"*equivalence comps 1 {tolerance} 1 0 0 0 0 0"
  exec_tcl(tcl)


def api_create_solid_from_surfaces(session=None):
  """从闭合曲面创建实体 (Closed Shell → Solid)"""
  tcl = (
    f"*createmark surfs 1 all; "
    f"*solidfromsurfs surfs 1 0 0 0 0 0"
  )
  exec_tcl(tcl)


def api_stitch_free_edges(session=None, tolerance: float = 0.5):
  """缝合自由边 — 在容差内将自由边缝合为共享边"""
  tcl = (
    f"*createmark surfs 1 all; "
    f"*edgestitch surfs 1 {tolerance}"
  )
  exec_tcl(tcl)


# ===================== 组件查询 =====================

def api_get_component_list(session=None) -> list:
  """获取模型中所有组件 ID 列表"""
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities
  _, result = model.hm_entitylist(entity=ent.Component, listType="id")
  ids = result.entityList
  # 转为 Python int（去掉 numpy 类型）
  return [int(i) for i in ids]


def api_get_component_name(session=None, comp_id: int = 0) -> str:
  """获取组件名称 — 直接从 Component entity 读 name 属性"""
  if not comp_id:
    return ""
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities

  comp = ent.Component(model, int(comp_id))
  name = getattr(comp, 'name', None)
  if name:
    return str(name)
  return f"comp_{comp_id}"


def api_get_component_volume(session=None, comp_id: int = 0) -> float:
  """获取组件真实体积

  优先级:
    1. hm_getmass → totalvolume（需要材料属性）
    2. hm_getgeometricthinsolidinfo（仅适用薄壁件）
    3. 遍历 Solid 实体读取 volume 属性
    4. 包络盒估算
  """
  if not comp_id:
    return 0.0
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities

  # 方法1: hm_getmass
  try:
    comp_col = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(comp_id)]))
    _, result = model.hm_getmass(collection=comp_col, mass_type=1)
    v = getattr(result, 'totalvolume', None)
    if v is not None and float(v) > 0:
      return float(v)
  except Exception:
    pass

  # 方法2: 遍历 Solid 实体读取 volume 属性
  try:
    comp_sel = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(comp_id)]))
    solid_col = hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Solid, ent.Component), comp_sel)
    total_vol = 0.0
    for solid in solid_col:
      v = getattr(solid, 'volume', None)
      if v is not None and float(v) > 0:
        total_vol += float(v)
    if total_vol > 0:
      return total_vol
  except Exception:
    pass

  # 方法3: 包络盒估算
  try:
    bbox = api_get_component_bbox(None, comp_id)
    dx = bbox[3] - bbox[0]; dy = bbox[4] - bbox[1]; dz = bbox[5] - bbox[2]
    if dx <= 0 or dy <= 0 or dz <= 0:
      return 0.0
    return dx * dy * dz * 0.5
  except Exception:
    return 0.0


def api_get_component_area(session=None, comp_id: int = 0) -> float:
  """获取组件真实表面积 — 通过 hm_getmass API"""
  if not comp_id:
    return 0.0
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities
  try:
    comp_col = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(comp_id)]))
    _, result = model.hm_getmass(collection=comp_col, mass_type=1)
    a = getattr(result, 'totalarea', None)
    if a is not None and float(a) > 0:
      return float(a)
  except Exception:
    pass
  # 回退: 包络盒估算
  try:
    bbox = api_get_component_bbox(None, comp_id)
    dx = bbox[3] - bbox[0]; dy = bbox[4] - bbox[1]; dz = bbox[5] - bbox[2]
    if dx > 0:
      return 2 * (dx*dy + dy*dz + dx*dz) * 1.5
  except Exception:
    pass
  return 0.0


def api_get_component_bbox(session=None, comp_id: int = 0):
  """获取组件包络盒，返回 (xmin, ymin, zmin, xmax, ymax, zmax)"""
  if not comp_id:
    return (0, 0, 0, 0, 0, 0)
  try:
    hm_mod = get_hm()
    model = get_model()
    try:
      import hm.entities as ent
    except ImportError:
      ent = hm_mod.entities
    comp_col = hm_mod.Collection(model, ent.Component, [int(comp_id)])
    _, result = model.hm_getboundingbox(
      entityCollection=comp_col, entityFlag=3, systemID=0, boxType=0
    )
    min_vals = result.minValues
    max_vals = result.maxValues
    return (
      float(min_vals[0]), float(min_vals[1]), float(min_vals[2]),
      float(max_vals[0]), float(max_vals[1]), float(max_vals[2]),
    )
  except Exception:
    return (0, 0, 0, 0, 0, 0)


def api_get_component_thickness(session=None, comp_id: int = 0) -> float:
  """获取组件厚度（中面抽取后）"""
  if not comp_id:
    return 0.0
  try:
    hm_mod = get_hm()
    import hm.entities as ent
    model = get_model()
    # 通过中面厚度查询
    comp = ent.Component(model, comp_id)
    surf_col = hm_mod.Collection(model, ent.Surface)
    # 使用曲面厚度查询
    _, results = model.hm_getsurfacethicknessvalues_bycollection(
      collection=surf_col, element_method=4, ambiguous_values=1
    )
    if hasattr(results, '__iter__'):
      thicknesses = [r.thickness for r in results if hasattr(r, 'thickness')]
      if thicknesses:
        return sum(thicknesses) / len(thicknesses)
  except Exception:
    pass
  # Tcl 回退
  tcl = f"*createmark comps 1 {comp_id}; *getvalue comps id={comp_id} dataname=thickness"
  r = exec_tcl_ret(tcl)
  try:
    import re
    nums = re.findall(r"[\d.]+", str(r))
    if nums:
      return float(nums[-1])
  except (ValueError, IndexError):
    pass
  return 6.0  # 默认板厚


# ===================== 组件厚度查询（基于 Solid） =====================

def api_get_solid_thickness(session=None, comp_id: int = 0) -> float:
  """通过 hm_getgeometricthinsolidinfo 获取实体的几何厚度（可靠的板厚值）
  返回组件内所有 Solid 的平均厚度，失败返回 0
  """
  if not comp_id:
    return 0.0
  try:
    hm_mod = get_hm()
    model = get_model()
    try:
      import hm.entities as ent
    except ImportError:
      ent = hm_mod.entities

    comp_sel = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(comp_id)]))
    solid_col = hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Solid, ent.Component), comp_sel)
    _, resultlist = model.hm_getgeometricthinsolidinfo(collection=solid_col)
    thicknesses = [r.thickness for r in resultlist if hasattr(r, 'thickness') and float(r.thickness) > 0]
    if thicknesses:
      return sum(thicknesses) / len(thicknesses)
  except Exception:
    pass
  return 0.0


def api_diag_thickness(comp_id: int):
  """诊断一个组件的真实几何厚度（用于验证分类策略）"""
  thick = api_get_solid_thickness(None, comp_id)
  bbox = api_get_component_bbox(None, comp_id)
  dx = bbox[3] - bbox[0] if len(bbox) >= 6 else 0
  dy = bbox[4] - bbox[1] if len(bbox) >= 6 else 0
  dz = bbox[5] - bbox[2] if len(bbox) >= 6 else 0
  dims = sorted([dx, dy, dz], reverse=True)
  name = api_get_component_name(None, comp_id)
  vol = api_get_component_volume(None, comp_id)
  area = api_get_component_area(None, comp_id)
  print(f"comp {comp_id} '{name}':")
  print(f"  hm_getgeometricthinsolidinfo 厚度: {thick:.1f}mm")
  print(f"  hm_getmass 体积: {vol:.0f}mm³  面积: {area:.0f}mm²")
  if area > 0 and vol > 0:
    print(f"  2V/A 等效厚度: {2.0*vol/area:.1f}mm")
  print(f"  包络盒: {dx:.0f} x {dy:.0f} x {dz:.0f}")
  if dims[0] > 0:
    print(f"  bbox 厚度(min_dim): {dims[2]:.1f}  bbox_ratio: {dims[2]/dims[0]:.3f}")

def api_get_edges_nearby(session=None, comp_a: int = 0, comp_b: int = 0, gap_tol: float = 1.5) -> list:
  """检测两个组件之间的邻近边（缝焊候选）"""
  if not comp_a or not comp_b:
    return []
  try:
    hm_mod = get_hm()
    import hm.entities as ent
    model = get_model()
    # 使用 proximity API
    comp_col = hm_mod.Collection(model, ent.Component, [comp_a, comp_b])
    status = model.hm_proximityinit(
      collection=comp_col, max_distance=gap_tol,
      mode=2, check_side=3, proximity_scheme=1, proximity_by_edge=0,
      min_angle_limit=0, max_angle_limit=180,
    )
    edges_found = []
    if hasattr(status, 'status') and status.status == 0:
      # 获取组件对
      try:
        _, pair_result = model.hm_proximitygetcomponentpair(0)
        if hasattr(pair_result, 'entityPair'):
          edges_found.append({
            "source": comp_a, "target": comp_b,
            "entities": pair_result.entityPair,
          })
      except Exception:
        pass
    model.hm_proximityend()
    if edges_found:
      return edges_found
  except Exception:
    pass
  # Tcl 回退
  tcl = (
    f"*createmark comps 1 {comp_a} {comp_b}; "
    f"*findedges comps 1 {gap_tol} 1 0 0 0 0"
  )
  r = exec_tcl_ret(tcl)
  # 如果找到边，返回表示有连接的简单标记
  if "0 edges found" not in str(r).lower():
    return [{"source": comp_a, "target": comp_b, "gap": gap_tol}]
  return []


def api_get_holes_matching(
  session=None, comp_a: int = 0, comp_b: int = 0,
  dia_min: float = 8.0, dia_max: float = 30.0,
  dia_tol: float = 0.5, coax_tol: float = 0.5
) -> list:
  """检测两组件间的匹配孔（螺栓候选）"""
  if not comp_a or not comp_b:
    return []
  try:
    hm_mod = get_hm()
    import hm.entities as ent
    model = get_model()
    comp_col = hm_mod.Collection(model, ent.Component, [comp_a, comp_b])
    # 初始化孔检测
    model.hm_holedetectioninit()
    model.hm_holedetectionsetentities(collection=comp_col)
    model.hm_holedetectionsetholeparams(hole_shape=31)
    model.hm_holedetectionfindholes(find=1)
    model.hm_holedetectionfindmates(
      max_angle=5.0, max_distance=coax_tol * 20,
      max_lateral_distance=coax_tol, allow_mismatched_shapes=1, allow_self=0,
    )
    # 获取匹配数量
    _, count_result = model.hm_holedetectiongetnumberofmates()
    num_mates = count_result.numberofMates if hasattr(count_result, 'numberofMates') else 0
    holes_found = []
    for i in range(int(num_mates)):
      try:
        _, mate = model.hm_holedetectiongetmatedetails(i, "id")
        if hasattr(mate, 'entity'):
          holes_found.append({
            "index": i, "source": comp_a, "target": comp_b,
            "entity": mate.entity if hasattr(mate, 'entity') else None,
          })
      except Exception:
        pass
    model.hm_holedetectionend()
    return holes_found
  except Exception:
    pass
  # Tcl 回退
  tcl = (
    f"*createmark comps 1 {comp_a} {comp_b}; "
    f"*findholes comps 1 {dia_min} {dia_max} {dia_tol} {coax_tol}"
  )
  r = exec_tcl_ret(tcl)
  if "0 holes found" not in str(r).lower() and r.strip():
    return [{"source": comp_a, "target": comp_b, "dia_min": dia_min, "dia_max": dia_max}]
  return []


# ===================== 材料属性赋参 =====================

def api_assign_material(
  session=None, comp_id: int = 0,
  material: dict = None, thickness: float = 6.0, card_type: str = "PSHELL"
):
  """给组件赋材料属性（api_assign_property 的别名）"""
  return api_assign_property(comp_id, material, thickness, card_type)


def api_assign_property_shared(thin_groups: list, thick_comp_ids: list,
                                material_db: dict = None):
  """共享材料/属性赋参（geometry_defeature.py 风格）

  薄壁件: 按厚度分组，每组创建 T{thk}_{mat} PSHELL 属性，共用 Q235
  厚实体: 共用 "SW" PSOLID 属性 + Q355

  参数:
    thin_groups:   [(comp_id_list, thickness, material_name), ...]
    thick_comp_ids: 所有厚实体 comp_id 列表
    material_db:    material_db.json 内容 (dict)
  """
  if not material_db:
    material_db = {}

  # ---- Q235 material ----
  mat_q235 = material_db.get("Q235", {"E": 210000, "nu": 0.3, "rho": 7.85e-9})
  exec_tcl(
    f"*collectorcreate materials \"MAT_235\" \"\" 11; "
    f"*setvalue materials id=1 STATUS=1 1=1; "
    f"*materialupdate materials 1 E={mat_q235['E']} NU={mat_q235['nu']} RHO={mat_q235['rho']}"
  )
  logger.info("材料 MAT_235 (Q235) 已创建")

  # ---- Thin parts: PSHELL per thickness group ----
  for comp_ids, thickness, mat_name in thin_groups:
    prop_name = f"T{thickness:.0f}_{mat_name}"
    for cid in comp_ids:
      exec_tcl(
        f"*collectorcreate properties \"{prop_name}\" \"PSHELL\" 11; "
        f"*setvalue props id=1 STATUS=1 95=1 1={thickness}; "
        f"*createmark comps 1 {cid}; "
        f"*componentupdate comps 1 1 0 \"{prop_name}\" 1 0 \"MAT_235\""
      )
    logger.info(f"PSHELL {prop_name}: {len(comp_ids)} 个组件 (T={thickness}mm)")

  # ---- Thick parts: shared PSOLID "SW" with Q355 ----
  if thick_comp_ids:
    mat_q355 = material_db.get("Q355", {"E": 210000, "nu": 0.3, "rho": 7.85e-9})
    exec_tcl(
      f"*collectorcreate materials \"MAT_355\" \"\" 11; "
      f"*setvalue materials id=1 STATUS=1 1=1; "
      f"*materialupdate materials 1 E={mat_q355['E']} NU={mat_q355['nu']} RHO={mat_q355['rho']}"
    )
    logger.info("材料 MAT_355 (Q355) 已创建")

    exec_tcl(
      f"*collectorcreate properties \"SW\" \"PSOLID\" 11; "
      f"*setvalue props id=1 STATUS=1 95=1"
    )
    logger.info("属性 SW (PSOLID) 已创建")

    for cid in thick_comp_ids:
      exec_tcl(
        f"*createmark comps 1 {cid}; "
        f"*componentupdate comps 1 1 0 \"SW\" 1 0 \"MAT_355\""
      )
    logger.info(f"SW PSOLID -> {len(thick_comp_ids)} 个厚实体组件")


# ===================== 模型名获取 =====================

def get_model_name() -> str:
  try:
    hm_mod = get_hm()
    return hm_mod.Session().get_current_model()
  except:
    return "@ImplicitModel_3_1"


# ===================== Part/Representation 管理 =====================

def _get_hm_home() -> str:
  """自动检测 HM 安装目录"""
  for candidate in os.environ.get("ALTAIR_HOME", ""), os.environ.get("HM_HOME", ""):
    if candidate and os.path.isdir(candidate):
      return candidate
  default = "D:/Program Files/Altair/2026/hwdesktop"
  if os.path.isdir(default):
    return default
  return ""


def api_get_part_list(session=None) -> list:
  """获取模型中所有 Part 实体 ID 列表"""
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities
  try:
    _, result = model.hm_entitylist(entity=ent.Part, listType="id")
    ids = result.entityList
    return [int(i) for i in ids]
  except Exception:
    return []


def api_get_part_name(session=None, part_id: int = 0) -> str:
  """获取 Part 名称"""
  if not part_id:
    return ""
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities
  try:
    p = ent.Part(model, int(part_id))
    return str(p.name) if p.name else f"Part_{part_id}"
  except Exception:
    return f"Part_{part_id}"


def api_get_module_id_by_name(part_name: str) -> tuple:
  """根据 Part 名称查询 Occ/Proto ID，返回 (occ_id, proto_id)"""
  if not part_name:
    return None, None

  hm_mod = get_hm()
  model = get_model()
  ent_module = None
  try:
    import hm.entities as _ent
    ent_module = _ent.Module
    ent_part = _ent.Part
  except ImportError:
    ent_module = hm_mod.entities.Module
    ent_part = hm_mod.entities.Part

  occ_id = None
  proto_id = None

  # 遍历 Module 实体，通过 Python 属性匹配
  try:
    _, result = model.hm_entitylist(entity=ent_module, listType="id")
    for mid in result.entityList:
      mid = int(mid)
      try:
        m = ent_module(model, mid)
        uid = getattr(m, 'unique_id', '')
        if uid and part_name in str(uid):
          occ_id = mid
        rev = getattr(m, 'major_revision', '')
        if str(rev).strip() in ("-", ""):
          proto_id = mid
      except Exception:
        pass
  except Exception:
    pass

  # 备选: 遍历 Part 实体
  if occ_id is None:
    try:
      _, result = model.hm_entitylist(entity=ent_part, listType="id")
      for pid in result.entityList:
        pid = int(pid)
        try:
          p = ent_part(model, pid)
          pname = str(p.name) if p.name else ""
          if part_name in pname:
            occ_id = pid
            break
        except Exception:
          pass
    except Exception:
      pass

  return occ_id, proto_id


def api_save_part_rep(session=None, occ_id: int = 0, part_name: str = "",
                      output_file: str = "") -> str:
  """为 Part Occurrence 保存 CAD Representation
  步骤:
    1. *detach_geom → 分离几何到 Parts DB
    2. *filewriteentities → 写为 .hm 文件
    3. *undohistorystate → 撤销分离以恢复视图
  返回: 输出的 .hm 文件路径
  """
  if not occ_id or not output_file:
    return ""

  output_file = output_file.replace("\\", "/")

  # 按名称标记模块（更稳定）
  if not part_name:
    hm_mod = get_hm()
    model = get_model()
    try:
      p = hm_mod.entities.Module(model, occ_id)
      part_name = p.unique_id if hasattr(p, 'unique_id') else f"part_{occ_id}"
    except Exception:
      part_name = f"part_{occ_id}"

  fp = output_file.replace("\\", "/")

  tcl = (
    f'*createmark modules 1 "{part_name}"; '
    f"*detach_geom entitytype=parts mark0=1 organize=1; "
    f"*createmark modules 1 \"{part_name}\"; "
    f'*filewriteentities modules 1 "{fp}" 32 -1; '
    f"*undohistorystate 1"
  )
  exec_tcl(tcl)
  return fp if os.path.isfile(fp) else ""


def api_add_rep_to_part(session=None, proto_id: int = 0, occ_id: int = 0,
                        rep_key: str = "CAD", rep_file: str = "",
                        file_format: str = "hypermesh") -> bool:
  """为 Part Prototype 添加 Representation 并关联文件，然后设置 Occurrence 使用此 Rep

  调用 Python API 执行:
    ME_ModuleRepresentationRemove2 → 删除旧的同名 Rep
    ME_ModuleRepresentationAdd2   → 添加新 Rep
    ME_ModuleRepresentationAddFile2 → 关联 .hm 文件
    ME_ModuleOccurrenceRepresentationSet2 → 设置 Occurrence 显示此 Rep
  """
  if not proto_id or not occ_id or not rep_file:
    return False

  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities

  proto_entity = ent.Part(model, int(proto_id))
  occ_entity = ent.Part(model, int(occ_id))

  rep_file = rep_file.replace("\\", "/")

  try:
    # 先删除旧 Rep（忽略不存在的报错）
    try:
      model.ME_ModuleRepresentationRemove2(part_entity=proto_entity, key=rep_key, reserved="")
    except Exception:
      pass

    # 添加新 Rep
    model.ME_ModuleRepresentationAdd2(
      part_entity=proto_entity, key=rep_key, type="Mesh",
      udm_rep_ref_id="",
    )
    model.ME_ModuleRepresentationAddFile2(
      part_entity=proto_entity, key=rep_key,
      fileformat=file_format, filename=rep_file,
    )
    # 设置 Occurrence 使用此 Rep
    model.ME_ModuleOccurrenceRepresentationSet2(
      part_entity=occ_entity, key=rep_key,
    )
    return True
  except Exception as e:
    from utils.logger import logger
    logger.error(f"添加 Rep 失败 (proto={proto_id}, occ={occ_id}): {e}")
    return False


def api_set_part_rep(occ_id: int = 0, rep_key: str = "CAD") -> bool:
  """设置 Part Occurrence 的当前表示"""
  if not occ_id:
    return False
  hm_mod = get_hm()
  model = get_model()
  try:
    import hm.entities as ent
  except ImportError:
    ent = hm_mod.entities
  try:
    model.ME_ModuleOccurrenceRepresentationSet2(
      part_entity=ent.Part(model, int(occ_id)), key=rep_key,
    )
    return True
  except Exception as e:
    from utils.logger import logger
    logger.error(f"设置 Rep 失败: {e}")
    return False


def api_batchmesh_file(
  input_file: str, output_name: str = "",
  criteria_file: str = None, param_file: str = None,
  output_dir: str = None,
) -> str:
  """使用 hmbm::BatchMesh Tcl 包对 .hm 文件运行 BatchMesher
  完全复现 GUI 右键 Part → BatchMesh 的流程

  参数:
    input_file:     输入 .hm 文件路径（Part 的 CAD Representation）
    output_name:    输出文件名（不含路径），默认基于输入文件名自动生成
    criteria_file:  .criteria 路径，默认用工程 batchmesh/crash_5mm.criteria
    param_file:     .param 路径，默认用工程 batchmesh/crash_5mm.param
    output_dir:     输出目录，默认与输入文件同目录

  返回: 生成的 Crash 5mm .hm 文件路径
  """
  from utils.logger import logger

  input_file = input_file.replace("\\", "/")
  _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

  if criteria_file is None:
    criteria_file = os.path.join(_root, "batchmesh", "crash_5mm.criteria")
  if param_file is None:
    param_file = os.path.join(_root, "batchmesh", "crash_5mm.param")

  criteria_file = criteria_file.replace("\\", "/")
  param_file = param_file.replace("\\", "/")

  # 确定输出路径
  if output_dir is None:
    output_dir = os.path.dirname(input_file)
  output_dir = output_dir.replace("\\", "/")
  if not os.path.isdir(output_dir):
    os.makedirs(output_dir, exist_ok=True)

  base_name = os.path.splitext(os.path.basename(input_file))[0]
  if not output_name:
    output_name = base_name.replace("CAD", "Crash 5mm").replace("Common", "Crash 5mm") + ".hm"
  result_txt = output_name.replace(".hm", "_res.txt")

  criteria_name = os.path.basename(criteria_file)
  param_name = os.path.basename(param_file)

  tmp_dir = os.path.join(output_dir, "tmp_")
  tmp_dir = tmp_dir.replace("\\", "/")

  # 查找 HM 安装目录
  hm_home = _get_hm_home()
  if not hm_home:
    hm_home = "D:/Program Files/Altair/2026/hwdesktop"

  callbacks_path = f"{hm_home}/hm/scripts/br/views/modules/core/batchmesher/batchmesher_callbacks.tcl"
  batchmesh_scripts = f"{hm_home}/hm/scripts/batchmesh"

  # 1. 加载 hmbm 包
  load_tcl = (
    f'evaltclstring "lappend auto_path {batchmesh_scripts}" 0; '
    f'evaltclstring "package require hmbm" 0'
  )
  exec_tcl(load_tcl)

  # 2. 设置全局参数
  set_args = (
    f'::hmbm::SetGlobalArgs '
    f'{{{input_file}}} {{{os.path.basename(input_file)}}} '
    f'hm '
    f'{{{criteria_file}}} {{{criteria_name}}} '
    f'{{{param_file}}} {{{param_name}}} '
    f'{{{tmp_dir}}} {{{result_txt}}} {{{output_name}}} {{{output_name}}} '
  )
  exec_tcl(f'evaltclstring "{set_args}" 0')

  # 3. 注册回调
  register_pre_geom_callbacks = (
    f'::hmbm::RegisterUserProc PRE_GEOMETRY_LOAD '
    f'{{{callbacks_path}}} ::modulebatchmesher::PreGeomTCL {{}}'
  )
  register_pre_mesh_callbacks = (
    f'::hmbm::RegisterUserProc PRE_BATCHMESH '
    f'{{{callbacks_path}}} ::modulebatchmesher::PreMeshTCL {{}}'
  )
  register_post_mesh_callbacks = (
    f'::hmbm::RegisterUserProc POST_BATCHMESH '
    f'{{{callbacks_path}}} ::modulebatchmesher::PostMeshTCL {{}}'
  )
  exec_tcl(f'evaltclstring "{register_pre_geom_callbacks}" 0')
  exec_tcl(f'evaltclstring "{register_pre_mesh_callbacks}" 0')
  exec_tcl(f'evaltclstring "{register_post_mesh_callbacks}" 0')

  # 4. 注册 CAD import 选项（匹配 STEP 导入时的 CreationType=Parts）
  cad_import_opts = (
    "CreationType=Parts DisplayRepresentation=off SplitComponents=Body "
    "CleanupTol=-0.01 TargetUnits=MMKS (mm kg N s) ScaleFactor=1.0 "
    "UpdateSketchingUnits=on DegSurfTol=0.0 SkipCreationOfSolid=off "
    "DoNotMergeEdges=on StitchingAcrossBodies=on ImportCoordinateSystems=on "
    "ImportFreeCurves=on ImportFreePoints=on ImportBlanked=off "
    "BodyIDAsMetadata=off ColorsAsMetadata=off DensityAsMetadata=off "
    "FullNameAsMetadata=off LayerAsMetadata=off LegacyHierarchyAsMetadata=off "
    "OriginalIdAsMetadata=on TagsAsMetadata=on PartName=PartName UID=UID "
    "MaterialName=Material MeshFlag=MeshFlag MID=MaterialId PartNumber=PartNumber "
    "PID=PID Revision=Revision ThicknessName=Thickness "
    "VariantCondition=VariantCondition VariantScope=VariantScope"
  )
  register_cad_opts = (
    f'::hmbm::RegisterCADImportOpt {{{cad_import_opts}}}'
  )
  exec_tcl(f'evaltclstring "{register_cad_opts}" 0')

  # 5. 运行 BatchMesh
  batch_cmd = (
    f'::hmbm::BatchMesh '
    f'{{{input_file}}} hm '
    f'{{{criteria_file}}} {{{param_file}}}'
  )
  exec_tcl(f'evaltclstring "{batch_cmd}" 0')

  # 判断输出文件
  output_file = os.path.join(output_dir, output_name)
  if os.path.isfile(output_file):
    return output_file
  return ""

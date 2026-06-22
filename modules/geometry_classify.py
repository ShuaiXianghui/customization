"""
几何分类模块 — 三维判定：薄壁件 / 微小件 / 厚实体件
针对叉车结构件优化的体量比判定策略 + 体积过滤
"""
import math
from dataclasses import dataclass, field
from typing import Optional

from config.settings import CLASSIFY
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_get_component_list,
  api_get_component_name,
  api_get_component_volume,
  api_get_component_area,
  api_get_component_bbox,
  api_get_solid_thickness,
  exec_tcl,
  get_hm,
  get_model,
)


@dataclass
class PartInfo:
  """零件信息"""

  comp_id: int
  name: str
  volume: float = 0.0
  surface_area: float = 0.0
  bbox_dims: tuple = (0, 0, 0)
  category: str = "unknown"   # "thin" / "small" / "thick_solid" / "unknown"
  ratio: float = 0.0
  bbox_ratio: float = 0.0
  moved_to: str = ""          # 记录被移动到哪个组件


@dataclass
class ClassifyResult:
  success: bool
  thin_parts: list = field(default_factory=list)       # 可抽中面的薄壁件
  small_parts: list = field(default_factory=list)      # 微小件（可删除）
  thick_solid_parts: list = field(default_factory=list) # 厚实体件（保留，tetra网格）
  unknown_parts: list = field(default_factory=list)
  message: str = ""


class GeometryClassifier:
  """三维分类器 — 体积/表面积比值 + 包络盒比例 + 体积过滤"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self.threshold = CLASSIFY.get("thin_threshold", 0.08)
    # 微小件判定参数
    self.small_volume_ratio = 0.001     # 单件体积 < 总体积 * 0.1% → 微小件
    self.small_volume_absolute = 10000   # 单件体积 < 10000 mm³ → 微小件（硬阈值）
    self.small_bbox_max = 15.0          # 三个方向最大尺寸都 < 15mm → 微小件
    # 厚实体判定参数
    self.thick_bbox_ratio = 0.15      # 最小/最大方向比 ≥ 0.15 → 厚实体
    self.thick_threshold = 10.0        # 等效厚度 > 10mm → 厚实体
    self._result: Optional[ClassifyResult] = None
    self._total_volume: float = 0.0
    self._results: dict = {}  # comp_id → PartInfo

  def set_params(self, volume_ratio=None, volume_abs=None, bbox_max=None, thick_ratio=None):
    if volume_ratio is not None: self.small_volume_ratio = volume_ratio
    if volume_abs is not None: self.small_volume_absolute = volume_abs
    if bbox_max is not None: self.small_bbox_max = bbox_max
    if thick_ratio is not None: self.thick_bbox_ratio = thick_ratio

  @property
  def result(self) -> Optional[ClassifyResult]:
    return self._result

  def _get_part_info(self, comp_id: int) -> Optional[PartInfo]:
    try:
      name = api_get_component_name(self.session, comp_id) or f"comp_{comp_id}"
      volume = api_get_component_volume(self.session, comp_id)
      area = api_get_component_area(self.session, comp_id) or 1.0
      bbox = api_get_component_bbox(self.session, comp_id)
      dx = bbox[3] - bbox[0] if len(bbox) >= 6 else 0
      dy = bbox[4] - bbox[1] if len(bbox) >= 6 else 0
      dz = bbox[5] - bbox[2] if len(bbox) >= 6 else 0

      return PartInfo(
        comp_id=comp_id, name=name,
        volume=volume, surface_area=area, bbox_dims=(dx, dy, dz),
      )
    except Exception as e:
      logger.warn(f"获取零件 {comp_id} 几何信息失败: {e}")
      return None

  def _classify_part(self, part: PartInfo) -> PartInfo:
    """三维判定：thin / small / thick_solid"""
    volume = part.volume
    area = part.surface_area
    dx, dy, dz = part.bbox_dims
    dims_sorted = sorted([dx, dy, dz], reverse=True)
    bbox_max_dim = dims_sorted[0] if dims_sorted[0] > 0 else 1
    bbox_min_dim = dims_sorted[2]

    if volume <= 0 or area <= 0:
      part.ratio = 0
      part.bbox_ratio = 0
    else:
      part.ratio = volume / (area ** 1.5)
      part.bbox_ratio = bbox_min_dim / bbox_max_dim

    volume_pct = (volume / self._total_volume) if self._total_volume > 0 else 0

    # 判断1: 微小件
    # 条件: 体积 ≤ 10000mm³ 或 包络盒最大尺寸 < 20mm
    # 注意: hm_getmass 对无材料属性的几何体可能返回 0，此时 bbox 回退体积用于判断
    is_small = volume <= self.small_volume_absolute or max(dx, dy, dz) < 20.0

    if is_small:
      part.category = "small"
      logger.info(f"  微小件: {part.name} | V={volume:.0f}mm³ bbox max={max(dx,dy,dz):.0f}mm")
      return part

    # 判断2: 厚实体 vs 薄壁
    # 策略优先级:
    #   1. hm_getgeometricthinsolidinfo → 真实几何厚度
    #   2. hm_getmass 体积/面积 → 2V/A 等效厚度
    #   3. bbox_min_dim（回退）
    geom_thickness = api_get_solid_thickness(self.session, part.comp_id)

    if area > 0 and volume > 0:
      equiv_thk = 2.0 * volume / area
    else:
      equiv_thk = 0

    if geom_thickness > 0:
      actual_thickness = geom_thickness
    elif equiv_thk > 0:
      actual_thickness = equiv_thk
    else:
      actual_thickness = bbox_min_dim

    if actual_thickness <= self.thick_threshold:
      part.category = "thin"
      logger.info(f"  薄壁件: {part.name} | 厚度={actual_thickness:.1f}mm")
    else:
      part.category = "thick_solid"
      logger.info(f"  厚实体: {part.name} | 厚度={actual_thickness:.1f}mm")

    return part

  def run(self, comp_ids: list = None) -> ClassifyResult:
    """执行三维分类"""
    logger.info("===== 三维零件分类 =====")

    if comp_ids is None:
      comp_ids = api_get_component_list(self.session)

    if not comp_ids:
      return ClassifyResult(success=False, message="未找到任何组件")

    # 第一轮: 获取所有零件信息并计算总体积
    all_parts = []
    for cid in comp_ids:
      info = self._get_part_info(cid)
      if info is not None:
        all_parts.append(info)
        self._total_volume += info.volume

    logger.info(f"零件总数: {len(all_parts)}, 总体积: {self._total_volume:.0f} mm³")

    # 第二轮: 分类
    thin_parts, small_parts, thick_parts, unknown_parts = [], [], [], []

    for p in all_parts:
      p = self._classify_part(p)
      self._results[p.comp_id] = p

      if p.category == "thin":
        thin_parts.append(p)
      elif p.category == "small":
        small_parts.append(p)
      elif p.category == "thick_solid":
        thick_parts.append(p)
      else:
        unknown_parts.append(p)

    result = ClassifyResult(
      success=len(thin_parts) + len(thick_parts) > 0,
      thin_parts=thin_parts,
      small_parts=small_parts,
      thick_solid_parts=thick_parts,
      unknown_parts=unknown_parts,
      message=(
        f"分类完成: 薄壁 {len(thin_parts)} /"
        f" 微小 {len(small_parts)} /"
        f" 厚实体 {len(thick_parts)} /"
        f" 未知 {len(unknown_parts)}"
      ),
    )

    self._result = result
    logger.info("")
    logger.info(result.message)
    logger.info("===== 三维零件分类完成 =====")
    return result

  def get_part_info(self, comp_id: int) -> Optional[PartInfo]:
    return self._results.get(comp_id)

  def delete_small_parts(self) -> list:
    """删除所有微小件，返回已删除的 comp_id 列表"""
    if not self._result:
      return []
    deleted = []
    for p in self._result.small_parts:
      try:
        import hm.entities as ent
        model = get_hm().Model() if get_hm() else None
        if model:
          comp = ent.Component(model, p.comp_id)
          model.delete(comp)
          deleted.append(p.comp_id)
          logger.info(f"已删除微小件: {p.name} (comp_id={p.comp_id})")
        else:
          logger.warn(f"无法删除 {p.comp_id}: 无 HM Model")
      except Exception as e:
        logger.error(f"删除 {p.comp_id} 失败: {e}")
    logger.info(f"删除微小件: {len(deleted)} 个")
    return deleted

  def organize_parts(self) -> dict:
    """按分类结果创建 Part 体系：
    创建三个顶层 Part Assembly:
      _薄壁件_shell → 每个薄壁零件创建一个子 Part，存放原始 Solid
      _微小件_small → 每个微小零件创建一个子 Part
      _实体件_solid → 每个厚实体零件创建一个子 Part
    返回: {"thin": top_part_id, "small": top_part_id, "thick": top_part_id}
    """
    if not self._result:
      logger.warn("请先运行 classify()")
      return {}

    from utils.logger import logger

    hm_mod = get_hm()
    model = get_model()
    try:
      import hm.entities as ent
    except ImportError:
      ent = hm_mod.entities

    category_config = {
      "thin":  ("_薄壁件_shell", self._result.thin_parts),
      "small": ("_微小件_small", self._result.small_parts),
      "thick": ("_实体件_solid", self._result.thick_solid_parts),
    }

    created = {}

    for key, (top_name, parts) in category_config.items():
      if not parts:
        continue

      try:
        # Step 1: 创建顶层 Part Assembly
        top_part = ent.Part(model)
        top_part.name = top_name
        created[key] = int(top_part.id)
        model.ME_ModuleOccurrenceConvert(part_entity=top_part, type="assembly", reserved="")

        # Step 2: 为每个零件创建子 Part，把 Solid 移进去
        for p in parts:
          cid = int(p.comp_id)
          child_name = p.name if p.name else f"part_{cid}"

          # 用 ME_ModuleOccurrenceCreate 在顶层 Part 下创建子 Part
          model.ME_ModuleOccurrenceCreate(
            name=child_name, parent_part_entity=top_part, structural_type="part",
          )

        logger.info(f"Part 分组完成: {len(parts)} 个 → '{top_name}' (Part_{top_part.id})")
      except Exception as e:
        logger.error(f"Part 分组失败 ({top_name}): {e}")

    return created

"""
几何分类模块 — 按厚度分组 + 重组 Component
参照 geometry_defeature.py 逻辑：
  遍历所有 Solid → hm_getgeometricthinsolidinfo 获取厚度 →
  ≤10mm → T{thk}_shell, 10-15mm → T{thk}_solid, ≥15mm → T{thk}_solid
同时检测微小件（体积≤10000mm³ or bbox<20mm）→ _small
"""
import math
from dataclasses import dataclass, field
from typing import Optional

from config.settings import CLASSIFY_THREE_TIER
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_get_component_list,
  api_get_component_name,
  api_get_component_volume,
  api_get_component_area,
  api_get_component_bbox,
  api_get_solid_thickness,
  api_group_solids_by_thickness,
  api_move_solids_to_new_component,
  get_hm,
  get_model,
)


@dataclass
class PartInfo:
  """零件信息 — 按厚度分组后的 Component"""

  comp_id: int
  name: str            # T{thk}_shell / T{thk}_solid / _small_N
  thickness: float = 0.0
  category: str = "unknown"   # "thin" / "small" / "mid_thick" / "thick"


@dataclass
class ClassifyResult:
  success: bool
  thin_parts: list = field(default_factory=list)        # T{thk}_shell (≤10mm)
  small_parts: list = field(default_factory=list)       # _small (已合并到一个组件)
  mid_thick_parts: list = field(default_factory=list)   # T{thk}_solid (10-15mm)
  thick_parts: list = field(default_factory=list)       # T{thk}_solid (≥15mm)
  message: str = ""

  # 旧字段别名（向后兼容）
  @property
  def thick_solid_parts(self):
    return self.thick_parts

  @property
  def solid_parts(self):
    return self.mid_thick_parts + self.thick_parts


class GeometryClassifier:
  """按厚度分组的几何分类器 — geometry_defeature.py 风格"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self.thin_threshold = CLASSIFY_THREE_TIER.get("thin_threshold", 10.0)
    self.mid_thick_threshold = CLASSIFY_THREE_TIER.get("mid_thick_threshold", 15.0)
    self.small_volume_absolute = 10000  # mm³
    self._result: Optional[ClassifyResult] = None
    self._original_comps: list = []  # 原始 component id 列表（用于后续删除）

  @property
  def result(self) -> Optional[ClassifyResult]:
    return self._result

  def set_threshold(self, value: float):
    """设置薄壁/实体分界阈值（GUI 用）"""
    self.thin_threshold = value
    self.mid_thick_threshold = max(value + 5.0, 15.0)

  def set_params(self, volume_abs=None):
    """设置微小件参数"""
    if volume_abs is not None:
      self.small_volume_absolute = volume_abs

  def _detect_small_solids(self, all_comps: list) -> list:
    """检测微小件: 体积≤10000mm³ 或包络盒最大尺寸<20mm 的 component"""
    small_comp_ids = []
    total_vol = 0.0
    for cid in all_comps:
      vol = api_get_component_volume(self.session, cid)
      total_vol += vol

    for cid in all_comps:
      vol = api_get_component_volume(self.session, cid)
      bbox = api_get_component_bbox(self.session, cid)
      if len(bbox) >= 6:
        dx = bbox[3] - bbox[0]
        dy = bbox[4] - bbox[1]
        dz = bbox[5] - bbox[2]
        bbox_max = max(dx, dy, dz)
      else:
        bbox_max = 0

      is_small = vol <= self.small_volume_absolute or bbox_max < 20.0
      if is_small and vol > 0:
        name = api_get_component_name(self.session, cid)
        small_comp_ids.append(cid)
        logger.info(f"  微小件: {name} | V={vol:.0f}mm³ bbox_max={bbox_max:.0f}mm")

    return small_comp_ids

  def run(self, comp_ids: list = None) -> ClassifyResult:
    """主流程: 遍历 Solid → 按厚度分组 → 创建 T{thk}_shell / T{thk}_solid Component
    未被分类的 surface/line 等保留到 _others 组件
    """
    logger.info("===== 按厚度分组分类 =====")

    if comp_ids is None:
      comp_ids = api_get_component_list(self.session)

    if not comp_ids:
      return ClassifyResult(success=False, message="未找到任何组件")

    # ---- Step 1: 获取所有 Solid 厚度 ----
    groups = api_group_solids_by_thickness(self.session)
    shell_groups = groups["shell_groups"]    # ≤10mm
    mid_groups = groups["mid_groups"]        # 10-15mm
    thick_groups = groups["thick_groups"]    # ≥15mm
    solid_info = groups["solid_info"]

    if not solid_info:
      logger.info("未检测到有效的 Solid 实体")
      return ClassifyResult(success=False, message="未找到可分类的 Solid")

    # 收集所有已分类的 solid ID
    classified_sids = set()
    for t_key, sids in shell_groups.items():
      classified_sids.update(sids)
    for t_key, sids in mid_groups.items():
      classified_sids.update(sids)
    for t_key, sids in thick_groups.items():
      classified_sids.update(sids)

    # ---- Step 2: 创建 _others 组件存放未分类的 solid ----
    import hm.entities as ent
    hm_mod = get_hm()
    model = get_model()
    all_solids = hm_mod.Collection(model, ent.Solid)
    unclassified_sids = []
    for s in all_solids:
      sid = int(s.id)
      if sid not in classified_sids:
        unclassified_sids.append(sid)

    if unclassified_sids:
      api_move_solids_to_new_component("_others", unclassified_sids)
      logger.info(f"_others: {len(unclassified_sids)} 个未分类 Solid")

    # ---- Step 3: 为每个厚度分组创建新 Component ----
    thin_parts = []
    for t_key, sids in sorted(shell_groups.items(), key=lambda kv: float(kv[0])):
      comp_name = f"T{t_key}_shell"
      cid = api_move_solids_to_new_component(comp_name, sids)
      thin_parts.append(PartInfo(
        comp_id=cid, name=comp_name,
        thickness=float(t_key), category="thin",
      ))

    mid_thick_parts = []
    for t_key, sids in sorted(mid_groups.items(), key=lambda kv: float(kv[0])):
      comp_name = f"T{t_key}_solid"
      cid = api_move_solids_to_new_component(comp_name, sids)
      mid_thick_parts.append(PartInfo(
        comp_id=cid, name=comp_name,
        thickness=float(t_key), category="mid_thick",
      ))

    thick_parts = []
    for t_key, sids in sorted(thick_groups.items(), key=lambda kv: float(kv[0])):
      comp_name = f"T{t_key}_solid"
      cid = api_move_solids_to_new_component(comp_name, sids)
      thick_parts.append(PartInfo(
        comp_id=cid, name=comp_name,
        thickness=float(t_key), category="thick",
      ))

    # ---- Step 4: 跳过删除旧组件（solid 已移走，旧组件可能有残留曲面需用户手动清理）----

    # ---- Step 5: 检测微小件（跳过 _others, _small）----
    skip_names = {"_others", "_small"}
    remaining = [c for c in api_get_component_list(self.session)
                 if api_get_component_name(self.session, c) not in skip_names]
    small_comp_ids = self._detect_small_solids(remaining)

    small_parts = []
    if small_comp_ids:
      # 把微小件 solid 移入 _small 组件
      import hm.entities as ent
      hm_mod = get_hm()
      model = get_model()
      small_sids = []
      for scid in small_comp_ids:
        try:
          for s in hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Solid, ent.Component),
                                     hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Component, ids=[int(scid)]))):
            small_sids.append(int(s.id))
        except Exception:
          pass
      if small_sids:
        small_cid = api_move_solids_to_new_component("_small", small_sids)
        small_parts.append(PartInfo(
          comp_id=small_cid, name="_small", thickness=0, category="small",
        ))

    # ---- Step 6: 构建结果 ----
    result = ClassifyResult(
      success=len(thin_parts) + len(mid_thick_parts) + len(thick_parts) > 0,
      thin_parts=thin_parts,
      small_parts=small_parts,
      mid_thick_parts=mid_thick_parts,
      thick_parts=thick_parts,
      message=(
        f"分组完成: 薄壁 {len(thin_parts)} 组 /"
        f" 微小 {len(small_parts)} /"
        f" 中厚 {len(mid_thick_parts)} 组 /"
        f" 厚实体 {len(thick_parts)} 组"
      ),
    )

    self._result = result
    logger.info(result.message)
    logger.info("===== 按厚度分组分类完成 =====")
    return result

  def delete_small_parts(self) -> list:
    """删除所有微小件，返回已删除的 comp_id 列表"""
    if not self._result or not self._result.small_parts:
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
      except Exception as e:
        logger.error(f"删除 {p.comp_id} 失败: {e}")
    logger.info(f"删除微小件: {len(deleted)} 个")
    return deleted

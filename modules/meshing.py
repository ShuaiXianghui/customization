"""
参数化网格划分模块
- 薄壁件 → 壳网格 (2D, batchmesh2 midmesh)
- 中厚件 → 六面体网格 (3D, elemoffset_thinsolid 3层)
- 厚实体件 → 六面体网格 (3D, elemoffset_thinsolid t/5层)
"""
from dataclasses import dataclass, field
from typing import Optional

from config.settings import (
  DEFAULT_SHELL_SIZE,
  DEFAULT_SOLID_SIZE,
  SHELL_ELEM_TYPE,
  HEX_ELEM_SIZE,
)
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_auto_mesh,
  api_elemoffset_thinsolid,
  api_get_solid_thickness,
)


@dataclass
class MeshRecord:
  comp_id: int
  comp_name: str
  mesh_type: str
  elem_size: float
  elem_count: int = 0
  quality_pass: bool = True


@dataclass
class MeshResult:
  success: bool
  records: list = field(default_factory=list)
  message: str = ""


class MeshingEngine:
  """网格划分引擎"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self.shell_size = DEFAULT_SHELL_SIZE
    self.solid_size = DEFAULT_SOLID_SIZE
    self.hex_size = HEX_ELEM_SIZE
    self.shell_elem_type = SHELL_ELEM_TYPE
    self._result: Optional[MeshResult] = None

  def set_shell_size(self, size: float):
    self.shell_size = size

  def set_solid_size(self, size: float):
    self.solid_size = size

  @property
  def result(self) -> Optional[MeshResult]:
    return self._result

  def _mesh_single(self, comp_id: int, comp_name: str, size: float, elem_type: str) -> MeshRecord:
    try:
      api_auto_mesh(self.session, comp_id, size, elem_type)
      return MeshRecord(
        comp_id=comp_id, comp_name=comp_name,
        mesh_type=elem_type, elem_size=size, quality_pass=True,
      )
    except Exception as e:
      logger.error(f"网格划分失败 comp={comp_id}: {e}")
      return MeshRecord(
        comp_id=comp_id, comp_name=comp_name,
        mesh_type=elem_type, elem_size=size, quality_pass=False,
      )

  def _mesh_hex_single(self, comp_id: int, comp_name: str, layers: int, size: float = 5.0) -> MeshRecord:
    """六面体实体网格 (elemoffset_thinsolid)"""
    try:
      api_elemoffset_thinsolid(None, [comp_id], num_layers=layers, elem_size=size)
      return MeshRecord(
        comp_id=comp_id, comp_name=comp_name,
        mesh_type="hexa", elem_size=size, quality_pass=True,
      )
    except Exception as e:
      logger.error(f"六面体网格失败 comp={comp_id}: {e}")
      return MeshRecord(
        comp_id=comp_id, comp_name=comp_name,
        mesh_type="hexa", elem_size=size, quality_pass=False,
      )

  def run(self, thin_parts: list, solid_parts: list,
          mid_thick_parts: list = None, thick_parts: list = None) -> MeshResult:
    """批量网格划分
    thin_parts: 薄壁件 → shell mesh
    solid_parts: 实体件列表（兼容旧调用 = mid_thick + thick 合并，用 tet 回退）
    mid_thick_parts: 中厚件 10-15mm → hex 3层
    thick_parts: 厚实体 ≥15mm → hex t/5层
    """
    self._result = None
    mid_thick = mid_thick_parts or []
    thick = thick_parts or []
    records = []

    # 薄壁件 → 壳网格
    for part in thin_parts:
      cid = part.comp_id if hasattr(part, "comp_id") else part
      name = part.name if hasattr(part, "name") else f"comp_{cid}"
      r = self._mesh_single(cid, name, self.shell_size, self.shell_elem_type)
      records.append(r)
      logger.info(f"壳网格: {name}, size={self.shell_size}mm, ok={r.quality_pass}")

    # 中厚件 → 六面体 3 层
    for part in mid_thick:
      cid = part.comp_id if hasattr(part, "comp_id") else part
      name = part.name if hasattr(part, "name") else f"comp_{cid}"
      r = self._mesh_hex_single(cid, name, layers=3, size=self.hex_size)
      records.append(r)
      logger.info(f"六面体(中厚): {name}, 3层, size={self.hex_size}mm, ok={r.quality_pass}")

    # 厚实体 → 六面体 t/5 层
    for part in thick:
      cid = part.comp_id if hasattr(part, "comp_id") else part
      name = part.name if hasattr(part, "name") else f"comp_{cid}"
      # 计算层数
      thick_val = None
      if hasattr(part, "volume") and hasattr(part, "surface_area"):
        thick_val = api_get_solid_thickness(None, cid)
        if thick_val <= 0 and part.surface_area > 0 and part.volume > 0:
          thick_val = 2.0 * part.volume / part.surface_area
      if not thick_val or thick_val <= 0:
        thick_val = 20.0
      layers = max(2, int(thick_val / 5.0 + 0.5))
      r = self._mesh_hex_single(cid, name, layers=layers, size=self.hex_size)
      records.append(r)
      logger.info(f"六面体(厚): {name}, {layers}层, size={self.hex_size}mm, ok={r.quality_pass}")

    fail_count = sum(1 for r in records if not r.quality_pass)
    result = MeshResult(
      success=fail_count == 0, records=records,
      message=f"网格划分完成: {len(records)} 个, 失败 {fail_count} 个",
    )
    self._result = result
    logger.info(result.message)
    return result

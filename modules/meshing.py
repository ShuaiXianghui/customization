"""
参数化网格划分模块
- 薄壁件 → 壳网格 (2D)
- 实体件 → 体网格 (3D)
"""
from dataclasses import dataclass, field
from typing import Optional

from config.settings import (
  DEFAULT_SHELL_SIZE,
  DEFAULT_SOLID_SIZE,
  SHELL_ELEM_TYPE,
  SOLID_ELEM_TYPE,
)
from utils.logger import logger
from utils.hw_api import get_session, api_auto_mesh


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
    self.shell_elem_type = SHELL_ELEM_TYPE
    self.solid_elem_type = SOLID_ELEM_TYPE
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

  def run(self, thin_parts: list, solid_parts: list) -> MeshResult:
    logger.info(f"开始网格划分: 壳={self.shell_size}mm, 体={self.solid_size}mm")
    records = []

    for part in thin_parts:
      cid = part.comp_id if hasattr(part, "comp_id") else part
      name = part.name if hasattr(part, "name") else f"comp_{cid}"
      r = self._mesh_single(cid, name, self.shell_size, self.shell_elem_type)
      records.append(r)
      logger.info(f"壳网格: {name}, size={self.shell_size}mm, ok={r.quality_pass}")

    for part in solid_parts:
      cid = part.comp_id if hasattr(part, "comp_id") else part
      name = part.name if hasattr(part, "name") else f"comp_{cid}"
      r = self._mesh_single(cid, name, self.solid_size, self.solid_elem_type)
      records.append(r)
      logger.info(f"体网格: {name}, size={self.solid_size}mm, ok={r.quality_pass}")

    fail_count = sum(1 for r in records if not r.quality_pass)
    result = MeshResult(
      success=fail_count == 0, records=records,
      message=f"网格划分完成: {len(records)} 个, 失败 {fail_count} 个",
    )
    self._result = result
    logger.info(result.message)
    return result

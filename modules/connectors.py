"""
连接器自动化模块
针对叉车部件: 缝焊 / 焊点 / 螺栓
识别策略 + 预览确认 + 批量创建
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config.settings import CONNECTOR
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_get_component_list,
  api_get_component_name,
  api_get_edges_nearby,
  api_get_holes_matching,
  api_create_seam_weld,
  api_create_bolt,
  api_create_spot_weld,
)


class ConnectorType(Enum):
  SEAM_WELD = "seam_weld"
  SPOT_WELD = "spot_weld"
  BOLT = "bolt"
  ADHESIVE = "adhesive"


@dataclass
class ConnectorCandidate:
  id: int
  conn_type: ConnectorType
  source_comp: str
  target_comp: str
  position: tuple = (0, 0, 0)
  params: dict = field(default_factory=dict)
  selected: bool = True


@dataclass
class ConnectorResult:
  success: bool
  candidates: list = field(default_factory=list)
  created: list = field(default_factory=list)
  message: str = ""


class ConnectorEngine:

  def __init__(self, session=None):
    self.session = session or get_session()
    self._candidates: list = []
    self._result: Optional[ConnectorResult] = None

    self.seam_gap_tol = CONNECTOR["seam_gap_tolerance"]
    self.seam_angle_tol = CONNECTOR["seam_angle_tolerance"]
    self.bolt_hole_range = tuple(CONNECTOR["bolt_hole_diameter_range"])
    self.bolt_coaxial_tol = CONNECTOR["bolt_coaxial_tolerance"]
    self.bolt_diameter_tol = CONNECTOR["bolt_diameter_match_tolerance"]
    self.spot_edge_offset = CONNECTOR["spot_edge_offset"]
    self.spot_spacing = CONNECTOR["spot_spacing"]

  @property
  def candidates(self) -> list:
    return self._candidates.copy()

  @property
  def result(self) -> Optional[ConnectorResult]:
    return self._result

  def detect_all(self) -> list:
    """全自动识别所有连接候选"""
    logger.info("开始自动识别连接器候选...")
    self._candidates = []
    comps = api_get_component_list(self.session)

    if len(comps) < 2:
      logger.warn("组件数不足，无法创建连接")
      return []

    candidate_id = 0

    for i, c1 in enumerate(comps):
      for c2 in comps[i + 1:]:
        name1 = api_get_component_name(self.session, c1) or f"comp_{c1}"
        name2 = api_get_component_name(self.session, c2) or f"comp_{c2}"

        edges = api_get_edges_nearby(self.session, c1, c2, self.seam_gap_tol)
        if edges:
          self._candidates.append(ConnectorCandidate(
            id=candidate_id, conn_type=ConnectorType.SEAM_WELD,
            source_comp=name1, target_comp=name2,
            params={"edges": edges},
          ))
          candidate_id += 1

        holes = api_get_holes_matching(
          self.session, c1, c2,
          self.bolt_hole_range[0], self.bolt_hole_range[1],
          self.bolt_diameter_tol, self.bolt_coaxial_tol,
        )
        if holes:
          self._candidates.append(ConnectorCandidate(
            id=candidate_id, conn_type=ConnectorType.BOLT,
            source_comp=name1, target_comp=name2,
            params={"holes": holes},
          ))
          candidate_id += 1

    summary = {ConnectorType.SEAM_WELD: 0, ConnectorType.SPOT_WELD: 0, ConnectorType.BOLT: 0}
    for c in self._candidates:
      if c.conn_type in summary:
        summary[c.conn_type] += 1

    logger.info(
      f"识别完成: 缝焊 {summary[ConnectorType.SEAM_WELD]} 处, "
      f"焊点 {summary[ConnectorType.SPOT_WELD]} 处, "
      f"螺栓 {summary[ConnectorType.BOLT]} 处"
    )
    return self._candidates

  def set_selection(self, candidate_ids: list, selected: bool):
    id_set = set(candidate_ids)
    for c in self._candidates:
      if c.id in id_set:
        c.selected = selected

  def set_all_selected(self, selected: bool = True):
    for c in self._candidates:
      c.selected = selected

  def create_selected(self) -> ConnectorResult:
    selected = [c for c in self._candidates if c.selected]
    logger.info(f"准备创建 {len(selected)} 个连接器...")

    created = []
    for c in selected:
      try:
        if c.conn_type == ConnectorType.SEAM_WELD:
          api_create_seam_weld(self.session, c.params.get("edges", []), self.seam_gap_tol)
          created.append(c)
          logger.info(f"创建缝焊: {c.source_comp} ↔ {c.target_comp}")
        elif c.conn_type == ConnectorType.BOLT:
          api_create_bolt(self.session, c.params.get("holes", []), c.params.get("diameter", 10.0))
          created.append(c)
          logger.info(f"创建螺栓: {c.source_comp} ↔ {c.target_comp}")
        elif c.conn_type == ConnectorType.SPOT_WELD:
          api_create_spot_weld(self.session, c.params.get("nodes", []), self.spot_spacing)
          created.append(c)
          logger.info(f"创建焊点: {c.source_comp} ↔ {c.target_comp}")
      except Exception as e:
        logger.error(f"创建失败 id={c.id}: {e}")

    result = ConnectorResult(
      success=len(created) > 0, candidates=self._candidates, created=created,
      message=f"创建完成: 成功 {len(created)} 个, 跳过 {len(selected) - len(created)} 个",
    )
    self._result = result
    logger.info(result.message)
    return result

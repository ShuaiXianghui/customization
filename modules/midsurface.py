"""
中面抽取模块 — 对薄壁件批量抽取中面并提取厚度
"""
from dataclasses import dataclass, field
from typing import Optional

from config.settings import MIDSURFACE
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_extract_midsurface,
  api_get_component_thickness,
)


@dataclass
class MidsurfaceResult:
  success: bool
  extracted_parts: list = field(default_factory=list)
  failed_parts: list = field(default_factory=list)
  thickness_map: dict = field(default_factory=dict)
  message: str = ""


class MidsurfaceExtractor:
  """中面抽取器"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self.target_thickness_min = MIDSURFACE["target_thickness_min"]
    self.target_thickness_max = MIDSURFACE["target_thickness_max"]
    self.cleanup_tolerance = MIDSURFACE["cleanup_tolerance"]
    self._result: Optional[MidsurfaceResult] = None
    self._thickness_map: dict = {}

  @property
  def result(self) -> Optional[MidsurfaceResult]:
    return self._result

  def _extract_single(self, comp_id: int) -> bool:
    """抽取单个组件的中面并获取厚度"""
    try:
      api_extract_midsurface(self.session, [comp_id])
      thickness = api_get_component_thickness(self.session, comp_id) or 6.0
      self._thickness_map[comp_id] = thickness
      logger.info(f"中面抽取成功: comp={comp_id}, thickness={thickness:.1f}mm")
      return True
    except Exception as e:
      logger.error(f"中面抽取失败 comp={comp_id}: {e}")
      return False

  def run(self, thin_comp_ids: list) -> MidsurfaceResult:
    """批量抽取中面"""
    logger.info(f"开始中面抽取，共 {len(thin_comp_ids)} 个薄壁件...")

    self._thickness_map = {}
    extracted = []
    failed = []

    for cid in thin_comp_ids:
      if self._extract_single(cid):
        extracted.append(cid)
      else:
        failed.append(cid)

    result = MidsurfaceResult(
      success=len(extracted) > 0,
      extracted_parts=extracted,
      failed_parts=failed,
      thickness_map=self._thickness_map,
      message=f"中面抽取完成: 成功 {len(extracted)} 个, 失败 {len(failed)} 个",
    )

    self._result = result
    logger.info(result.message)
    return result

"""
几何清理模块 — 修复 CAD 几何错误、去除小特征、缝合自由边
对应 HM GUI 的 Surface Repair 工作流
"""
from dataclasses import dataclass, field
from typing import Optional

from config.settings import MIDSURFACE
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_geometry_cleanup,
  api_surface_merge,
  api_fill_holes,
  api_remove_small_fillets,
  api_equivalence,
  api_create_solid_from_surfaces,
  api_stitch_free_edges,
  api_get_component_list,
)


@dataclass
class CleanupResult:
  success: bool
  steps_executed: list = field(default_factory=list)
  steps_failed: list = field(default_factory=list)
  message: str = ""


class GeometryCleanup:
  """几何清理器 — 多步骤修复 CAD 几何问题"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self.cleanup_tolerance = MIDSURFACE.get("cleanup_tolerance", 0.5)
    self.hole_max_size = 5.0       # 最大填孔尺寸 (mm)
    self.fillet_max_radius = 3.0   # 最大去圆角半径 (mm)
    self.stitch_tolerance = 0.5    # 缝合容差 (mm)
    self.equivalence_tolerance = 0.1  # 等效节点/边容差 (mm)
    self._result: Optional[CleanupResult] = None

  def set_params(self, cleanup_tol=None, hole_size=None, fillet_radius=None,
                 stitch_tol=None, equiv_tol=None):
    """设置清理参数"""
    if cleanup_tol is not None:
      self.cleanup_tolerance = cleanup_tol
    if hole_size is not None:
      self.hole_max_size = hole_size
    if fillet_radius is not None:
      self.fillet_max_radius = fillet_radius
    if stitch_tol is not None:
      self.stitch_tolerance = stitch_tol
    if equiv_tol is not None:
      self.equivalence_tolerance = equiv_tol

  @property
  def result(self) -> Optional[CleanupResult]:
    return self._result

  def run(self, comp_ids: list = None) -> CleanupResult:
    """执行完整几何清理流程"""
    logger.info("===== 开始几何清理 =====")

    if comp_ids is None:
      comp_ids = api_get_component_list()

    steps_executed = []
    steps_failed = []

    # Step 1: 自动拓扑清理 (修复自由边、缝隙、重复面)
    try:
      logger.info("[1/5] 自动拓扑清理...")
      api_stitch_free_edges(self.session, self.stitch_tolerance)
      steps_executed.append("stitch_free_edges")
    except Exception as e:
      logger.error(f"缝合自由边失败: {e}")
      steps_failed.append("stitch_free_edges")

    # Step 2: 等效处理 (合并重合节点/边)
    try:
      logger.info("[2/5] 等效节点/边...")
      api_equivalence(self.session, self.equivalence_tolerance)
      steps_executed.append("equivalence")
    except Exception as e:
      logger.error(f"等效处理失败: {e}")
      steps_failed.append("equivalence")

    # Step 3: 合并相邻曲面 (去冗余边)
    try:
      logger.info("[3/5] 合并相邻曲面...")
      api_surface_merge(self.session, break_angle=30.0, min_radius=0.0, max_radius=100.0)
      steps_executed.append("surface_merge")
    except Exception as e:
      logger.error(f"曲面合并失败: {e}")
      steps_failed.append("surface_merge")

    # Step 4: 填孔 (去除小孔/缝隙)
    try:
      logger.info(f"[4/5] 填充小孔 (max={self.hole_max_size}mm)...")
      api_fill_holes(self.session, self.hole_max_size)
      steps_executed.append("fill_holes")
    except Exception as e:
      logger.error(f"填孔失败: {e}")
      steps_failed.append("fill_holes")

    # Step 5: 去小圆角
    try:
      logger.info(f"[5/5] 去除小圆角 (max={self.fillet_max_radius}mm)...")
      api_remove_small_fillets(self.session, self.fillet_max_radius)
      steps_executed.append("remove_fillets")
    except Exception as e:
      logger.error(f"去圆角失败: {e}")
      steps_failed.append("remove_fillets")

    result = CleanupResult(
      success=len(steps_executed) > 0,
      steps_executed=steps_executed,
      steps_failed=steps_failed,
      message=f"几何清理完成: 成功 {len(steps_executed)} 步, 失败 {len(steps_failed)} 步",
    )

    self._result = result
    logger.info(result.message)
    return result

  def run_quick(self, comp_ids: list = None) -> CleanupResult:
    """快速清理 — 仅缝合自由边 + 等效处理"""
    logger.info("===== 快速几何清理 =====")

    if comp_ids is None:
      comp_ids = api_get_component_list()

    steps_executed = []
    steps_failed = []

    try:
      logger.info("[1/2] 缝合自由边...")
      api_stitch_free_edges(self.session, self.stitch_tolerance)
      steps_executed.append("stitch_free_edges")
    except Exception as e:
      logger.error(f"缝合自由边失败: {e}")
      steps_failed.append("stitch_free_edges")

    try:
      logger.info("[2/2] 等效节点/边...")
      api_equivalence(self.session, self.equivalence_tolerance)
      steps_executed.append("equivalence")
    except Exception as e:
      logger.error(f"等效处理失败: {e}")
      steps_failed.append("equivalence")

    result = CleanupResult(
      success=len(steps_executed) > 0,
      steps_executed=steps_executed,
      steps_failed=steps_failed,
      message=f"快速清理完成: 成功 {len(steps_executed)} 步, 失败 {len(steps_failed)} 步",
    )
    self._result = result
    logger.info(result.message)
    return result

"""
BatchMesher 模块 — 基于 Part/Representation 体系
通过 Part → CAD Representation → hmbm::BatchMesh → Crash 5mm Representation 完成网格划分
"""
import os
from dataclasses import dataclass, field
from typing import Optional

from config.settings import DEFAULT_SHELL_SIZE
from utils.logger import logger
from utils.hw_api import get_session
from modules.part_rep_manager import PartRepManager, PartRepInfo


@dataclass
class BatchMeshResult:
  success: bool
  parts: list = field(default_factory=list)
  message: str = ""


class BatchMeshEngine:
  """BatchMesher 引擎 — Part/Representation 体系"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self.elem_size = DEFAULT_SHELL_SIZE            # 默认 5.0 mm
    self.criteria_file = None                      # None=用默认 crash_5mm.criteria
    self.param_file = None                         # None=用默认 crash_5mm.param
    self.skip_save = False                         # 跳过保存（已有 .hm 文件时）
    self._result: Optional[BatchMeshResult] = None
    self._manager: Optional[PartRepManager] = None

  def set_params(
    self, elem_size=None,
    criteria_file=None, param_file=None,
    skip_save=None,
  ):
    if elem_size is not None:
      self.elem_size = elem_size
    if criteria_file is not None:
      self.criteria_file = criteria_file
    if param_file is not None:
      self.param_file = param_file
    if skip_save is not None:
      self.skip_save = skip_save

  @property
  def result(self) -> Optional[BatchMeshResult]:
    return self._result

  def run(self, part_ids: list = None) -> BatchMeshResult:
    """完整流程:
    1. Part → 导出 CAD Representation (.hm)
    2. hmbm::BatchMesh 处理每个 .hm 文件
    3. 结果挂回 Part → Crash 5mm Representation
    """
    logger.info("===== BatchMesher (Part/Rep 模式) =====")
    logger.info(f"  单元尺寸={self.elem_size}mm")
    if self.skip_save:
      logger.info(f"  模式: 跳过保存（使用已有 .hm 文件）")

    self._result = None

    try:
      self._manager = PartRepManager(self.session)
      result = self._manager.run(
        part_ids=part_ids,
        criteria_file=self.criteria_file,
        param_file=self.param_file,
        skip_save=self.skip_save,
      )

      # 构建返回结果
      success_parts = [p for p in result.parts if p.status == "done"]
      self._result = BatchMeshResult(
        success=result.success,
        parts=result.parts,
        message=result.message,
      )

      logger.info(self._result.message)
      logger.info(f"  查看: Assembly → Part Browser → 选择 Part → 右键 Switch Rep → Crash 5mm")

    except Exception as e:
      logger.error(f"BatchMesher 失败: {e}")
      self._result = BatchMeshResult(
        success=False,
        message=f"BatchMesher 失败: {e}",
      )

    return self._result

"""
几何导入模块 — Parasolid 批量导入
"""
import os
from dataclasses import dataclass, field
from typing import Optional

from config.settings import USER_PREFS_PATH
from utils.logger import logger
from utils.validators import batch_validate_files, is_parasolid
from utils.hw_api import get_session, api_import_parasolid


@dataclass
class ImportResult:
  success: bool
  imported_files: list = field(default_factory=list)
  failed_files: list = field(default_factory=list)
  component_ids: list = field(default_factory=list)
  message: str = ""


class GeometryImporter:
  """Parasolid 几何导入器"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self._files: list = []
    self._scale: float = 1.0
    self._result: Optional[ImportResult] = None

  def set_files(self, filepaths: list):
    self._files = filepaths

  def add_file(self, filepath: str):
    if filepath not in self._files:
      self._files.append(filepath)

  def remove_file(self, filepath: str):
    if filepath in self._files:
      self._files.remove(filepath)

  def set_scale(self, scale: float):
    self._scale = scale

  @property
  def files(self) -> list:
    return self._files.copy()

  @property
  def result(self) -> Optional[ImportResult]:
    return self._result

  def run(self) -> ImportResult:
    if not self._files:
      return ImportResult(success=False, message="未选择任何文件")

    valid_files, invalid_files = batch_validate_files(self._files)
    failed = [(f, r) for f, r in invalid_files]

    if not valid_files:
      return ImportResult(
        success=False,
        failed_files=failed,
        message="所有文件校验失败，无法导入",
      )

    logger.info(f"准备导入 {len(valid_files)} 个 Parasolid 文件")
    imported = []
    comp_ids = []

    for fp in valid_files:
      try:
        logger.info(f"导入: {os.path.basename(fp)}")
        api_import_parasolid(self.session, fp, self._scale)
        imported.append(fp)
        comp_ids.append(fp)
      except Exception as e:
        logger.error(f"导入失败 {fp}: {e}")
        failed.append((fp, str(e)))

    result = ImportResult(
      success=len(imported) > 0,
      imported_files=imported,
      failed_files=failed,
      component_ids=comp_ids,
      message=f"成功导入 {len(imported)} 个文件, 失败 {len(failed)} 个",
    )

    self._result = result
    logger.info(result.message)
    return result


def batch_import_from_folder(folder: str, scale: float = 1.0) -> ImportResult:
  """从文件夹批量导入 Parasolid 文件"""
  files = []
  for f in os.listdir(folder):
    fp = os.path.join(folder, f)
    if os.path.isfile(fp) and is_parasolid(fp):
      files.append(fp)

  importer = GeometryImporter()
  importer.set_files(files)
  importer.set_scale(scale)
  return importer.run()

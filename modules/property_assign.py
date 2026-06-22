"""
属性识别与材料赋参模块
- 厚度自动识别并取整到标准板厚
- 材料匹配与属性卡片生成
"""
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from config.settings import STANDARD_THICKNESS, DEFAULT_MATERIAL
from utils.logger import logger
from utils.hw_api import (
  get_session,
  api_assign_material,
  api_get_component_name,
  api_get_component_thickness,
  api_get_solid_thickness,
)


@dataclass
class PropertyRecord:
  comp_id: int
  comp_name: str
  measured_thickness: float
  standard_thickness: float
  material: str
  mesh_type: str  # shell / solid


@dataclass
class PropertyResult:
  success: bool
  records: list = field(default_factory=list)
  message: str = ""


class PropertyAssigner:
  """属性赋参器：厚度取整 + 材料匹配 + 卡片生成"""

  def __init__(self, session=None):
    self.session = session or get_session()
    self._material_db: dict = {}
    self._default_material = DEFAULT_MATERIAL
    self._records: list = []
    self._result: Optional[PropertyResult] = None
    self._load_material_db()

  def _load_material_db(self):
    db_path = os.path.join(
      os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
      "config",
      "material_db.json",
    )
    try:
      with open(db_path, "r", encoding="utf-8") as f:
        self._material_db = json.load(f)
      logger.info(f"加载材料库: {len(self._material_db)} 种材料")
    except Exception as e:
      logger.warn(f"加载材料库失败: {e}, 使用默认材料")
      self._material_db = {
        self._default_material: {
          "E": 210000, "nu": 0.3, "rho": 7.85e-9, "yield": 235,
        }
      }

  def set_default_material(self, mat_name: str):
    if mat_name in self._material_db:
      self._default_material = mat_name

  def get_material_list(self) -> list:
    return list(self._material_db.keys())

  def get_material_props(self, mat_name: str) -> Optional[dict]:
    return self._material_db.get(mat_name)

  @property
  def result(self) -> Optional[PropertyResult]:
    return self._result

  def round_to_standard_thickness(self, measured: float) -> float:
    """测量值取整到最接近的标准板厚"""
    if measured <= 0:
      return STANDARD_THICKNESS[0]
    return min(STANDARD_THICKNESS, key=lambda x: abs(x - measured))

  def _match_material_by_name(self, comp_name: str) -> str:
    """根据零件名匹配材料"""
    name_upper = comp_name.upper()
    for mat_name in self._material_db:
      if mat_name.upper() in name_upper:
        logger.debug(f"材料匹配: {comp_name} → {mat_name}")
        return mat_name
    return self._default_material

  def assign_single(
    self,
    comp_id: int,
    comp_name: str = "",
    mesh_type: str = "shell",
    material: str = None,
    thickness: float = None,
  ):
    """给单个组件赋属性"""
    if not comp_name:
      comp_name = api_get_component_name(self.session, comp_id) or f"comp_{comp_id}"

    if thickness is None:
      # 用 hm_getgeometricthinsolidinfo 获取几何厚度
      from utils.hw_api import api_get_solid_thickness as _thk
      thick = _thk(self.session, comp_id)
      if thick > 0:
        thickness = thick
      else:
        thickness = 6.0

    measured = thickness
    standard_thk = self.round_to_standard_thickness(measured)

    if material is None:
      material = self._match_material_by_name(comp_name)

    card_type = "PSHELL" if mesh_type == "shell" else "PSOLID"

    record = PropertyRecord(
      comp_id=comp_id,
      comp_name=comp_name,
      measured_thickness=measured,
      standard_thickness=standard_thk,
      material=material,
      mesh_type=mesh_type,
    )

    try:
      mat_props = self._material_db.get(
        material, self._material_db[self._default_material]
      )
      api_assign_material(
        self.session, comp_id, mat_props, standard_thk, card_type,
      )
      logger.info(
        f"赋属性: {comp_name} | 厚度 {measured:.1f}→{standard_thk:.0f}mm "
        f"| 材料 {material} | {card_type}"
      )
      self._records.append(record)
      return record
    except Exception as e:
      logger.error(f"赋属性失败 {comp_name}: {e}")
      return None

  def run(
    self, thin_parts: list, solid_parts: list, thickness_map: dict = None,
  ) -> PropertyResult:
    """批量赋属性
    thin_parts: 可传入 PartInfo 对象列表，或直接传 comp_id 列表（BatchMesher 模式）
    solid_parts: 同上
    """
    logger.info("开始属性识别与材料赋参...")

    self._records = []
    thickness_map = thickness_map or {}

    for part in thin_parts:
      # 兼容两种模式: PartInfo 对象 或 纯 int
      if isinstance(part, int):
        cid, name = part, f"comp_{part}"
        thk = thickness_map.get(cid)
      else:
        cid = part.comp_id if hasattr(part, "comp_id") else part
        name = part.name if hasattr(part, "name") else ""
        thk = thickness_map.get(cid)
      self.assign_single(cid, name, "shell", thickness=thk)

    for part in solid_parts:
      if isinstance(part, int):
        cid, name = part, f"comp_{part}"
      else:
        cid = part.comp_id if hasattr(part, "comp_id") else part
        name = part.name if hasattr(part, "name") else ""
      self.assign_single(cid, name, "solid")

    result = PropertyResult(
      success=len(self._records) > 0,
      records=self._records,
      message=f"属性赋参完成: {len(self._records)} 个组件",
    )

    self._result = result
    logger.info(result.message)
    return result

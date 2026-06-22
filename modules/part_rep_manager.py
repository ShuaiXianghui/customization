"""
Part/Representation 管理器（简化版）
- 跳过 Module/Occ/Proto 系统
- 直接为每个 Part 导出底层 Component 几何为 .hm 文件
- 调用 hmbm::BatchMesh 处理每个 .hm 文件
"""
import os
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import logger
from utils.hw_api import (
  get_session, get_hm, get_model,
  api_get_part_list, api_get_part_name, api_get_component_list,
  exec_tcl, exec_tcl_ret,
  api_batchmesh_file,
)


@dataclass
class PartRepInfo:
  part_id: int
  part_name: str = ""
  cad_file: str = ""
  mesh_file: str = ""
  status: str = "pending"


@dataclass
class PartRepResult:
  success: bool
  parts: list = field(default_factory=list)
  message: str = ""


class PartRepManager:

  def __init__(self, session=None, rep_dir: str = None):
    self.session = session or get_session()
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    self.rep_dir = rep_dir or os.path.join(_root, "representations")
    os.makedirs(self.rep_dir, exist_ok=True)
    self._parts: dict[int, PartRepInfo] = {}

  # ===== 已确认可行的 Tcl 命令 =====
  # *createmark comps 1 <ids>   — 标记组件
  # *filewriteentities comps 1 <path> 32 -1  — 导出 .hm
  # *createmark modules 1 "name" — 标记 Part（modules 实体）
  # 不可用: *detach_geom, *getvalue, *getentityid

  def _get_comps_for_part(self, part_id: int) -> list:
    """获取 Part 下的所有 Component ID"""
    hm_mod = get_hm()
    model = get_model()
    comp_ids = []
    try:
      import hm.entities as ent
    except ImportError:
      ent = hm_mod.entities
    try:
      part_ent = ent.Part(model, int(part_id))
      part_col = hm_mod.Collection(model, hm_mod.FilterByEnumeration(ent.Part, [int(part_id)]))
      comp_col = hm_mod.Collection(model, hm_mod.FilterByCollection(ent.Component, ent.Part), part_col)
      for c in comp_col:
        comp_ids.append(int(c.id))
    except Exception:
      pass
    return comp_ids

  def save_all_reps(self, part_ids: list = None, overwrite: bool = False) -> dict:
    """为所有薄壁件导出 .hm 文件
    策略: 逐个 Component 导出为独立的 .hm 文件
    （每个 Part 通常只含一个 Component）
    """
    if part_ids is None:
      part_ids = api_get_part_list(self.session)

    if not part_ids:
      logger.warn("没有发现 Part")
      return {}

    # 获取所有 Component
    all_comp_ids = api_get_component_list(self.session) or []

    logger.info(f"===== 导出 CAD 几何 ({len(part_ids)} 个 Part, {len(all_comp_ids)} 个 Component) =====")

    rep_map = {}
    exported = set()

    for pid in part_ids:
      info = PartRepInfo(part_id=pid)
      self._parts[pid] = info

      try:
        name = api_get_part_name(self.session, pid)
        info.part_name = name
        safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")

        # 获取此 Part 下的 Component
        comp_ids = self._get_comps_for_part(pid)

        if comp_ids:
          # 有直接关联的 Component — 只导第一个（大多数 Part 只有一个 Comp）
          cid = comp_ids[0]
        else:
          # 回退: 通过名称匹配（有些 Part 的 name 包含 Component 名）
          name_clean = name.strip().split("<")[0].split(">")[0] if name else ""
          cid = None
          for comp_id in all_comp_ids:
            if comp_id in exported:
              continue
            cname = api_get_part_name(self.session, comp_id)  # 复用: 实际是 component_name
            if name_clean and name_clean in (cname or ""):
              pass
          # 更简单: 首个未导出的 Component
          for comp_id in all_comp_ids:
            if comp_id not in exported:
              cid = comp_id
              break

        if cid is None and not overwrite:
          # 跳过没有 Component 的 Part（可能是装配体、拷贝、空 Part）
          continue

        cad_file = os.path.join(self.rep_dir, f"{safe_name}_CAD_-_-_1.hm")
        info.cad_file = cad_file

        if not overwrite and os.path.isfile(cad_file) and os.path.getsize(cad_file) > 100:
          logger.info(f"  已存在: {name} → {os.path.basename(cad_file)}")
          rep_map[pid] = cad_file
          info.status = "done"
          if cid:
            exported.add(cid)
          continue

        info.status = "saving"
        fp = cad_file.replace("\\", "/")

        # 直接导出此 Component
        if cid:
          tcl = f'*createmark comps 1 {cid}; *filewriteentities comps 1 "{fp}" 32 -1'
          exec_tcl(tcl)
          exported.add(cid)
          if os.path.isfile(fp):
            rep_map[pid] = cad_file
            info.status = "done"
            logger.info(f"  已导出: {name} (comp={cid}) → {os.path.basename(cad_file)}")
          else:
            logger.warn(f"  导出失败: {name} (comp={cid})")
        else:
          logger.warn(f"  无 Component: {name}")

      except Exception as e:
        logger.error(f"处理 Part {pid} 失败: {e}")
        info.status = "failed"

    logger.info(f"===== 导出完成: {len(rep_map)}/{len(part_ids)} =====")
    return rep_map

  def batchmesh_all(
    self, rep_map: dict = None,
    criteria_file: str = None, param_file: str = None,
  ) -> dict:
    if rep_map is None:
      rep_map = {pid: info.cad_file for pid, info in self._parts.items()
                 if info.cad_file and os.path.isfile(info.cad_file)}

    if not rep_map:
      logger.warn("无 CAD 文件可处理")
      return {}

    logger.info(f"===== BatchMesher ({len(rep_map)} 个文件) =====")

    mesh_map = {}
    for pid, cad_file in rep_map.items():
      info = self._parts.get(pid)
      if info:
        info.status = "meshing"

      base = os.path.splitext(os.path.basename(cad_file))[0]
      output_name = base.replace("_CAD_", "_Crash 5mm_") + ".hm"

      try:
        result = api_batchmesh_file(
          input_file=cad_file,
          output_name=output_name,
          criteria_file=criteria_file,
          param_file=param_file,
          output_dir=self.rep_dir,
        )
        if result and os.path.isfile(result):
          mesh_map[pid] = result
          if info:
            info.mesh_file = result
            info.status = "done"
          logger.info(f"  完成: {os.path.basename(cad_file)} → {os.path.basename(result)}")
        else:
          if info:
            info.status = "failed"
          logger.warn(f"  失败: {os.path.basename(cad_file)}")
      except Exception as e:
        logger.error(f"BatchMesher 失败: {e}")
        if info:
          info.status = "failed"

    logger.info(f"===== BatchMesher 完成: {len(mesh_map)}/{len(rep_map)} =====")
    return mesh_map

  def run(
    self, part_ids: list = None,
    criteria_file: str = None, param_file: str = None,
    skip_save: bool = False,
  ) -> PartRepResult:
    if skip_save:
      rep_map = {}
      if part_ids is None:
        part_ids = api_get_part_list(self.session)
      for pid in part_ids:
        name = api_get_part_name(self.session, pid)
        safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
        cad_file = os.path.join(self.rep_dir, f"{safe_name}_CAD_-_-_1.hm")
        if os.path.isfile(cad_file):
          info = PartRepInfo(part_id=pid, part_name=name, cad_file=cad_file, status="done")
          self._parts[pid] = info
          rep_map[pid] = cad_file
    else:
      rep_map = self.save_all_reps(part_ids)

    if not rep_map:
      return PartRepResult(success=False, message="无 CAD 文件")

    mesh_map = self.batchmesh_all(rep_map, criteria_file, param_file)
    if not mesh_map:
      return PartRepResult(success=False, parts=list(self._parts.values()),
                          message="BatchMesher 无输出")

    done = sum(1 for i in self._parts.values() if i.status == "done")
    return PartRepResult(success=True, parts=list(self._parts.values()),
                        message=f"完成: {done} 个网格")

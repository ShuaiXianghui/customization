"""
平衡重式叉车车架 - 半自动化网格划分脚本 (HyperMesh Python API)
================================================================
处理流程：
  第1步：几何简化 — 清除直径<10mm的圆孔、半径<10mm的圆角
  第2步：零件命名 — 按板厚自动分级命名（T+厚度+shell 或 T+厚度+solid）
  第3步：材料属性 — 创建Q235/Q355材料，按板厚建立属性并赋予零件
  第4步：中面抽取 — 对薄板（<=10mm）零件抽取中面
  第5步：网格划分 — 三级网格策略：
          薄板(<=10mm):    中面抽取 + BatchMesh shell 5mm
          中厚板(10~15mm):  elemoffset_thinsolid 六面体, 厚度方向3层, 面内5mm
          厚板(>=15mm):     elemoffset_thinsolid 六面体, 层数=厚度/5, 面内5mm

材料参数：
  Q235: E=212000MPa, Nu=0.288, Rho=7.86E3
  Q355: E=206000MPa, Nu=0.280, Rho=7.85E3

属性规则：
  薄板(<=10mm):      PSHELL, 命名 T{厚度}_Q235, 厚度=实测板厚, 材料Q235
  中厚板(10~15mm):   PSOLID, 命名 SW, 材料Q355
  厚板(>=15mm):      PSOLID, 命名 SW, 材料Q355（中厚板和厚板共用SW属性）

所有函数均基于 pythonapi/ 文件夹内的 HyperMesh API 文档。
"""

import hm
import hm.entities as ent


# ============================================================
# 工具函数
# ============================================================

def performance_mode(model, enable):
    """
    性能加速开关。参考 hm_examples.md 示例06。
    关闭图形刷新和命令录制，大幅提升批量处理速度。
    """
    if enable:
        hm.setoption(block_redraw=1, command_file_state=0, entity_highlighting=0)
        model.hm_blockbrowserupdate(mode=1)
    else:
        hm.setoption(block_redraw=0, command_file_state=1, entity_highlighting=1)
        model.hm_blockbrowserupdate(mode=0)


# ============================================================
# 第1步：几何简化 — 清除小孔和圆角
# ============================================================

def step1_geometry_cleanup(model, hole_max_diameter=10.0, fillet_max_radius=10.0):
    """
    清除直径小于指定值的圆孔和半径小于指定值的圆角。

    API来源：
      surfacemarkremoveallpinholes  → hm_mod_funcs/model.surfacemarkremoveallpinholes.md
      remove_solid_holes            → hm_mod_funcs/model.remove_solid_holes.md
      removeedgefillets             → hm_mod_funcs/model.removeedgefillets.md
    """
    print("=" * 60)
    print("  第1步：几何简化处理")
    print("=" * 60)

    all_surfaces = hm.Collection(model, ent.Surface)
    all_solids = hm.Collection(model, ent.Solid)

    print(f"  曲面: {len(all_surfaces)} 个  |  实体: {len(all_solids)} 个")
    print(f"  清除阈值: 孔径 < {hole_max_diameter}mm, 圆角半径 < {fillet_max_radius}mm")

    performance_mode(model, True)
    try:
        # 1a. 移除曲面上的小销孔（直径 < 10mm）
        print("  [1/3] 移除曲面小孔...")
        if len(all_surfaces) > 0:
            model.surfacemarkremoveallpinholes(
                collection=all_surfaces,
                diameter=hole_max_diameter
            )
            print("    OK")
        else:
            print("    无曲面")

        # 1b. 移除3D实体中的小孔（直径 < 10mm）
        print("  [2/3] 移除实体小孔...")
        if len(all_solids) > 0:
            model.remove_solid_holes(
                collection=all_solids,
                max_diam=hole_max_diameter,
                cross_sect_size_max=hole_max_diameter * 2.0,
                options=0,            # 不限形状
                string_array=hm.hwStringList()
            )
            print("    OK")
        else:
            print("    无实体")

        # 1c. 移除边缘圆角（半径 < 10mm）
        print("  [3/3] 移除曲面边缘圆角...")
        if len(all_surfaces) > 0:
            model.removeedgefillets(
                collection=all_surfaces,
                min_radius=0.0,
                max_radius=fillet_max_radius,
                min_angle=0.0,
                failed_elem_size=0.0
            )
            print("    OK")
        else:
            print("    无曲面")

    finally:
        performance_mode(model, False)

    print("  第1步完成。\n")


# ============================================================
# 第2步：零件命名 — 按板厚自动分类
# ============================================================

def step2_component_naming(model, shell_threshold=10.0, solid_mid_threshold=15.0):
    """
    检测每个实体的板厚，按规则命名并重组零件：
      - 厚度 <= shell_threshold          → 命名 "T{厚度}_shell"
      - shell_threshold < 厚度 < solid_mid_threshold → 命名 "T{厚度}_solid"（中厚板）
      - 厚度 >= solid_mid_threshold       → 命名 "T{厚度}_solid"（厚板）

    API来源：
      hm_getgeometricthinsolidinfo → hm_query_funcs/model.hm_getgeometricthinsolidinfo.md
      movemark                      → hm_mod_funcs (示例: hm_examples.md 示例06)

    参数：
        model               : HyperMesh Model 对象
        shell_threshold     : 壳/实体分类阈值（mm），默认10.0
        solid_mid_threshold : 中厚板/厚板分界阈值（mm），默认15.0

    返回：
        dict {
            "shell_comps":       [(comp_name, thickness, solid_ids), ...],
            "solid_mid_comps":   [(comp_name, thickness, solid_ids), ...],
            "solid_thick_comps": [(comp_name, thickness, solid_ids), ...],
        }
    """
    print("=" * 60)
    print("  第2步：零件厚度检测与命名")
    print("=" * 60)

    all_solids = hm.Collection(model, ent.Solid)

    if len(all_solids) == 0:
        print("  模型中没有实体，跳过。")
        return {"shell_comps": [], "solid_mid_comps": [], "solid_thick_comps": []}

    # 使用 hm_getgeometricthinsolidinfo 批量获取所有实体厚度
    print(f"  正在检测 {len(all_solids)} 个实体的壁厚...")
    _, result_list = model.hm_getgeometricthinsolidinfo(
        collection=all_solids,
        mode="simple"
    )

    if not result_list:
        print("  警告：未能获取厚度信息。请检查几何是否完整。")
        return {"shell_comps": [], "solid_mid_comps": [], "solid_thick_comps": []}

    # 按厚度分组：{thickness_str: [solid_id, ...]}
    shell_groups = {}
    solid_mid_groups = {}
    solid_thick_groups = {}

    for result in result_list:
        sid = result.entity.id
        t = result.thickness

        if t <= 0.0:
            print(f"  警告：实体 {sid} 厚度异常 ({t})，已跳过。")
            continue

        t_key = f"{t:.1f}"

        if t <= shell_threshold:
            shell_groups.setdefault(t_key, []).append(sid)
        elif t < solid_mid_threshold:
            solid_mid_groups.setdefault(t_key, []).append(sid)
        else:
            solid_thick_groups.setdefault(t_key, []).append(sid)

    # 打印检测结果
    total_shell = sum(len(v) for v in shell_groups.values())
    total_mid = sum(len(v) for v in solid_mid_groups.values())
    total_thick = sum(len(v) for v in solid_thick_groups.values())

    print(f"\n  检测结果：")
    print(f"    薄板 (<= {shell_threshold}mm → _shell): {total_shell} 个实体")
    for t_key in sorted(shell_groups.keys(), key=float):
        print(f"      T{t_key}_shell : {len(shell_groups[t_key])} 个实体")
    print(f"    中厚板 ({shell_threshold}mm < t < {solid_mid_threshold}mm → _solid, "
          f"厚度方向3层): {total_mid} 个实体")
    for t_key in sorted(solid_mid_groups.keys(), key=float):
        print(f"      T{t_key}_solid : {len(solid_mid_groups[t_key])} 个实体")
    print(f"    厚板 (>= {solid_mid_threshold}mm → _solid): {total_thick} 个实体")
    for t_key in sorted(solid_thick_groups.keys(), key=float):
        print(f"      T{t_key}_solid : {len(solid_thick_groups[t_key])} 个实体")

    # 创建组件并移动实体
    print(f"\n  正在组织实体到新组件...")

    shell_comp_info = []
    solid_mid_comp_info = []
    solid_thick_comp_info = []

    performance_mode(model, True)
    try:
        for t_key, sids in shell_groups.items():
            comp_name = f"T{t_key}_shell"
            _create_and_move(model, comp_name, sids)
            shell_comp_info.append((comp_name, float(t_key), sids))
            print(f"    {comp_name}: {len(sids)} 个实体")

        for t_key, sids in solid_mid_groups.items():
            comp_name = f"T{t_key}_solid"
            _create_and_move(model, comp_name, sids)
            solid_mid_comp_info.append((comp_name, float(t_key), sids))
            print(f"    {comp_name}: {len(sids)} 个实体")

        for t_key, sids in solid_thick_groups.items():
            comp_name = f"T{t_key}_solid"
            _create_and_move(model, comp_name, sids)
            solid_thick_comp_info.append((comp_name, float(t_key), sids))
            print(f"    {comp_name}: {len(sids)} 个实体")

    finally:
        performance_mode(model, False)

    total_new = len(shell_comp_info) + len(solid_mid_comp_info) + len(solid_thick_comp_info)
    print(f"\n  第2步完成：创建了 {total_new} 个组件。\n")

    return {
        "shell_comps": shell_comp_info,
        "solid_mid_comps": solid_mid_comp_info,
        "solid_thick_comps": solid_thick_comp_info,
    }


def _create_and_move(model, comp_name, solid_ids):
    """
    创建命名组件并将指定实体移入。
    API来源：ent.Component (hm_entities.md), movemark (hm_mod_funcs)
    """
    comp = ent.Component(model)
    comp.name = comp_name
    solid_col = hm.Collection(model, ent.Solid, solid_ids)
    model.movemark(collection=solid_col, name=comp_name)


# ============================================================
# 第3步：材料与属性创建 + 赋予零件
# ============================================================

def step3_material_property_assignment(model, naming_result):
    """
    创建材料 Q235 / Q355，按板厚建立属性并赋予到对应组件。

    材料参数：
      Q235: E=212000MPa, Nu=0.288, Rho=7.86E3
      Q355: E=206000MPa, Nu=0.280, Rho=7.85E3
      （密度值基于SI单位kg/m³，如模型使用mm-ton-s单位请改为7.86E-9等）

    属性规则：
      - 薄板（<=10mm）：PSHELL, 命名为 "T{厚度}_Q235", 板厚=实测厚度, 材料=Q235
      - 厚板（>10mm）： PSOLID, 命名为 "SW", 材料=Q355（所有厚板共用SW属性）

    API来源：
      ent.Material / ent.Property   → hm_entities.md
      PSHELL_T / materialid         → examples/hm_examples.md 示例04/05

    参数：
        model          : HyperMesh Model 对象
        naming_result  : 第2步返回的 dict

    返回：
        dict {
            "mat_q235": Material实体,
            "mat_q355": Material实体,
            "shell_props": {comp_name: Property实体, ...},
            "solid_prop": Property实体 (SW),
        }
    """
    print("=" * 60)
    print("  第3步：材料与属性创建 + 赋予零件")
    print("=" * 60)

    shell_comps = naming_result.get("shell_comps", [])
    solid_mid_comps = naming_result.get("solid_mid_comps", [])
    solid_thick_comps = naming_result.get("solid_thick_comps", [])
    solid_comps = solid_mid_comps + solid_thick_comps  # 合并用于属性赋予

    # ---- 3a. 创建材料 Q235 ----
    print("\n  [材料] 创建 Q235 和 Q355 ...")
    mat_q235 = ent.Material(model)
    mat_q235.name = "Q235"
    mat_q235.cardimage = "MAT1"
    mat_q235.E = 212000.0         # 弹性模量 MPa
    mat_q235.Nu = 0.288           # 泊松比
    mat_q235.Rho = 7.86E3         # 密度（注意单位系统）
    print(f"    Q235: E=212000, Nu=0.288, Rho=7.86E3 (MAT1)  [ID={mat_q235.id}]")

    # ---- 3b. 创建材料 Q355 ----
    mat_q355 = ent.Material(model)
    mat_q355.name = "Q355"
    mat_q355.cardimage = "MAT1"
    mat_q355.E = 206000.0         # 弹性模量 MPa
    mat_q355.Nu = 0.280           # 泊松比
    mat_q355.Rho = 7.85E3         # 密度（注意单位系统）
    print(f"    Q355: E=206000, Nu=0.280, Rho=7.85E3 (MAT1)  [ID={mat_q355.id}]")

    # ---- 3c. 创建壳属性（PSHELL）并赋予薄板组件 ----
    shell_props = {}

    if shell_comps:
        print(f"\n  [壳属性] 为 {len(shell_comps)} 个薄板组件创建 PSHELL 属性...")
        for comp_name, thickness, solid_ids in shell_comps:
            prop_name = f"T{thickness:.1f}_Q235"

            # 创建 PSHELL 属性
            prop = ent.Property(model)
            prop.name = prop_name
            prop.cardimage = "PSHELL"
            prop.materialid = mat_q235
            prop.PSHELL_T = thickness      # 板厚

            # 赋予到对应组件
            try:
                comp = _ensure_component_exists(model, comp_name)
                comp.propertyid = prop
                print(f"    {prop_name}: PSHELL T={thickness}mm, 材料Q235 -> {comp_name}")
            except Exception as e:
                print(f"    {prop_name}: 创建成功，但组件赋予失败: {e}")

            shell_props[comp_name] = prop

    # ---- 3d. 创建实体属性（PSOLID）并赋予厚板组件 ----
    solid_prop = None

    if solid_comps:
        print(f"\n  [实体属性] 为 {len(solid_comps)} 个厚板组件创建 PSOLID 属性...")
        # 所有厚板共用一个 SW 属性
        solid_prop = ent.Property(model)
        solid_prop.name = "SW"
        solid_prop.cardimage = "PSOLID"
        solid_prop.materialid = mat_q355
        print(f"    SW: PSOLID, 材料Q355 [ID={solid_prop.id}]")

        for comp_name, thickness, solid_ids in solid_comps:
            try:
                comp = _ensure_component_exists(model, comp_name)
                comp.propertyid = solid_prop
                print(f"    赋予 SW -> {comp_name} (厚度≈{thickness}mm)")
            except Exception as e:
                print(f"    赋予 SW -> {comp_name} 失败: {e}")

    print(f"\n  第3步完成。\n")

    return {
        "mat_q235": mat_q235,
        "mat_q355": mat_q355,
        "shell_props": shell_props,
        "solid_prop": solid_prop,
    }


# ============================================================
# 第4步：中面抽取 — 薄板零件
# ============================================================

def step4_midsurface_extraction(model, shell_comp_info, material_result=None):
    """
    对薄板（_shell 后缀）零件进行中面抽取。
    使用 new_or_curr_comp=7，中面曲面存入 "Midsurface_{original_name}" 组件，
    以便后续追踪来源。

    API来源：
      midsurface_extract_10 → hm_mod_funcs/model.midsurface_extract_10.md

    参数：
        model            : HyperMesh Model 对象
        shell_comp_info  : 第2步返回的 shell_comps 列表
                           [(comp_name, thickness, solid_ids), ...]
        material_result  : 第3步返回的 dict（含 shell_props 映射）

    返回：
        mapping : {original_comp_name: "Midsurface_xxx", ...}
    """
    print("=" * 60)
    print("  第4步：中面抽取（薄板 _shell 零件）")
    print("=" * 60)

    if not shell_comp_info:
        print("  无薄板零件，跳过中面抽取。")
        return {}

    print(f"  待处理: {len(shell_comp_info)} 个组件")

    done = {}
    performance_mode(model, True)

    try:
        for comp_name, thickness, solid_ids in shell_comp_info:
            print(f"  抽取中面: {comp_name} (厚度≈{thickness}mm, {len(solid_ids)}个实体)...")

            solid_col = hm.Collection(model, ent.Solid, solid_ids)

            try:
                model.midsurface_extract_10(
                    collection=solid_col,
                    outbound_normals=3,
                    thickness_bound=0,
                    align_steps=1,
                    extract_by_comp=1,
                    rerun_type=0,
                    stitch_tol_mode=0,
                    max_R_t_ratio=2.0,
                    reserved_1=0.0,
                    reserved_2=0.0,
                    max_thickness_ratio=10.0,
                    min_thickness=0.0,
                    max_thickness=0.0,
                    mid_position=0.5,
                    reserved_4=hm.Collection(model, ent.Component, populate=False),
                    reserved_5=0,
                    new_or_curr_comp=7        # 前缀 "Midsurface_"
                )
                midsurf_comp_name = f"Midsurface_{comp_name}"
                done[comp_name] = midsurf_comp_name
                print(f"    OK -> {midsurf_comp_name}")
            except Exception as e:
                print(f"    出错: {e}")

    finally:
        performance_mode(model, False)

    print(f"\n  第4步完成：成功处理 {len(done)}/{len(shell_comp_info)} 个组件。\n")
    return done


# ============================================================
# 辅助函数：薄壁实体六面体网格（elemoffset_thinsolid）
# ============================================================

def _hex_mesh_thin_solid(model, solid_ids, num_layers, target_comp_name=None):
    """
    对板类实体使用 elemoffset_thinsolid 生成六面体为主的实体网格。
    自动检测源面/目标面/侧面，从源面2D网格挤出num_layers层六面体。

    API来源：
      elemoffset_thinsolid → hm_mod_funcs/model.elemoffset_thinsolid.md

    参数：
        model             : HyperMesh Model 对象
        solid_ids         : 实体ID列表
        num_layers        : 厚度方向层数（密度density）
        target_comp_name  : 目标组件名（可选，用于后续网格转移）

    返回：
        (success: bool, message: str)
    """
    solid_col = hm.Collection(model, ent.Solid, solid_ids)
    empty_surfs = hm.Collection(model, ent.Surface, populate=False)

    # 2D源面网格参数: "2d: <elem_type> <elem_order> <method> <size> <min_size> <feature_angle> <mesh_flow>"
    # elem_type=2(Mixed), elem_order=1(First), method=2(free), size=5.0
    string_array = hm.hwStringList()
    string_array.append("2d: 2 1 2 5.0 1.5 25.0 1")

    # modes=128: Bit6-7=10 → 自动检测源/目标/侧面并划分
    #             Bit4=0 → 生成实体单元层（非壳层）
    #             Bit1=0 → 单元归属原组件
    try:
        model.elemoffset_thinsolid(
            collection_source=solid_col,
            collection_target=empty_surfs,
            collection_along=empty_surfs,
            modes=128,
            density=num_layers,
            biasing=0.0,
            string_array=string_array,
            batchmesh_source=1
        )
        return True, f"六面体网格 OK ({num_layers}层)"

    except Exception as e:
        return False, f"elemoffset_thinsolid 失败: {e}"


# ============================================================
# 第5步：网格划分（壳: batchmesh2 / 实体: elemoffset_thinsolid六面体）
# ============================================================

def step5_batchmesh_5mm(model, naming_result, midsurf_mapping=None, material_result=None):
    """
    三级网格划分策略：
      - 薄板 (<=10mm):    中面组件 → batchmesh2 shell → 转移单元到 T{厚度}_shell
      - 中厚板 (10~15mm): elemoffset_thinsolid 六面体, 厚度方向3层, 面内5mm
      - 厚板 (>=15mm):    elemoffset_thinsolid 六面体, 层数=厚度/5, 面内5mm

    壳网格划分后，将单元从 Midsurface_* 组件转移到对应的 T{厚度}_shell 组件，
    并赋予对应的 PSHELL 属性。

    API来源：
      batchmesh2               → hm_mod_funcs/model.batchmesh2.md
      elemoffset_thinsolid     → hm_mod_funcs/model.elemoffset_thinsolid.md
      movemark                 → hm_mod_funcs (示例: hm_examples.md 示例06)

    参数：
        model            : HyperMesh Model 对象
        naming_result    : 第2步返回的 dict
        midsurf_mapping  : 第4步返回的 {comp_name: midsurf_comp_name}
        material_result  : 第3步返回的 dict（含 shell_props）
    """
    print("=" * 60)
    print("  第5步：BatchMesh 5mm 网格划分")
    print("=" * 60)

    shell_comps = naming_result.get("shell_comps", [])
    solid_mid_comps = naming_result.get("solid_mid_comps", [])
    solid_thick_comps = naming_result.get("solid_thick_comps", [])
    shell_props = material_result.get("shell_props", {}) if material_result else {}

    print(f"  壳组件: {len(shell_comps)} 个  |  "
          f"中厚板实体: {len(solid_mid_comps)} 个  |  "
          f"厚板实体: {len(solid_thick_comps)} 个")
    print(f"  壳网格: BatchMesh 5mm  |  实体: elemoffset_thinsolid 六面体 5mm")

    performance_mode(model, True)

    try:
        # ---- 壳网格（中面曲面 → 2D壳单元 → 转移至 T{厚度}_shell）----
        if shell_comps:
            print(f"\n  [壳网格] 划分中面组件网格...")
            midsurf_comps = _find_midsurface_components(model)

            if midsurf_comps:
                for comp in midsurf_comps:
                    print(f"    网格划分: {comp.name} ...")
                    try:
                        model.batchmesh2(
                            collection=hm.Collection([comp]),
                            criteria_file="dummy",
                            param_file="dummy",
                            elemSize=5.0,
                            elemType=2,
                            elemOrder=1,
                            minElemSize=1.5,
                            maxElemSize=8.75,
                            elemFeatureAngle=25.0,
                            paramsGenerateMode="shell"
                        )
                        print(f"      OK")
                    except Exception as e:
                        print(f"      出错: {e}")

                # ---- 转移单元到 T{厚度}_shell 并赋予属性 ----
                print("\n  [转移] 将壳网格单元转移至 T厚度_shell 组件...")
                _transfer_elems_to_target(model, midsurf_comps, shell_props)

            else:
                print(f"    未找到中面组件，对所有曲面进行壳网格划分...")
                _batchmesh_all_surfaces(model, "shell")

        # ---- 中厚板实体网格（10mm < t < 15mm, 六面体, 3层, 5mm）----
        if solid_mid_comps:
            print(f"\n  [中厚板六面体网格] 对 {len(solid_mid_comps)} 个组件 "
                  f"(elemoffset_thinsolid, 3层, 5mm)...")
            for comp_name, thickness, solid_ids in solid_mid_comps:
                print(f"    处理: {comp_name} (厚度≈{thickness}mm, "
                      f"{len(solid_ids)}个实体)...")

                success, msg = _hex_mesh_thin_solid(
                    model, solid_ids, num_layers=3, target_comp_name=comp_name
                )
                if success:
                    print(f"      {msg}")
                else:
                    print(f"      {msg}，尝试 batchmesh2 备用...")
                    try:
                        comp = _ensure_component_exists(model, comp_name)
                        model.batchmesh2(
                            collection=hm.Collection([comp]),
                            criteria_file="dummy",
                            param_file="dummy",
                            elemSize=5.0,
                            elemType=2,
                            elemOrder=1,
                            paramsGenerateMode="solid"
                        )
                        print(f"      OK (batchmesh2 备用)")
                    except Exception as e2:
                        print(f"      备用也失败: {e2}")

        # ---- 厚板实体网格（>=15mm, 六面体, 层数=厚度/5mm）----
        if solid_thick_comps:
            print(f"\n  [厚板六面体网格] 对 {len(solid_thick_comps)} 个组件 "
                  f"(elemoffset_thinsolid, 5mm)...")
            for comp_name, thickness, solid_ids in solid_thick_comps:
                layers = max(2, int(thickness / 5.0 + 0.5))
                print(f"    处理: {comp_name} (厚度≈{thickness}mm, "
                      f"{layers}层, {len(solid_ids)}个实体)...")

                success, msg = _hex_mesh_thin_solid(
                    model, solid_ids, num_layers=layers, target_comp_name=comp_name
                )
                if success:
                    print(f"      {msg}")
                else:
                    print(f"      {msg}，尝试 batchmesh2 备用...")
                    try:
                        comp = _ensure_component_exists(model, comp_name)
                        model.batchmesh2(
                            collection=hm.Collection([comp]),
                            criteria_file="dummy",
                            param_file="dummy",
                            elemSize=5.0,
                            elemType=2,
                            elemOrder=1,
                            minElemSize=1.5,
                            maxElemSize=8.75,
                            elemFeatureAngle=25.0,
                            paramsGenerateMode="solid"
                        )
                        print(f"      OK (batchmesh2 备用)")
                    except Exception as e2:
                        print(f"      备用也失败: {e2}")

    finally:
        performance_mode(model, False)

    # 清理空组件
    _cleanup_empty_components(model)

    print(f"\n  第5步完成：壳网格5mm + 实体六面体网格(elemoffset_thinsolid)。\n")


def _cleanup_empty_components(model):
    """删除不含任何单元和几何体的空组件（单次遍历）。"""
    # 一次遍历所有单元，收集有单元的组件ID
    used_comp_ids = set()
    all_elems = hm.Collection(model, ent.Element)
    for e in all_elems:
        cid = _safe_get_component_id(e)
        if cid is not None:
            used_comp_ids.add(cid)

    # 删除不在使用列表中的组件
    deleted = 0
    all_comps = hm.Collection(model, ent.Component)
    for comp in all_comps:
        try:
            if comp.id not in used_comp_ids:
                model.delete(comp)
                deleted += 1
        except Exception:
            continue

    if deleted > 0:
        print(f"    清理了 {deleted} 个空组件。")


def _find_midsurface_components(model):
    """查找所有中面组件（名称以 'Midsurface_' 开头）。"""
    all_comps = hm.Collection(model, ent.Component)
    midsurf = []
    for comp in all_comps:
        try:
            if comp.name and comp.name.startswith("Midsurface_"):
                midsurf.append(comp)
        except Exception:
            continue
    return midsurf


def _transfer_elems_to_target(model, midsurf_comps, shell_props):
    """
    将中面组件中的单元转移到对应的 T{厚度}_shell 组件，
    并赋予对应的 PSHELL 属性。
    """
    all_elems = hm.Collection(model, ent.Element)
    if len(all_elems) == 0:
        print("    没有单元。")
        return

    # 建立映射：中面组件 -> 目标组件名 & 属性
    target_map = {}  # midsurf_name -> (target_name, property)
    for c in midsurf_comps:
        tgt = c.name.replace("Midsurface_", "", 1)
        target_map[c.name] = (tgt, shell_props.get(tgt))

    # 一次遍历：按中面组件名分组单元ID
    groups = {}
    for elem in all_elems:
        comp_name = _safe_get_component_name(elem)
        if comp_name and comp_name in target_map:
            groups.setdefault(comp_name, []).append(elem.id)

    # 如果组件名匹配法找不到单元，使用组件ID匹配
    if not groups:
        print("    组件名匹配无结果，尝试组件ID匹配...")
        midsurf_ids = {}
        for c in midsurf_comps:
            midsurf_ids[c.id] = c.name
        for elem in all_elems:
            cid = _safe_get_component_id(elem)
            if cid and cid in midsurf_ids:
                groups.setdefault(midsurf_ids[cid], []).append(elem.id)

    if not groups:
        print("    未找到属于中面组件的单元。")
        return

    # 转移并赋予属性
    for midsurf_name, elem_ids in groups.items():
        target_name, prop = target_map[midsurf_name]

        # 移动单元到目标组件
        try:
            elem_col = hm.Collection(model, ent.Element, elem_ids)
            model.movemark(collection=elem_col, name=target_name)
            print(f"    {len(elem_ids)} 个单元: {midsurf_name} -> {target_name}")
        except Exception as e:
            print(f"    {midsurf_name} 转移失败: {e}")
            continue

        # 赋予属性到目标组件
        if prop is not None:
            try:
                target_comp = _ensure_component_exists(model, target_name)
                target_comp.propertyid = prop
                print(f"    属性: {prop.name} -> {target_name}")
            except Exception as e:
                print(f"    属性赋予失败: {e}")


def _safe_get_component_name(elem):
    """安全获取元素所在组件名称。"""
    for attr in ("component", "collector", "comp"):
        try:
            obj = getattr(elem, attr, None)
            if obj is not None:
                name = getattr(obj, "name", None)
                if name:
                    return name
        except Exception:
            continue
    return None


def _safe_get_component_id(elem):
    """安全获取元素所在组件ID（整型）。"""
    for attr in ("component", "collector", "comp"):
        try:
            obj = getattr(elem, attr, None)
            if obj is not None:
                cid = getattr(obj, "id", None)
                if cid is not None:
                    return int(cid)
        except Exception:
            continue
    return None


def _ensure_component_exists(model, name):
    """获取或创建指定名称的组件。"""
    try:
        return model.get(ent.Component, f'name="{name}"')
    except Exception:
        comp = ent.Component(model)
        comp.name = name
        return comp


def _batchmesh_all_surfaces(model, mode):
    """备用：对所有曲面执行 batchmesh 网格划分。"""
    try:
        all_surfs = hm.Collection(model, ent.Surface)
        if len(all_surfs) > 0:
            model.batchmesh2(
                collection=all_surfs,
                criteria_file="dummy",
                param_file="dummy",
                elemSize=5.0,
                elemType=2,
                paramsGenerateMode=mode
            )
            print(f"      OK (全部曲面)")
    except Exception as e:
        print(f"      全部曲面网格划分也失败: {e}")


# ============================================================
# 第6步：焊缝建模 — 相邻零件检测 + 焊缝宽度计算
# ============================================================

def step6_weld_modeling(model, naming_result):
    """
    对所有零部件自动创建缝焊连接器并实现。
    搜索半径=30mm，焊缝宽度=10mm，间距=5mm，实体焊缝≥3层。

    API来源：
      CE_ConnectorCreateByAutoseam → hm_mod_funcs/model.CE_ConnectorCreateByAutoseam.md
      CE_Realize                   → hm_mod_funcs/model.CE_Realize.md
      CE_DetailSetIntByMark        → hm_mod_funcs/model.CE_DetailSetIntByMark.md
    """
    print("=" * 60)
    print("  第6步：焊缝建模")
    print("=" * 60)

    # 收集所有组件
    shell_comps = naming_result.get("shell_comps", [])
    solid_mid_comps = naming_result.get("solid_mid_comps", [])
    solid_thick_comps = naming_result.get("solid_thick_comps", [])
    all_comp_names = [c[0] for c in shell_comps] + [c[0] for c in solid_mid_comps] + [c[0] for c in solid_thick_comps]

    if len(all_comp_names) < 2:
        print("  零件数量 < 2，无需焊缝建模。")
        return []

    print(f"  零件总数: {len(all_comp_names)}")
    print(f"  搜索半径: 30mm | 焊缝宽度: 10mm | 间距: 5mm | 层数: 3")

    # 收集所有组件实体
    comp_list = []
    for name in all_comp_names:
        try:
            comp_list.append(_ensure_component_exists(model, name))
        except Exception:
            pass
    all_comps = hm.Collection(comp_list)

    performance_mode(model, True)

    try:
        # ---- 6a. 自动创建缝焊连接器 (搜索半径=30mm) ----
        print(f"\n  [创建] 搜索半径=30mm ...")
        model.CE_ConnectorCreateByAutoseam(
            collection=all_comps,
            options=(
                "search_radius = 30.000000 "
                "pitch = 5.000000 "
                "minimum_connector_length = 5.000000 "
                "exclude_holes_with_radius_less_than = 3.000000 "
                "create_internal_seams = 0 "
                "overlap_percentage = 50"
            )
        )
        print(f"    完成。")

        # ---- 6b. 扩展搜索半径 ----
        for radius in [50.0, 100.0]:
            print(f"  [扩展] 搜索半径={radius:.0f}mm ...")
            try:
                model.CE_ConnectorCreateByAutoseam(
                    collection=all_comps,
                    options=(
                        f"search_radius = {radius:.1f} "
                        f"pitch = 5.000000 "
                        f"minimum_connector_length = 5.000000 "
                        f"exclude_holes_with_radius_less_than = 3.000000 "
                        f"create_internal_seams = 0 "
                        f"overlap_percentage = 50"
                    )
                )
            except Exception:
                pass

        # ---- 6c. 创建连接器控制 (Penta六面体焊缝) ----
        print(f"\n  [控制] 创建连接器控制...")
        model.AE_AttachmentControlDefaultCreate(reserved1="", reserved2=1)
        model.CE_FE_CreateDCC(reserved=1)
        model.CE_FE_CreateUCCFromDCC(
            cc_name="connectorcontrol1",
            ccd_name="Bar2_seam_template"
        )

        cc = ent.Connectorcontrol(model, 1)
        cc.name = "penta"
        cc.ce_configname = "Penta (Mig)"
        cc.ce_spacing = 5          # 间距5mm
        cc.ce_fe_depth = 10        # 焊缝宽度10mm
        cc.ce_tolerance = 30       # 搜索容差30mm

        # ---- 6d. 统计连接器 ----
        ce_col = hm.Collection(model, ent.Connector)
        total = len(ce_col)
        print(f"    连接器总数: {total}")

        if total == 0:
            print("    未创建任何连接器，跳过后续步骤。")
            return []

        # ---- 6e. 应用连接器控制 ----
        print(f"\n  [应用] 更新连接器控制...")
        model.CE_FE_ConnectorUpdateByCC(
            ce_collection=ce_col,
            cc_name="penta",
            cc_type=ent.Connectorcontrol
        )

        # ---- 6f. 设置焊缝层数=3 ----
        print(f"  [层数] ce_layers = 3 ...")
        model.CE_DetailSetIntByMark(
            collection=ce_col,
            detail_name="ce_layers",
            integer_value=3,
            reserved=0,
            force_storage=0,
        )

        # ---- 6g. Realize连接器 ----
        print(f"  [实现] Realize连接器...")
        model.CE_Realize(collection=ce_col)

    finally:
        performance_mode(model, False)

    print(f"\n  第6步完成: {total} 个焊缝 (宽度=10mm, 层数=3, Penta)\n")
    return ce_col


# ============================================================
# 完整流水线
# ============================================================

def run_full_pipeline():
    """
    一键运行完整流水线（5步）：
      几何简化 → 零件命名 → 材料属性 → [确认] → 中面抽取 → 网格划分
    """
    model = hm.Model()

    print("\n" + "*" * 60)
    print("*   平衡重式叉车车架 — 半自动化网格划分")
    print("*   孔<10mm | 圆角<10mm | <=10mm→壳5mm | >10mm→六面体网格5mm")
    print("*   中厚板(10~15mm): 3层 | 厚板(>=15mm): 厚度/5层")
    print("*" * 60)

    # 第1步：几何简化
    step1_geometry_cleanup(model)

    # 第2步：零件命名
    result = step2_component_naming(model)

    if not result["shell_comps"] and not result["solid_mid_comps"] and not result["solid_thick_comps"]:
        print("未检测到可处理的组件，流水线终止。")
        return

    # 第3步：材料与属性创建 + 赋予
    material_result = step3_material_property_assignment(model, result)

    # 用户确认
    print("─" * 60)
    resp = input("继续第4、5步（中面抽取 + 5mm网格划分）？(y/n): ").strip().lower()
    if resp not in ("y", "yes"):
        print("已暂停。几何清理、零件命名和材料属性已完成。")
        return

    # 第4步：中面抽取
    midsurf_mapping = step4_midsurface_extraction(model, result["shell_comps"], material_result)

    # 第5步：BatchMesh 5mm（含壳网格转移和属性赋予）
    step5_batchmesh_5mm(model, result, midsurf_mapping, material_result)

    # 第6步：焊缝建模
    step6_weld_modeling(model, result)

    print("=" * 60)
    print("  全流程完成！请检查模型网格质量。")
    print("  - _shell组件 (<=10mm)：壳网格 + PSHELL属性 + Q235材料")
    print("  - _solid组件 (>10mm) ：六面体网格(elemoffset) + PSOLID(SW) + Q355")
    print("    · 中厚板(10~15mm)：3层5mm")
    print("    · 厚板(>=15mm)：厚度/5层5mm")
    print("  - 焊缝：相邻零件间，宽度=10mm, 层数=3")
    print("=" * 60)


def run_interactive():
    """
    交互模式：逐步确认，每步可跳过。
    适合需要人工判断每一步结果的场景。
    """
    model = hm.Model()
    result = {"shell_comps": [], "solid_mid_comps": [], "solid_thick_comps": []}
    material_result = {"mat_q235": None, "mat_q355": None, "shell_props": {}, "solid_prop": None}
    midsurf_mapping = {}

    steps = []

    # 用闭包捕获变量
    def do_step1():
        step1_geometry_cleanup(model)

    def do_step2():
        r = step2_component_naming(model)
        result.clear()
        result.update(r)

    def do_step3():
        r = step3_material_property_assignment(model, result)
        material_result.clear()
        material_result.update(r)

    def do_step4():
        m = step4_midsurface_extraction(model, result.get("shell_comps", []), material_result)
        midsurf_mapping.clear()
        midsurf_mapping.update(m)

    def do_step5():
        step5_batchmesh_5mm(model, result, midsurf_mapping, material_result)

    def do_step6():
        step6_weld_modeling(model, result)

    steps = [
        ("第1步：几何简化", do_step1),
        ("第2步：零件命名", do_step2),
        ("第3步：材料属性", do_step3),
        ("第4步：中面抽取", do_step4),
        ("第5步：网格划分", do_step5),
        ("第6步：焊缝建模", do_step6),
    ]

    print("\n" + "*" * 60)
    print("*   叉车车架网格划分 — 分步交互模式")
    print("*" * 60)

    for name, action in steps:
        resp = input(f"\n>>> 执行 {name}？(y/n/q): ").strip().lower()
        if resp == "q":
            print("用户退出。")
            return
        if resp not in ("y", "yes"):
            print(f"跳过 {name}。")
            continue
        action()

    print("\n" + "=" * 60)
    print("  交互模式完成！")
    print("=" * 60)


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    """
    运行说明：
      1. 在 HyperMesh 中打开叉车车架模型
      2. File > Run > Script → 选择本脚本
      3. 默认执行全自动流水线 run_full_pipeline()

    也可在 HyperMesh 命令行单独调用：
      - step1_geometry_cleanup(hm.Model())       仅几何清理
      - step2_component_naming(hm.Model())       仅零件命名
      - step3_material_property_assignment(...)  仅材料属性
      - step6_weld_modeling(model, result)       仅焊缝建模
      - run_interactive()                        逐步确认模式
    """
    run_full_pipeline()

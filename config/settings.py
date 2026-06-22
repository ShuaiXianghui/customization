# 全局默认配置

# 叉车钢板标准厚度规格（mm），测量值自动取整到最近标准值
STANDARD_THICKNESS = [3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30]

# 默认材料
DEFAULT_MATERIAL = "Q235"

# 默认单元尺寸（mm）
DEFAULT_SHELL_SIZE = 5.0
DEFAULT_SOLID_SIZE = 8.0

# 网格类型
SHELL_ELEM_TYPE = "mixed"  # mixed / tria / quads
SOLID_ELEM_TYPE = "tetra"  # tetra / hexa

# 网格质量要求
MESH_QUALITY = {
  "jacobian_min": 0.6,
  "skew_max": 60,
  "aspect_ratio_max": 5.0,
  "min_angle_quad": 30,
  "max_angle_quad": 150,
  "min_angle_tria": 20,
  "max_angle_tria": 120
}

# 几何分类参数
CLASSIFY = {
  "thin_threshold": 0.08
}

# 中面抽取参数
MIDSURFACE = {
  "auto_extract": True,
  "target_thickness_min": 2.0,
  "target_thickness_max": 30.0,
  "cleanup_tolerance": 0.5
}

# 连接器参数
CONNECTOR = {
  "seam_gap_tolerance": 1.5,
  "seam_angle_tolerance": 5.0,
  "bolt_hole_diameter_range": [8, 30],
  "bolt_coaxial_tolerance": 0.5,
  "bolt_diameter_match_tolerance": 0.5,
  "spot_overlap_layers_min": 2,
  "spot_edge_offset": 8.0,
  "spot_spacing": 40.0
}

# 用户偏好文件路径
USER_PREFS_PATH = "config/user_prefs.json"

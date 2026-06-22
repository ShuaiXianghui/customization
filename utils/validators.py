import os


def file_exists(filepath: str) -> bool:
  return os.path.isfile(filepath)


def dir_exists(dirpath: str) -> bool:
  return os.path.isdir(dirpath)


def is_parasolid(filepath: str) -> bool:
  """判断是否为 Parasolid 文件"""
  ext = os.path.splitext(filepath)[1].lower()
  return ext in (".x_t", ".x_b", ".xmt_txt", ".xmt_bin")


def is_valid_thickness(value: float) -> bool:
  return 0.5 <= value <= 100.0


def is_valid_element_size(value: float) -> bool:
  return 0.1 <= value <= 200.0


def is_valid_material_code(code: str) -> bool:
  """校验材料代号格式"""
  valid_patterns = ["Q235", "Q355", "Q460", "QSTE", "ZG", "QT", "45"]
  return any(code.startswith(p) for p in valid_patterns)


def batch_validate_files(filepaths: list, file_type: str = "parasolid") -> tuple:
  """批量校验文件列表，返回(有效列表, 无效列表)"""
  valid = []
  invalid = []
  for fp in filepaths:
    if file_exists(fp):
      if file_type == "parasolid" and is_parasolid(fp):
        valid.append(fp)
      elif file_type != "parasolid":
        valid.append(fp)
      else:
        invalid.append((fp, "格式不符"))
    else:
      invalid.append((fp, "文件不存在"))
  return valid, invalid

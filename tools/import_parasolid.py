# -*- coding: utf-8 -*-
"""工具① Parasolid 几何导入"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import api_import_parasolid
from utils.logger import logger

print("=== ① Parasolid 几何导入 ===")

# ★★★ 修改以下列表为你的文件路径 ★★★
FILES = [
  # r"C:\Users\Shuai\Desktop\ceshi\waibi.x_t",
]

if not FILES:
  print("[提示] 请在脚本顶部 FILES 列表中添加 .x_t/.x_b 文件路径")
else:
  for fp in FILES:
    logger.info(f"导入: {os.path.basename(fp)}")
    api_import_parasolid(fp)
  print(f"完成: 导入 {len(FILES)} 个文件")

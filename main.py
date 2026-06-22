#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HyperWorks 2026 叉车结构件自动化建模工具
========================================

入口文件，支持两种模式:
  1. GUI 模式:  python main.py
  2. 命令行模式: python main.py --batch --input <folder> --output <result.fem>

适用部件: 叉车车架 / 门架 / 护顶架
"""

import argparse
import sys
import os

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_gui():
  from utils.hw_api import is_available
  from utils.logger import logger

  if not is_available():
    print("\n" + "!" * 60)
    print("  未检测到 HyperMesh 2026 连接")
    print("  请先打开 HyperMesh，然后选择以下方式之一：")
    print()
    print("  方式A: 在 HM 的 Python 窗口中执行：")
    print("    exec(open(r'D:/Working/OnGoing/customization/startup.py', encoding='utf-8').read())")
    print("    panel()")
    print()
    print("  方式B: 用 launch_gui.py 尝试自动连接：")
    print("    python launch_gui.py")
    print("!" * 60 + "\n")
    return

  from gui.main_window import MainWindow
  logger.info("已连接 HM，启动完整 GUI...")
  app = MainWindow()
  app.mainloop()


def run_batch(input_folder: str, output_file: str, shell_size: float = 5.0, solid_size: float = 8.0):
  from utils.logger import logger
  from modules.geometry_import import GeometryImporter
  from modules.batch_mesh import BatchMeshEngine
  from modules.property_assign import PropertyAssigner
  from modules.connectors import ConnectorEngine

  logger.info(f"批量模式: input={input_folder}, output={output_file}")

  # Step 1: 导入几何
  importer = GeometryImporter()
  importer.set_files([os.path.join(input_folder, f) for f in os.listdir(input_folder)
                      if f.endswith((".x_t", ".x_b"))])
  result = importer.run()
  if not result.success:
    logger.error("导入失败")
    return

  # Step 2: BatchMesher（清理+去特征+中面+壳网格，一步完成）
  # 替代原来的 classifier + midsurface + mesher
  bm = BatchMeshEngine()
  bm.set_params(elem_size=shell_size, param_mode="midmesh")
  bm_result = bm.run()
  if not bm_result.success:
    logger.error("BatchMesher 失败")
    return

  # Step 3: 属性赋参（简化版，对所有组件赋参）
  assigner = PropertyAssigner()
  # BatchMesher 模式下 comp_ids 直接从 API 获取
  from utils.hw_api import api_get_component_list
  comp_ids = api_get_component_list()
  assigner.run(comp_ids, [])

  # Step 4: 连接器检测与创建
  connector = ConnectorEngine()
  connector.detect_all()
  connector.set_all_selected(True)
  connector.create_selected()

  logger.info("批量模式执行完成")


def main():
  parser = argparse.ArgumentParser(
    description="HyperWorks 2026 叉车结构件自动化建模工具"
  )
  parser.add_argument("--batch", action="store_true", help="命令行批量模式（无GUI）")
  parser.add_argument("--input", type=str, help="输入文件夹路径（批量模式）")
  parser.add_argument("--output", type=str, default="output.fem", help="输出文件路径（批量模式）")
  parser.add_argument("--shell-size", type=float, default=5.0, help="壳单元尺寸 (mm)")
  parser.add_argument("--solid-size", type=float, default=8.0, help="体单元尺寸 (mm)")

  args = parser.parse_args()

  if args.batch:
    if not args.input:
      parser.error("批量模式需要 --input 参数")
    run_batch(args.input, args.output, args.shell_size, args.solid_size)
  else:
    run_gui()


if __name__ == "__main__":
  main()

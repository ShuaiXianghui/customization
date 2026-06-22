# -*- coding: utf-8 -*-
"""
外部 Python 启动 GUI 并连接到运行中的 HyperMesh
在系统 cmd/PowerShell 中: python launch_gui.py
"""
import sys
import os

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_DIR)

from utils.logger import logger

def try_connect():
  """尝试连接到 HyperMesh"""
  global hm_session

  # 方式1: 检查是否已有 hm 全局对象（在 HM Python 控制台运行的情况）
  try:
    import __main__
    if hasattr(__main__, "hm"):
      logger.info("检测到 HM 控制台中的全局 hm 对象，直接启动 GUI")
      return True
  except Exception:
    pass

  # 方式2: 尝试 hwx 包
  try:
    import hwx
    logger.info("通过 hwx 包连接到 HyperMesh")
    return True
  except ImportError:
    pass

  # 方式3: 尝试 COM 连接
  try:
    import win32com.client
    # HyperMesh COM ProgID (根据版本不同可能有差异)
    for progid in ["HyperMesh.Application", "Altair.HyperMesh.Application",
                   "hvw.hwApplication", "HW.HyperMesh"]:
      try:
        hm = win32com.client.Dispatch(progid)
        if hm:
          import __main__
          __main__.hm = hm
          logger.info(f"通过 COM 连接到 HyperMesh (ProgID: {progid})")
          return True
      except Exception:
        continue
  except ImportError:
    pass

  return False

if __name__ == "__main__":
  if try_connect():
    from gui.main_window import MainWindow
    app = MainWindow()
    logger.info("GUI 启动中...")
    app.mainloop()
  else:
    print("\n[WARN] 无法连接到 HyperMesh 会话")
    print("请先在 HyperMesh 的 Python 控制台中运行 startup.py")
    print("然后再回到这里尝试运行 GUI\n")
    input("按 Enter 退出...")

# -*- coding: utf-8 -*-
"""
叉车建模工具控制面板 (tkinter)
在 HM Python 控制台: exec(open(r"tools/panel.py", encoding="utf-8").read())
"""
import sys, os
try:
  sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  _TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
  sys.path.insert(0, os.getcwd())
  _TOOLS_DIR = os.path.join(os.getcwd(), "tools")

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from utils.hw_api import get_model_name

class ForkliftPanel(tk.Tk):
  def __init__(self):
    super().__init__()
    self.title(f"叉车建模工具 — {get_model_name()}")
    self.geometry("320x420")
    self.resizable(False, False)

    self._build_ui()

  def _run_tool(self, name):
    script = os.path.join(_TOOLS_DIR, name)
    try:
      exec(open(script, encoding="utf-8").read())
    except Exception as e:
      messagebox.showerror("错误", str(e))

  def _build_ui(self):
    # 标题
    ttk.Label(self, text="叉车结构件自动化建模", font=("", 14, "bold")).pack(pady=(15, 5))
    ttk.Label(self, text="适用: 车架 | 护顶架", foreground="gray").pack(pady=(0, 15))

    # 按钮区
    ttk.Separator(self).pack(fill=tk.X, padx=20)
    ttk.Label(self, text="选择工具脚本", font=("", 10)).pack(pady=(10, 5))

    buttons = [
      ("📂 ① 几何导入",        "import_parasolid.py"),
      ("📐 ② 中面抽取",        "extract_midsurface.py"),
      ("🏷 ③ 属性赋参",        "assign_property.py"),
      ("🔲 ④ 网格划分",        "auto_mesh.py"),
      ("🔗 ⑤ 连接器创建",      "create_connectors.py"),
    ]

    for label, script in buttons:
      btn = ttk.Button(
        self, text=label,
        command=lambda s=script: self._run_tool(s),
        width=28
      )
      btn.pack(pady=3, padx=20)

    ttk.Separator(self).pack(fill=tk.X, padx=20, pady=(10, 5))

    ttk.Button(
      self, text="▶ 一键全流程",
      command=lambda: self._run_tool("run_all.py"),
      width=28
    ).pack(pady=3)

    ttk.Button(
      self, text="🧹 清理模型",
      command=lambda: self._run_tool("clear_all.py"),
      width=28
    ).pack(pady=3)

    ttk.Separator(self).pack(fill=tk.X, padx=20, pady=(10, 5))

    ttk.Label(self, text="使用说明", font=("", 9, "bold")).pack(pady=(5, 2))
    ttk.Label(self, text="执行前先编辑对应脚本顶部的 ★★★ 参数区",
              foreground="gray").pack()
    ttk.Label(self, text="设置文件路径 / 组件ID / 材料厚度等",
              foreground="gray").pack()

    # 底部状态
    ttk.Separator(self).pack(fill=tk.X, padx=20, pady=(10, 5))
    ttk.Label(self, text=f"已连接: {get_model_name()}", foreground="green").pack(pady=(0, 10))


if __name__ == "__main__":
  app = ForkliftPanel()
  app.mainloop()

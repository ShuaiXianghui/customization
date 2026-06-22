"""几何分类面板"""
import tkinter as tk
from tkinter import ttk

from gui.widgets import LabeledEntry
from modules.geometry_classify import GeometryClassifier
from utils.logger import logger


class ClassifyPanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._classifier = GeometryClassifier(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="几何分类（薄壁件 / 中厚件 / 实体件）", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    opts_frame = ttk.LabelFrame(self, text="分类参数")
    opts_frame.pack(fill=tk.X, pady=(0, 10))

    self.threshold_entry = LabeledEntry(
      opts_frame, "薄壁阈值(mm)", str(10.0), width=8
    )
    self.threshold_entry.pack(side=tk.LEFT, padx=5, pady=5)

    ttk.Label(opts_frame, text="(≤阈值为薄壁件_shell, >阈值为实体_solid)").pack(
      side=tk.LEFT, padx=5
    )

    self.result_tree = ttk.Treeview(
      self, columns=("id", "name", "type", "ratio"), show="headings", height=10
    )
    self.result_tree.heading("id", text="ID")
    self.result_tree.heading("name", text="组件名")
    self.result_tree.heading("type", text="类型")
    self.result_tree.heading("ratio", text="厚度")
    self.result_tree.column("ratio", width=100)
    self.result_tree.column("id", width=60)
    self.result_tree.column("name", width=160)
    self.result_tree.column("type", width=80)
    self.result_tree.column("ratio", width=100)
    self.result_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    btn_frame = ttk.Frame(self)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="执行分类", command=self._on_classify, width=12).pack(
      side=tk.RIGHT
    )

  def _on_classify(self):
    threshold = self.threshold_entry.get_float() or 0.08
    self._classifier.set_threshold(threshold)
    result = self._classifier.run()

    self.result_tree.delete(*self.result_tree.get_children())

    for p in result.thin_parts:
      self.result_tree.insert(
        "", tk.END, values=(p.comp_id, p.name, "薄壁件", f"{p.thickness:.1f}mm")
      )
    for p in result.mid_thick_parts:
      self.result_tree.insert(
        "", tk.END, values=(p.comp_id, p.name, "中厚件", f"{p.thickness:.1f}mm")
      )
    for p in result.thick_parts:
      self.result_tree.insert(
        "", tk.END, values=(p.comp_id, p.name, "实体件", f"{p.thickness:.1f}mm")
      )
    for p in result.small_parts:
      self.result_tree.insert(
        "", tk.END, values=(p.comp_id, p.name, "微小件", "-")
      )

  def get_classifier(self) -> GeometryClassifier:
    return self._classifier

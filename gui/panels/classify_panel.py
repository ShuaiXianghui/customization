"""几何分类面板"""
import tkinter as tk
from tkinter import ttk

from gui.widgets import LabeledEntry
from modules.geometry_classify import GeometryClassifier
from config.settings import CLASSIFY
from utils.logger import logger


class ClassifyPanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._classifier = GeometryClassifier(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="几何分类（薄壁件 / 实体件）", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    opts_frame = ttk.LabelFrame(self, text="分类参数")
    opts_frame.pack(fill=tk.X, pady=(0, 10))

    self.threshold_entry = LabeledEntry(
      opts_frame, "薄壁阈值", str(CLASSIFY["thin_threshold"]), width=8
    )
    self.threshold_entry.pack(side=tk.LEFT, padx=5, pady=5)

    ttk.Label(opts_frame, text="(体量比 < 阈值为薄壁件, 默认 0.08)").pack(
      side=tk.LEFT, padx=5
    )

    self.result_tree = ttk.Treeview(
      self, columns=("id", "name", "type", "ratio"), show="headings", height=10
    )
    self.result_tree.heading("id", text="ID")
    self.result_tree.heading("name", text="组件名")
    self.result_tree.heading("type", text="类型")
    self.result_tree.heading("ratio", text="体量比")
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
    threshold = self.threshold_entry.get_float() or CLASSIFY["thin_threshold"]
    self._classifier.set_threshold(threshold)
    result = self._classifier.run()

    self.result_tree.delete(*self.result_tree.get_children())

    for p in result.thin_parts:
      self.result_tree.insert(
        "", tk.END, values=(p.comp_id, p.name, "薄壁件", f"{p.ratio:.6f}")
      )
    for p in result.solid_parts:
      self.result_tree.insert(
        "", tk.END, values=(p.comp_id, p.name, "实体件", f"{p.ratio:.6f}")
      )
    for p in result.unknown_parts:
      self.result_tree.insert(
        "", tk.END, values=(p, "?", "未知", "-")
      )

  def get_classifier(self) -> GeometryClassifier:
    return self._classifier

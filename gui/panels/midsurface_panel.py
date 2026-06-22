"""中面抽取面板"""
import tkinter as tk
from tkinter import ttk

from modules.midsurface import MidsurfaceExtractor
from utils.logger import logger


class MidsurfacePanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._extractor = MidsurfaceExtractor(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="中面抽取（薄壁件）", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    info_frame = ttk.Frame(self)
    info_frame.pack(fill=tk.X, pady=(0, 10))
    self.info_label = ttk.Label(info_frame, text="待抽取: 0 个薄壁件")
    self.info_label.pack(anchor=tk.W)

    self.result_tree = ttk.Treeview(
      self,
      columns=("comp", "status", "thickness"),
      show="headings",
      height=10,
    )
    self.result_tree.heading("comp", text="组件ID")
    self.result_tree.heading("status", text="状态")
    self.result_tree.heading("thickness", text="厚度 (mm)")
    self.result_tree.column("comp", width=120)
    self.result_tree.column("status", width=100)
    self.result_tree.column("thickness", width=120)
    self.result_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    btn_frame = ttk.Frame(self)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="执行抽取", command=self._on_extract, width=12).pack(
      side=tk.RIGHT
    )

  def set_thin_parts(self, thin_parts: list):
    self._thin_parts = thin_parts
    self.info_label.config(text=f"待抽取: {len(thin_parts)} 个薄壁件")

  def _on_extract(self):
    if not hasattr(self, "_thin_parts") or not self._thin_parts:
      logger.warn("请先执行几何分类")
      return

    ids = [p.comp_id for p in self._thin_parts]
    result = self._extractor.run(ids)

    self.result_tree.delete(*self.result_tree.get_children())
    for cid in result.extracted_parts:
      thk = result.thickness_map.get(cid, 0)
      self.result_tree.insert("", tk.END, values=(cid, "成功", f"{thk:.1f}"))
    for cid in result.failed_parts:
      self.result_tree.insert("", tk.END, values=(cid, "失败", "-"))

  def get_extractor(self) -> MidsurfaceExtractor:
    return self._extractor

"""属性赋参面板"""
import tkinter as tk
from tkinter import ttk

from gui.widgets import LabeledCombo
from modules.property_assign import PropertyAssigner
from utils.logger import logger


class PropertyPanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._assigner = PropertyAssigner(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="厚度识别与材料赋参", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    opts_frame = ttk.LabelFrame(self, text="默认属性")
    opts_frame.pack(fill=tk.X, pady=(0, 10))

    self.mat_combo = LabeledCombo(
      opts_frame,
      "默认材料",
      values=self._assigner.get_material_list(),
      default="Q235",
    )
    self.mat_combo.pack(side=tk.LEFT, padx=5, pady=5)

    info_frame = ttk.Frame(self)
    info_frame.pack(fill=tk.X, pady=(0, 10))
    self.info_label = ttk.Label(info_frame, text="待赋值: 0 个薄壁件 + 0 个实体件")
    self.info_label.pack(anchor=tk.W)

    self.result_tree = ttk.Treeview(
      self,
      columns=("name", "measured", "standard", "material", "card"),
      show="headings",
      height=10,
    )
    self.result_tree.heading("name", text="组件名")
    self.result_tree.heading("measured", text="测量厚度")
    self.result_tree.heading("standard", text="标准厚度")
    self.result_tree.heading("material", text="材料")
    self.result_tree.heading("card", text="卡片")
    self.result_tree.column("name", width=140)
    self.result_tree.column("measured", width=80)
    self.result_tree.column("standard", width=80)
    self.result_tree.column("material", width=80)
    self.result_tree.column("card", width=80)
    self.result_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    btn_frame = ttk.Frame(self)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="执行赋值", command=self._on_assign, width=12).pack(
      side=tk.RIGHT
    )

  def set_parts(self, thin_parts: list, solid_parts: list):
    self._thin_parts = thin_parts
    self._solid_parts = solid_parts
    self.info_label.config(
      text=f"待赋值: {len(thin_parts)} 个薄壁件 + {len(solid_parts)} 个实体件"
    )

  def set_thickness_map(self, thickness_map: dict):
    self._thickness_map = thickness_map

  def _on_assign(self):
    if not hasattr(self, "_thin_parts"):
      logger.warn("请先执行几何分类")
      return

    default_mat = self.mat_combo.get()
    self._assigner.set_default_material(default_mat)

    result = self._assigner.run(
      self._thin_parts,
      self._solid_parts,
      getattr(self, "_thickness_map", None),
    )

    self.result_tree.delete(*self.result_tree.get_children())
    for r in result.records:
      self.result_tree.insert(
        "",
        tk.END,
        values=(
          r.comp_name,
          f"{r.measured_thickness:.1f}",
          f"{r.standard_thickness:.0f}",
          r.material,
          r.mesh_type,
        ),
      )

  def get_assigner(self) -> PropertyAssigner:
    return self._assigner

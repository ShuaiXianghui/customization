"""网格划分面板"""
import tkinter as tk
from tkinter import ttk

from gui.widgets import LabeledEntry, LabeledCombo
from modules.meshing import MeshingEngine
from config.settings import DEFAULT_SHELL_SIZE, DEFAULT_SOLID_SIZE
from utils.logger import logger


class MeshingPanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._engine = MeshingEngine(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="参数化网格划分", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    opts_frame = ttk.LabelFrame(self, text="网格参数")
    opts_frame.pack(fill=tk.X, pady=(0, 10))

    self.shell_size_entry = LabeledEntry(
      opts_frame, "壳单元尺寸", str(DEFAULT_SHELL_SIZE), width=8
    )
    self.shell_size_entry.pack(side=tk.LEFT, padx=5, pady=5)

    self.solid_size_entry = LabeledEntry(
      opts_frame, "体单元尺寸", str(DEFAULT_SOLID_SIZE), width=8
    )
    self.solid_size_entry.pack(side=tk.LEFT, padx=5, pady=5)

    self.shell_type_combo = LabeledCombo(
      opts_frame,
      "壳单元类型",
      values=["mixed", "quads", "tria"],
      default="mixed",
    )
    self.shell_type_combo.pack(side=tk.LEFT, padx=5, pady=5)

    info_frame = ttk.Frame(self)
    info_frame.pack(fill=tk.X, pady=(0, 10))
    self.info_label = ttk.Label(info_frame, text="待划分: 0 个薄壁件 + 0 个实体件")
    self.info_label.pack(anchor=tk.W)

    self.result_tree = ttk.Treeview(
      self,
      columns=("name", "type", "size", "status"),
      show="headings",
      height=10,
    )
    self.result_tree.heading("name", text="组件")
    self.result_tree.heading("type", text="类型")
    self.result_tree.heading("size", text="尺寸(mm)")
    self.result_tree.heading("status", text="状态")
    self.result_tree.column("name", width=160)
    self.result_tree.column("type", width=80)
    self.result_tree.column("size", width=80)
    self.result_tree.column("status", width=80)
    self.result_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    btn_frame = ttk.Frame(self)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="执行划分", command=self._on_mesh, width=12).pack(
      side=tk.RIGHT
    )

  def set_parts(self, thin_parts: list, solid_parts: list):
    self._thin_parts = thin_parts
    self._solid_parts = solid_parts
    self.info_label.config(
      text=f"待划分: {len(thin_parts)} 个薄壁件 + {len(solid_parts)} 个实体件"
    )

  def _on_mesh(self):
    if not hasattr(self, "_thin_parts"):
      logger.warn("请先执行几何分类")
      return

    self._engine.set_shell_size(self.shell_size_entry.get_float() or DEFAULT_SHELL_SIZE)
    self._engine.set_solid_size(self.solid_size_entry.get_float() or DEFAULT_SOLID_SIZE)
    self._engine.shell_elem_type = self.shell_type_combo.get()

    result = self._engine.run(self._thin_parts, self._solid_parts)

    self.result_tree.delete(*self.result_tree.get_children())
    for r in result.records:
      status = "完成" if r.quality_pass else "失败"
      self.result_tree.insert(
        "", tk.END, values=(r.comp_name, r.mesh_type, str(r.elem_size), status)
      )

  def get_engine(self) -> MeshingEngine:
    return self._engine

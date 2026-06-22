"""几何导入面板"""
import tkinter as tk
from tkinter import ttk

from gui.widgets import FileListBox, LabeledEntry
from modules.geometry_import import GeometryImporter
from utils.logger import logger


class ImportPanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._importer = GeometryImporter(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="Parasolid 几何导入", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    ttk.Label(self, text="选择 Parasolid 文件 (*.x_t, *.x_b)").pack(anchor=tk.W)
    self.file_list = FileListBox(
      self,
      filetypes=[("Parasolid", "*.x_t;*.x_b"), ("所有文件", "*.*")],
    )
    self.file_list.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    opts_frame = ttk.LabelFrame(self, text="导入选项")
    opts_frame.pack(fill=tk.X, pady=(0, 10))

    self.scale_entry = LabeledEntry(opts_frame, "缩放比例", "1.0", width=8)
    self.scale_entry.pack(side=tk.LEFT, padx=5, pady=5)

    btn_frame = ttk.Frame(self)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="执行导入", command=self._on_import, width=12).pack(
      side=tk.RIGHT
    )

  def _on_import(self):
    files = self.file_list.get_files()
    if not files:
      logger.warn("请先添加 Parasolid 文件")
      return

    scale = self.scale_entry.get_float() or 1.0
    self._importer.set_files(files)
    self._importer.set_scale(scale)
    self._importer.run()

  def get_importer(self) -> GeometryImporter:
    return self._importer

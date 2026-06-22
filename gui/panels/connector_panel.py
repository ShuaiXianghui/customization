"""连接器面板 — 识别/预览/确认/创建"""
import tkinter as tk
from tkinter import ttk

from modules.connectors import ConnectorEngine, ConnectorType
from utils.logger import logger


class ConnectorPanel(ttk.Frame):

  def __init__(self, parent, session=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._session = session
    self._engine = ConnectorEngine(session)
    self._build_ui()

  def _build_ui(self):
    ttk.Label(
      self, text="连接器自动化（缝焊 / 塞焊 / 螺栓）", font=("", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 10))

    toolbar = ttk.Frame(self)
    toolbar.pack(fill=tk.X, pady=(0, 5))

    ttk.Button(toolbar, text="自动识别", command=self._on_detect, width=10).pack(
      side=tk.LEFT, padx=(0, 5)
    )
    ttk.Button(toolbar, text="全选", command=self._on_select_all, width=6).pack(
      side=tk.LEFT, padx=(0, 5)
    )
    ttk.Button(toolbar, text="全不选", command=self._on_deselect_all, width=6).pack(
      side=tk.LEFT, padx=(0, 5)
    )
    ttk.Button(toolbar, text="创建已选", command=self._on_create, width=10).pack(
      side=tk.LEFT
    )

    summary_frame = ttk.Frame(self)
    summary_frame.pack(fill=tk.X, pady=(5, 5))
    self.summary_label = ttk.Label(summary_frame, text="识别结果: 尚未识别")
    self.summary_label.pack(anchor=tk.W)

    self.tree = ttk.Treeview(
      self,
      columns=("id", "type", "source", "target", "selected"),
      show="headings",
      height=12,
    )
    self.tree.heading("id", text="ID")
    self.tree.heading("type", text="类型")
    self.tree.heading("source", text="源组件")
    self.tree.heading("target", text="目标组件")
    self.tree.heading("selected", text="勾选")
    self.tree.column("id", width=50)
    self.tree.column("type", width=80)
    self.tree.column("source", width=150)
    self.tree.column("target", width=150)
    self.tree.column("selected", width=60)
    self.tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    self.tree.bind("<Double-1>", self._on_toggle_selection)

    btn_frame = ttk.Frame(self)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="创建已选", command=self._on_create, width=12).pack(
      side=tk.RIGHT
    )

  def _on_detect(self):
    candidates = self._engine.detect_all()
    self._refresh_tree()

    summary = {"缝焊": 0, "焊点": 0, "螺栓": 0}
    for c in candidates:
      if c.conn_type == ConnectorType.SEAM_WELD:
        summary["缝焊"] += 1
      elif c.conn_type == ConnectorType.SPOT_WELD:
        summary["焊点"] += 1
      elif c.conn_type == ConnectorType.BOLT:
        summary["螺栓"] += 1
    self.summary_label.config(
      text=f"识别结果: 缝焊 {summary['缝焊']} | 焊点 {summary['焊点']} | 螺栓 {summary['螺栓']} | 共 {len(candidates)} 处"
    )

  def _refresh_tree(self):
    self.tree.delete(*self.tree.get_children())
    for c in self._engine.candidates:
      type_name = {
        ConnectorType.SEAM_WELD: "缝焊",
        ConnectorType.SPOT_WELD: "焊点",
        ConnectorType.BOLT: "螺栓",
        ConnectorType.ADHESIVE: "胶粘",
      }.get(c.conn_type, "未知")
      self.tree.insert(
        "",
        tk.END,
        iid=str(c.id),
        values=(c.id, type_name, c.source_comp, c.target_comp, "✓" if c.selected else "✗"),
      )

  def _on_toggle_selection(self, event):
    item = self.tree.selection()[0]
    if item:
      cid = int(item)
      self._engine.set_selection(
        [cid], not self._engine.candidates[cid].selected
      )
      self._refresh_tree()

  def _on_select_all(self):
    self._engine.set_all_selected(True)
    self._refresh_tree()

  def _on_deselect_all(self):
    self._engine.set_all_selected(False)
    self._refresh_tree()

  def _on_create(self):
    if not self._engine.candidates:
      logger.warn("请先识别连接器候选")
      return
    selected = [c for c in self._engine.candidates if c.selected]
    if not selected:
      logger.warn("没有勾选的连接器")
      return
    self._engine.create_selected()

  def get_engine(self) -> ConnectorEngine:
    return self._engine

"""
HyperWorks 自动化建模工具 v1.0 — 主界面
叉车车架/门架/护顶架专用
"""
import tkinter as tk
from tkinter import ttk, messagebox

from gui.widgets import LogPanel, ProgressFrame
from gui.panels.import_panel import ImportPanel
from gui.panels.classify_panel import ClassifyPanel
from gui.panels.midsurface_panel import MidsurfacePanel
from gui.panels.property_panel import PropertyPanel
from gui.panels.meshing_panel import MeshingPanel
from gui.panels.connector_panel import ConnectorPanel
from utils.logger import logger


STEPS = [
  ("① 几何导入", "import"),
  ("② 几何分类", "classify"),
  ("③ 中面抽取", "midsurface"),
  ("④ 属性赋参", "property"),
  ("⑤ 网格划分", "meshing"),
  ("⑥ 连接器", "connector"),
]


class MainWindow(tk.Tk):

  def __init__(self, session=None):
    super().__init__()
    self._session = session
    self._current_step = "import"
    self._panels: dict = {}

    self.title("HyperWorks 自动化建模工具 — 叉车专用 v1.0")
    self.geometry("1100x700")
    self.minsize(900, 600)

    self._build_layout()
    self._show_step("import")

    logger.set_gui_callback(self._log_panel.append)

  def _build_layout(self):
    # 顶部标题栏
    header = ttk.Frame(self)
    header.pack(fill=tk.X, padx=10, pady=(10, 5))
    ttk.Label(
      header,
      text="HyperWorks 2026 叉车结构件自动化建模工具",
      font=("", 13, "bold"),
    ).pack(side=tk.LEFT)
    ttk.Label(
      header,
      text="适用: 车架 | 门架 | 护顶架",
      foreground="gray",
    ).pack(side=tk.RIGHT)

    # 主区域: 左侧步骤 + 右侧面板
    main_frame = ttk.Frame(self)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

    # 左侧步骤栏
    sidebar = ttk.Frame(main_frame, width=140)
    sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
    sidebar.pack_propagate(False)

    ttk.Label(sidebar, text="建模流程", font=("", 10, "bold")).pack(
      anchor=tk.W, pady=(0, 8)
    )

    self._step_indicators: dict = {}
    for label, key in STEPS:
      indicator = ttk.Label(
        sidebar,
        text=label,
        font=("", 10),
        padding=(8, 6),
        cursor="hand2",
        foreground="gray",
      )
      indicator.pack(fill=tk.X, pady=2)
      indicator.bind("<Button-1>", lambda e, k=key: self._show_step(k))
      self._step_indicators[key] = indicator

    ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    # 一键全流程按钮
    self.full_run_btn = ttk.Button(
      sidebar,
      text="▶ 一键全流程",
      command=self._on_full_run,
    )
    self.full_run_btn.pack(fill=tk.X, pady=(0, 5))

    ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

    # 右侧面板区
    right_frame = ttk.Frame(main_frame)
    right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    self._panel_container = ttk.Frame(right_frame)
    self._panel_container.pack(fill=tk.BOTH, expand=True)

    self._import_panel = ImportPanel(self._panel_container, self._session)
    self._classify_panel = ClassifyPanel(self._panel_container, self._session)
    self._midsurface_panel = MidsurfacePanel(self._panel_container, self._session)
    self._property_panel = PropertyPanel(self._panel_container, self._session)
    self._meshing_panel = MeshingPanel(self._panel_container, self._session)
    self._connector_panel = ConnectorPanel(self._panel_container, self._session)

    self._panels = {
      "import": self._import_panel,
      "classify": self._classify_panel,
      "midsurface": self._midsurface_panel,
      "property": self._property_panel,
      "meshing": self._meshing_panel,
      "connector": self._connector_panel,
    }

    # 底部日志区
    bottom_frame = ttk.Frame(self)
    bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    self._progress = ProgressFrame(bottom_frame)
    self._progress.pack(fill=tk.X, pady=(0, 5))

    self._log_panel = LogPanel(bottom_frame)
    self._log_panel.pack(fill=tk.BOTH, expand=True)

  def _show_step(self, step_key: str):
    # 隐藏所有面板
    for panel in self._panels.values():
      panel.pack_forget()

    self._panels[step_key].pack(fill=tk.BOTH, expand=True)
    self._current_step = step_key

    # 更新步骤指示器
    for key, indicator in self._step_indicators.items():
      if key == step_key:
        indicator.configure(foreground="#0066cc")
      elif self._is_step_completed(key):
        indicator.configure(foreground="#00aa00")
      else:
        indicator.configure(foreground="gray")

  def _is_step_completed(self, step_key: str) -> bool:
    if step_key == "import":
      result = self._import_panel.get_importer().result
      return result is not None and result.success
    elif step_key == "classify":
      result = self._classify_panel.get_classifier().result
      return result is not None and result.success
    elif step_key == "midsurface":
      result = self._midsurface_panel.get_extractor().result
      return result is not None and result.success
    elif step_key == "property":
      result = self._property_panel.get_assigner().result
      return result is not None and result.success
    elif step_key == "meshing":
      result = self._meshing_panel.get_engine().result
      return result is not None and result.success
    elif step_key == "connector":
      result = self._connector_panel.get_engine().result
      return result is not None and result.success
    return False

  def _on_full_run(self):
    """一键全流程执行"""
    if not messagebox.askyesno(
      "确认",
      "即将执行一键全流程:\n\n"
      "① 几何导入 → ② 分类 → ③ 中面抽取 → ④ 属性赋参 → ⑤ 网格划分 → ⑥ 连接器识别\n\n"
      "这个过程可能需要几分钟，确认继续？",
    ):
      return

    self._progress.set(0, "开始全流程...")
    self.update()

    # Step 1: 导入
    self._progress.set(10, "① 几何导入...")
    self._show_step("import")
    self._import_panel._on_import()
    self.update()

    # Step 2: 分类
    self._progress.set(25, "② 几何分类...")
    self._show_step("classify")
    self._classify_panel._on_classify()
    self.update()

    classifier = self._classify_panel.get_classifier()
    if not classifier.result or not classifier.result.success:
      logger.error("几何分类失败，流程终止")
      messagebox.showerror("错误", "几何分类失败")
      return

    thin = classifier.result.thin_parts
    solid = classifier.result.thick_parts
    mid_thick = classifier.result.mid_thick_parts

    # Step 3: 中面抽取
    self._progress.set(40, "③ 中面抽取...")
    self._show_step("midsurface")
    self._midsurface_panel.set_thin_parts(thin)
    self._midsurface_panel._on_extract()
    self.update()

    extractor = self._midsurface_panel.get_extractor()
    thickness_map = extractor.result.thickness_map if extractor.result else {}

    # Step 4: 属性赋参
    self._progress.set(55, "④ 属性识别与材料赋参...")
    self._show_step("property")
    self._property_panel.set_parts(thin, solid, mid_thick)
    self._property_panel.set_thickness_map(thickness_map)
    self._property_panel._on_assign()
    self.update()

    # Step 5: 网格划分
    self._progress.set(75, "⑤ 网格划分...")
    self._show_step("meshing")
    self._meshing_panel.set_parts(thin, solid, mid_thick)
    self._meshing_panel._on_mesh()
    self.update()

    # Step 6: 连接器识别
    self._progress.set(90, "⑥ 连接器识别...")
    self._show_step("connector")
    self._connector_panel._on_detect()
    self.update()

    self._progress.set(100, "全流程完成！请在连接器面板确认连接并创建")
    logger.info("========= 一键全流程完成 =========")
    messagebox.showinfo("完成", "全流程执行完成！\n请检查连接器识别结果，确认后点击\"创建已选\"。")

  def get_session(self):
    return self._session

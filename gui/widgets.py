"""通用 GUI 控件"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class LabeledEntry(ttk.Frame):
  """带标签的输入框"""

  def __init__(self, parent, label, default="", width=15, **kwargs):
    super().__init__(parent, **kwargs)
    self.var = tk.StringVar(value=str(default))
    ttk.Label(self, text=label, width=12).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Entry(self, textvariable=self.var, width=width).pack(side=tk.LEFT)

  def get(self) -> str:
    return self.var.get()

  def get_float(self) -> float:
    try:
      return float(self.var.get())
    except ValueError:
      return 0.0

  def get_int(self) -> int:
    try:
      return int(self.var.get())
    except ValueError:
      return 0

  def set(self, value):
    self.var.set(str(value))


class LabeledCombo(ttk.Frame):
  """带标签的下拉框"""

  def __init__(self, parent, label, values=None, default=None, width=18, **kwargs):
    super().__init__(parent, **kwargs)
    self.var = tk.StringVar()
    ttk.Label(self, text=label, width=12).pack(side=tk.LEFT, padx=(0, 5))
    self.combo = ttk.Combobox(
      self, textvariable=self.var, values=values or [], state="readonly", width=width
    )
    self.combo.pack(side=tk.LEFT)
    if default and default in (values or []):
      self.var.set(default)
    elif values:
      self.var.set(values[0])

  def get(self) -> str:
    return self.var.get()


class FileSelector(ttk.Frame):
  """文件选择器"""

  def __init__(self, parent, label, filetypes=None, **kwargs):
    super().__init__(parent, **kwargs)
    self.var = tk.StringVar()
    self._filetypes = filetypes or [("所有文件", "*.*")]
    ttk.Label(self, text=label, width=12).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Entry(self, textvariable=self.var, width=35).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(self, text="浏览...", command=self._browse, width=6).pack(side=tk.LEFT)

  def _browse(self):
    path = filedialog.askopenfilename(filetypes=self._filetypes)
    if path:
      self.var.set(path)

  def get(self) -> str:
    return self.var.get()


class FolderSelector(ttk.Frame):
  """文件夹选择器"""

  def __init__(self, parent, label, **kwargs):
    super().__init__(parent, **kwargs)
    self.var = tk.StringVar()
    ttk.Label(self, text=label, width=12).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Entry(self, textvariable=self.var, width=35).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(self, text="浏览...", command=self._browse, width=6).pack(side=tk.LEFT)

  def _browse(self):
    path = filedialog.askdirectory()
    if path:
      self.var.set(path)

  def get(self) -> str:
    return self.var.get()


class FileListBox(ttk.Frame):
  """文件列表管理器"""

  def __init__(self, parent, filetypes=None, **kwargs):
    super().__init__(parent, **kwargs)
    self._filetypes = filetypes or [("Parasolid", "*.x_t;*.x_b")]
    self._files: list = []

    toolbar = ttk.Frame(self)
    toolbar.pack(fill=tk.X, pady=(0, 3))
    ttk.Button(toolbar, text="添加文件", command=self._add_files, width=10).pack(
      side=tk.LEFT, padx=(0, 5)
    )
    ttk.Button(toolbar, text="添加文件夹", command=self._add_folder, width=10).pack(
      side=tk.LEFT, padx=(0, 5)
    )
    ttk.Button(toolbar, text="移除选中", command=self._remove_selected, width=10).pack(
      side=tk.LEFT, padx=(0, 5)
    )
    ttk.Button(toolbar, text="清空", command=self._clear, width=6).pack(side=tk.LEFT)

    list_frame = ttk.Frame(self)
    list_frame.pack(fill=tk.BOTH, expand=True)

    self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=8)
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
    self.listbox.configure(yscrollcommand=scrollbar.set)
    self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

  def _add_files(self):
    paths = filedialog.askopenfilenames(filetypes=self._filetypes)
    for p in paths:
      if p not in self._files:
        self._files.append(p)
        self.listbox.insert(tk.END, p)

  def _add_folder(self):
    folder = filedialog.askdirectory()
    if not folder:
      return
    import os

    for f in os.listdir(folder):
      fp = os.path.join(folder, f)
      ext = os.path.splitext(f)[1].lower()
      if ext in (".x_t", ".x_b") and os.path.isfile(fp):
        if fp not in self._files:
          self._files.append(fp)
          self.listbox.insert(tk.END, fp)

  def _remove_selected(self):
    selected = self.listbox.curselection()
    for idx in reversed(selected):
      fp = self.listbox.get(idx)
      self._files.remove(fp)
      self.listbox.delete(idx)

  def _clear(self):
    self._files.clear()
    self.listbox.delete(0, tk.END)

  def get_files(self) -> list:
    return self._files.copy()


class LogPanel(ttk.Frame):
  """日志输出面板"""

  def __init__(self, parent, **kwargs):
    super().__init__(parent, **kwargs)
    self.text = tk.Text(self, height=10, wrap=tk.WORD, state=tk.DISABLED)
    scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
    self.text.configure(yscrollcommand=scrollbar.set)
    self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    self.text.tag_configure("error", foreground="red")
    self.text.tag_configure("warning", foreground="orange")
    self.text.tag_configure("success", foreground="green")

  def append(self, message: str):
    self.text.configure(state=tk.NORMAL)
    tag = None
    if "[ERROR]" in message:
      tag = "error"
    elif "[WARNING]" in message:
      tag = "warning"
    if tag:
      self.text.insert(tk.END, message + "\n", tag)
    else:
      self.text.insert(tk.END, message + "\n")
    self.text.see(tk.END)
    self.text.configure(state=tk.DISABLED)

  def clear(self):
    self.text.configure(state=tk.NORMAL)
    self.text.delete(1.0, tk.END)
    self.text.configure(state=tk.DISABLED)


class ProgressFrame(ttk.Frame):
  """进度条"""

  def __init__(self, parent, **kwargs):
    super().__init__(parent, **kwargs)
    self.progress = ttk.Progressbar(self, mode="determinate")
    self.progress.pack(fill=tk.X, pady=(0, 3))
    self.label = ttk.Label(self, text="就绪")
    self.label.pack()

  def set(self, value: float, text: str = ""):
    self.progress["value"] = min(value, 100)
    if text:
      self.label.config(text=text)

  def set_total_steps(self, total: int):
    self.progress["maximum"] = total

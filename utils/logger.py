import logging
import sys
from datetime import datetime
from typing import Callable, Optional


class Logger:
  """统一日志模块，支持控制台输出和GUI回调"""

  _instance = None

  def __init__(self):
    self.logger = logging.getLogger("HWAutomation")
    self.logger.setLevel(logging.DEBUG)

    if not self.logger.handlers:
      fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
      )
      ch = logging.StreamHandler(sys.stdout)
      ch.setFormatter(fmt)
      self.logger.addHandler(ch)

    self._gui_callback: Optional[Callable] = None

  @classmethod
  def get_instance(cls):
    if cls._instance is None:
      cls._instance = cls()
    return cls._instance

  def set_gui_callback(self, callback: Callable):
    self._gui_callback = callback

  def _log(self, level: str, msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    text = f"{timestamp} [{level}] {msg}"
    getattr(self.logger, level.lower())(msg)
    if self._gui_callback:
      self._gui_callback(text)

  def info(self, msg: str):
    self._log("INFO", msg)

  def warn(self, msg: str):
    self._log("WARNING", msg)

  def error(self, msg: str):
    self._log("ERROR", msg)

  def debug(self, msg: str):
    self._log("DEBUG", msg)


logger = Logger.get_instance()

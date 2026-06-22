# -*- coding: utf-8 -*-
"""清理模型"""
import sys, os
try: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError: sys.path.insert(0, os.getcwd())

from utils.hw_api import api_clear_all
api_clear_all()
print("模型已清理")

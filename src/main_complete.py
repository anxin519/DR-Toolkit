# -*- coding: utf-8 -*-
"""DICOM 运维工具 - 主程序入口"""
import sys
import os
import warnings
sys.path.insert(0, os.path.dirname(__file__))

# 过滤 pydicom 的非关键警告（源文件数据问题，不影响功能）
warnings.filterwarnings('ignore', category=UserWarning, module='pydicom')

import tkinter as tk
import ttkbootstrap as ttk_boot

from core.config_manager import ConfigManager
from core.logger import Logger
from core.forward_queue import ForwardQueue

from gui import tab_send, tab_receive, tab_worklist, tab_editor, tab_browser


class DicomToolApp:
    """主应用骨架：负责初始化共享状态，各 Tab 由 gui/ 下各模块构建"""

    def __init__(self, root: ttk_boot.Window):
        self.root = root
        self.root.title("DICOM 运维工具 v2.1")
        self.root.geometry("1280x820")

        # ── 共享服务 ──────────────────────────────────────────────────
        self.config = ConfigManager()
        self.logger = Logger.get_logger('app')
        self.forward_queue = ForwardQueue()

        # ── 共享状态 ──────────────────────────────────────────────────
        self.scp = None                  # DICOM SCP 实例
        self.worklist_scp = None         # Worklist SCP 实例
        self.current_dataset = None      # 编辑器当前打开的 dataset
        self.current_filepath = None     # 编辑器当前文件路径
        self.current_tk_image = None     # 防止 GC 回收图像
        self.file_paths: list = []       # 发送页文件列表
        self.browser_data: list = []     # 文件浏览器数据

        # ── Tkinter 变量 ──────────────────────────────────────────────
        self.auto_forward_var = tk.BooleanVar(value=False)
        self.wc_var = tk.IntVar(value=0)
        self.ww_var = tk.IntVar(value=400)

        self._build_ui()
        self.logger.info("应用启动")

    def _build_ui(self):
        self.notebook = ttk_boot.Notebook(self.root, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.notebook.add(tab_send.build(self),     text="📤 发送")
        self.notebook.add(tab_receive.build(self),  text="📥 接收")
        self.notebook.add(tab_worklist.build(self), text="📋 Worklist")
        self.notebook.add(tab_editor.build(self),   text="✏️ 编辑器")
        self.notebook.add(tab_browser.build(self),  text="📁 文件浏览")

        self.status = ttk_boot.Label(self.root, text="就绪", relief='sunken', anchor='w')
        self.status.pack(side='bottom', fill='x')

    def set_status(self, msg: str):
        self.root.after(0, lambda: self.status.config(text=msg))


def main():
    root = ttk_boot.Window(themename="cosmo")
    DicomToolApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

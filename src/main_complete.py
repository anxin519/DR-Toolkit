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

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.logger.info("应用启动")

    def _build_ui(self):
        self.notebook = ttk_boot.Notebook(self.root, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.tab_send = tab_send.build(self)
        self.tab_receive = tab_receive.build(self)
        self.tab_worklist = tab_worklist.build(self)
        self.tab_editor = tab_editor.build(self)
        self.tab_browser = tab_browser.build(self)

        self.notebook.add(self.tab_send,     text="📤 发送")
        self.notebook.add(self.tab_receive,  text="📥 接收")
        self.notebook.add(self.tab_worklist, text="📋 Worklist")
        self.notebook.add(self.tab_editor,   text="✏️ 编辑器")
        self.notebook.add(self.tab_browser,  text="📁 文件浏览")

        self.status = ttk_boot.Label(self.root, text="就绪", relief='sunken', anchor='w')
        self.status.pack(side='bottom', fill='x')

    def set_status(self, msg: str):
        self.root.after(0, lambda: self.status.config(text=msg))

    def _on_closing(self):
        """窗口关闭时清理后台服务，防止端口泄露"""
        try:
            if hasattr(self, 'tab_receive') and self.tab_receive.scp:
                self.tab_receive.scp.stop()
                self.logger.info("关闭时停止 DICOM SCP")
        except Exception:
            pass
        try:
            if hasattr(self, 'tab_worklist') and self.tab_worklist.worklist_scp:
                self.tab_worklist.worklist_scp.stop()
                self.logger.info("关闭时停止 Worklist SCP")
        except Exception:
            pass
        try:
            self.forward_queue.stop_worker()
            self.logger.info("关闭时停止转发队列")
        except Exception:
            pass
        self.logger.info("应用退出")
        self.root.destroy()


def main():
    root = ttk_boot.Window(themename="cosmo")
    DicomToolApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

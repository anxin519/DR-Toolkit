# -*- coding: utf-8 -*-
"""主窗口界面 - 完整版"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import ttkbootstrap as ttk_boot
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import sys
import os
import threading
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dicom.scu import DicomSCU
from dicom.scp import DicomSCP
from dicom.editor import DicomEditor
from dicom.anonymizer import DicomAnonymizer
from dicom.worklist import WorklistSCU
from dicom.worklist_scp import WorklistSCP
from dicom.echo import DicomEcho
from dicom.image_viewer import DicomImageViewer
from utils.uid_generator import modify_uids, batch_modify_uids
from utils.age_calculator import calculate_age
from utils.excel_exporter import ExcelExporter
from core.config_manager import ConfigManager
from core.logger import Logger
from core.forward_queue import ForwardQueue
import pydicom

class MainWindow:
    """主窗口"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM运维工具 v2.0")
        
        # 初始化管理器
        self.config = ConfigManager()
        self.logger = Logger.get_logger('app')
        self.forward_queue = ForwardQueue()
        
        # 加载窗口大小
        window_size = self.config.get('ui_settings.window_size', [1200, 800])
        self.root.geometry(f"{window_size[0]}x{window_size[1]}")
        
        # 状态变量
        self.scp = None
        self.worklist_scp = None
        self.current_dataset = None
        self.current_filepath = None
        self.current_pixel_array = None
        self.current_window_center = 0
        self.current_window_width = 0
        self.file_paths = []
        self.browser_data = []
        
        self.init_ui()
        self.logger.info("应用程序启动")
    
    def init_ui(self):
        """初始化界面"""
        # 创建标签页
        self.notebook = ttk_boot.Notebook(self.root, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 添加各个标签页
        self.notebook.add(self.create_send_tab(), text="📤 发送")
        self.notebook.add(self.create_receive_tab(), text="📥 接收")
        self.notebook.add(self.create_forward_tab(), text="🔄 转发")
        self.notebook.add(self.create_worklist_tab(), text="📋 Worklist")
        self.notebook.add(self.create_editor_tab(), text="✏️ 编辑器")
        self.notebook.add(self.create_browser_tab(), text="📁 文件浏览")
        self.notebook.add(self.create_config_tab(), text="⚙️ 配置")
        self.notebook.add(self.create_about_tab(), text="ℹ️ 关于")
        
        # 状态栏
        self.status_bar = ttk_boot.Label(self.root, text="就绪", relief='sunken', anchor='w')
        self.status_bar.pack(side='bottom', fill='x')
    
    def create_send_tab(self):
        """创建发送标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 远程配置组
        config_frame = ttk_boot.Labelframe(frame, text="远程DICOM节点配置", bootstyle="info", padding=10)
        config_frame.pack(fill='x', padx=10, pady=10)
        
        # 预设选择
        row0 = ttk_boot.Frame(config_frame)
        row0.pack(fill='x', pady=5)
        ttk_boot.Label(row0, text="预设节点:", width=10).pack(side='left', padx=5)
        self.send_preset = ttk_boot.Combobox(row0, width=20, state='readonly')
        self.send_preset.pack(side='left', padx=5)
        self.load_preset_list()
        self.send_preset.bind('<<ComboboxSelected>>', self.on_preset_selected)
        
        # 配置输入
        row1 = ttk_boot.Frame(config_frame)
        row1.pack(fill='x', pady=5)
        
        ttk_boot.Label(row1, text="AE Title:", width=10).pack(side='left', padx=5)
        self.remote_ae = ttk_boot.Entry(row1, width=15)
        self.remote_ae.insert(0, "REMOTE_AE")
        self.remote_ae.pack(side='left', padx=5)
        
        ttk_boot.Label(row1, text="Host:", width=8).pack(side='left', padx=5)
        self.remote_host = ttk_boot.Entry(row1, width=15)
        self.remote_host.insert(0, "127.0.0.1")
        self.remote_host.pack(side='left', padx=5)
        
        ttk_boot.Label(row1, text="Port:", width=8).pack(side='left', padx=5)
        self.remote_port = ttk_boot.Spinbox(row1, from_=1, to=65535, width=10)
        self.remote_port.set(104)
        self.remote_port.pack(side='left', padx=5)
        
        # Echo测试按钮
        self.btn_echo = ttk_boot.Button(row1, text="🔍 测试连接", bootstyle="info-outline",
                                       command=self.test_connection)
        self.btn_echo.pack(side='left', padx=10)
        
        # 文件列表
        list_frame = ttk_boot.Labelframe(frame, text="待发送文件列表", bootstyle="success", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 列表框和滚动条
        list_container = ttk_boot.Frame(list_frame)
        list_container.pack(fill='both', expand=True)
        
        scrollbar = ttk_boot.Scrollbar(list_container)
        scrollbar.pack(side='right', fill='y')
        
        self.file_listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set, 
                                       font=('Consolas', 9), selectmode='extended')
        self.file_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # 按钮
        btn_frame = ttk_boot.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk_boot.Button(btn_frame, text="添加文件", bootstyle="info", 
                       command=self.add_files).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="添加文件夹", bootstyle="info", 
                       command=self.add_folder).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="清空列表", bootstyle="warning", 
                       command=self.clear_files).pack(side='left', padx=5)
        
        # 进度条
        self.send_progress = ttk_boot.Progressbar(btn_frame, mode='determinate', bootstyle="success-striped")
        self.send_progress.pack(side='left', fill='x', expand=True, padx=10)
        
        ttk_boot.Button(btn_frame, text="发送全部", bootstyle="success", 
                       command=self.send_files).pack(side='right', padx=5)
        
        return frame

    
    def create_receive_tab(self):
        """创建接收标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        # SCP配置
        config_frame = ttk_boot.Labelframe(frame, text="接收服务配置", bootstyle="info", padding=10)
        config_frame.pack(fill='x', padx=10, pady=10)
        
        row1 = ttk_boot.Frame(config_frame)
        row1.pack(fill='x', pady=5)
        
        ttk_boot.Label(row1, text="本地AE Title:", width=12).pack(side='left', padx=5)
        self.local_ae = ttk_boot.Entry(row1, width=15)
        local_ae_config = self.config.get('local_scp.ae', 'DICOM_TOOL')
        self.local_ae.insert(0, local_ae_config)
        self.local_ae.pack(side='left', padx=5)
        
        ttk_boot.Label(row1, text="端口:", width=8).pack(side='left', padx=5)
        self.local_port = ttk_boot.Spinbox(row1, from_=1, to=65535, width=10)
        local_port_config = self.config.get('local_scp.port', 11112)
        self.local_port.set(local_port_config)
        self.local_port.pack(side='left', padx=5)
        
        ttk_boot.Label(row1, text="存储路径:", width=10).pack(side='left', padx=5)
        self.storage_path = ttk_boot.Entry(row1, width=30)
        storage_path_config = self.config.get('local_scp.storage_path', './storage')
        self.storage_path.insert(0, storage_path_config)
        self.storage_path.pack(side='left', padx=5)
        
        ttk_boot.Button(row1, text="浏览", bootstyle="secondary", 
                       command=self.browse_storage).pack(side='left', padx=5)
        
        # 控制按钮
        btn_frame = ttk_boot.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        self.btn_start_scp = ttk_boot.Button(btn_frame, text="▶ 启动接收服务", 
                                            bootstyle="success", command=self.start_scp)
        self.btn_start_scp.pack(side='left', padx=5)
        
        self.btn_stop_scp = ttk_boot.Button(btn_frame, text="⏹ 停止接收服务", 
                                           bootstyle="danger", command=self.stop_scp, state='disabled')
        self.btn_stop_scp.pack(side='left', padx=5)
        
        ttk_boot.Button(btn_frame, text="清空日志", bootstyle="warning", 
                       command=self.clear_log).pack(side='left', padx=5)
        
        # 日志显示
        log_frame = ttk_boot.Labelframe(frame, text="接收日志", bootstyle="secondary", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, font=('Consolas', 9), 
                                                  wrap='word', height=20)
        self.log_text.pack(fill='both', expand=True)
        
        return frame
    
    def create_forward_tab(self):
        """创建转发配置标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 转发开关
        switch_frame = ttk_boot.Frame(frame)
        switch_frame.pack(fill='x', padx=10, pady=10)
        
        self.forward_enabled = ttk_boot.Checkbutton(switch_frame, text="启用自动转发", 
                                                    bootstyle="success-round-toggle")
        self.forward_enabled.pack(side='left', padx=5)
        
        ttk_boot.Button(switch_frame, text="查看转发队列", bootstyle="info",
                       command=self.show_forward_queue).pack(side='left', padx=5)
        
        # 转发规则列表
        rules_frame = ttk_boot.Labelframe(frame, text="转发规则", bootstyle="primary", padding=10)
        rules_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 表格
        columns = ('enabled', 'target', 'modality', 'source_ae', 'priority')
        self.forward_tree = ttk_boot.Treeview(rules_frame, columns=columns, show='headings', height=10)
        
        self.forward_tree.heading('enabled', text='启用')
        self.forward_tree.heading('target', text='目标节点')
        self.forward_tree.heading('modality', text='模态过滤')
        self.forward_tree.heading('source_ae', text='来源AE过滤')
        self.forward_tree.heading('priority', text='优先级')
        
        self.forward_tree.column('enabled', width=60, anchor='center')
        self.forward_tree.column('target', width=150)
        self.forward_tree.column('modality', width=150)
        self.forward_tree.column('source_ae', width=150)
        self.forward_tree.column('priority', width=80, anchor='center')
        
        scrollbar = ttk_boot.Scrollbar(rules_frame, orient='vertical', command=self.forward_tree.yview)
        self.forward_tree.configure(yscrollcommand=scrollbar.set)
        
        self.forward_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 按钮
        btn_frame = ttk_boot.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk_boot.Button(btn_frame, text="添加规则", bootstyle="success",
                       command=self.add_forward_rule).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="编辑规则", bootstyle="info",
                       command=self.edit_forward_rule).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="删除规则", bootstyle="danger",
                       command=self.delete_forward_rule).pack(side='left', padx=5)
        
        self.load_forward_rules()
        
        return frame

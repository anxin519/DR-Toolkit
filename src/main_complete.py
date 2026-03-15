# -*- coding: utf-8 -*-
"""完整版主程序入口"""
import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import ttkbootstrap as ttk_boot
from ttkbootstrap.constants import *
import threading
from datetime import datetime
import pydicom

# 导入模块
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
from utils.charset_helper import fix_dataset_encoding, safe_str
from core.config_manager import ConfigManager
from core.logger import Logger
from core.forward_queue import ForwardQueue

class DicomToolApp:
    """DICOM运维工具主应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM运维工具 v2.0 - 完整版")
        self.root.geometry("1200x800")
        
        # 初始化
        self.config = ConfigManager()
        self.logger = Logger.get_logger('app')
        self.forward_queue = ForwardQueue()
        
        # 状态变量
        self.scp = None
        self.worklist_scp = None
        self.current_dataset = None
        self.current_filepath = None
        self.file_paths = []
        self.browser_data = []
        self.auto_forward_var = tk.BooleanVar(value=False)
        
        self.create_ui()
        self.logger.info("应用启动")
    
    def create_ui(self):
        """创建UI"""
        # 主标签页
        self.notebook = ttk_boot.Notebook(self.root, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 添加标签页
        self.notebook.add(self.create_send_tab(), text="📤 发送")
        self.notebook.add(self.create_receive_tab(), text="📥 接收")
        self.notebook.add(self.create_worklist_tab(), text="📋 Worklist")
        self.notebook.add(self.create_editor_tab(), text="✏️ 编辑器")
        self.notebook.add(self.create_browser_tab(), text="📁 文件浏览")
        
        # 状态栏
        self.status = ttk_boot.Label(self.root, text="就绪", relief='sunken', anchor='w')
        self.status.pack(side='bottom', fill='x')
    
    def create_send_tab(self):
        """发送页面"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 目标节点管理区
        node_frame = ttk_boot.Labelframe(frame, text="目标节点管理", padding=10)
        node_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 左侧：节点列表
        left_panel = ttk_boot.Frame(node_frame)
        left_panel.pack(side='left', fill='both', expand=True, padx=5)
        
        ttk_boot.Label(left_panel, text="可用节点列表（勾选要发送的节点）:").pack(anchor='w', pady=5)
        
        # 节点列表（带复选框）
        from tkinter import ttk
        columns = ('selected', 'name', 'ae', 'host', 'port', 'status')
        self.node_tree = ttk.Treeview(left_panel, columns=columns, show='headings', height=8)
        
        self.node_tree.heading('selected', text='✓')
        self.node_tree.heading('name', text='名称')
        self.node_tree.heading('ae', text='AE Title')
        self.node_tree.heading('host', text='Host')
        self.node_tree.heading('port', text='Port')
        self.node_tree.heading('status', text='状态')
        
        self.node_tree.column('selected', width=40, anchor='center')
        self.node_tree.column('name', width=120)
        self.node_tree.column('ae', width=100)
        self.node_tree.column('host', width=120)
        self.node_tree.column('port', width=60, anchor='center')
        self.node_tree.column('status', width=80, anchor='center')
        
        # 双击填充到右侧编辑区
        self.node_tree.bind('<Double-1>', self.load_node_to_edit)
        # 单击切换选中状态
        self.node_tree.bind('<Button-1>', self.toggle_node_selection)
        
        scrollbar = ttk_boot.Scrollbar(left_panel, orient='vertical', command=self.node_tree.yview)
        self.node_tree.configure(yscrollcommand=scrollbar.set)
        
        self.node_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 节点管理按钮（竖向排列）
        node_btn_frame = ttk_boot.Frame(left_panel)
        node_btn_frame.pack(fill='x', pady=5)
        
        ttk_boot.Button(node_btn_frame, text="全选", bootstyle="info-outline",
                       command=self.select_all_nodes).pack(fill='x', pady=2)
        ttk_boot.Button(node_btn_frame, text="全不选", bootstyle="info-outline",
                       command=self.deselect_all_nodes).pack(fill='x', pady=2)
        ttk_boot.Button(node_btn_frame, text="测试选中", bootstyle="info",
                       command=self.test_selected_nodes).pack(fill='x', pady=2)
        
        # 右侧：节点编辑
        right_panel = ttk_boot.Frame(node_frame)
        right_panel.pack(side='right', fill='y', padx=5)
        
        ttk_boot.Label(right_panel, text="添加/编辑节点:").pack(anchor='w', pady=5)
        
        edit_frame = ttk_boot.Frame(right_panel)
        edit_frame.pack(fill='x', pady=5)
        
        ttk_boot.Label(edit_frame, text="名称:", width=8).grid(row=0, column=0, sticky='w', pady=2)
        self.node_name = ttk_boot.Entry(edit_frame, width=20)
        self.node_name.grid(row=0, column=1, pady=2)
        
        ttk_boot.Label(edit_frame, text="AE Title:", width=8).grid(row=1, column=0, sticky='w', pady=2)
        self.node_ae = ttk_boot.Entry(edit_frame, width=20)
        self.node_ae.grid(row=1, column=1, pady=2)
        
        ttk_boot.Label(edit_frame, text="Host:", width=8).grid(row=2, column=0, sticky='w', pady=2)
        self.node_host = ttk_boot.Entry(edit_frame, width=20)
        self.node_host.grid(row=2, column=1, pady=2)
        
        ttk_boot.Label(edit_frame, text="Port:", width=8).grid(row=3, column=0, sticky='w', pady=2)
        self.node_port = ttk_boot.Spinbox(edit_frame, from_=1, to=65535, width=18)
        self.node_port.set(104)
        self.node_port.grid(row=3, column=1, pady=2)
        
        edit_btn_frame = ttk_boot.Frame(right_panel)
        edit_btn_frame.pack(fill='x', pady=10)
        
        ttk_boot.Button(edit_btn_frame, text="添加节点", bootstyle="success",
                       command=self.add_node).pack(fill='x', pady=2)
        ttk_boot.Button(edit_btn_frame, text="更新节点", bootstyle="info",
                       command=self.update_node).pack(fill='x', pady=2)
        ttk_boot.Button(edit_btn_frame, text="删除节点", bootstyle="danger",
                       command=self.delete_node).pack(fill='x', pady=2)
        
        # 文件列表
        file_frame = ttk_boot.Labelframe(frame, text="待发送文件列表", padding=10)
        file_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.file_listbox = tk.Listbox(file_frame, font=('Consolas', 9), height=10)
        file_scrollbar = ttk_boot.Scrollbar(file_frame, orient='vertical', command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        self.file_listbox.pack(side='left', fill='both', expand=True)
        file_scrollbar.pack(side='right', fill='y')
        
        # 按钮
        btn_frame = ttk_boot.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk_boot.Button(btn_frame, text="添加文件", command=self.add_files).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="添加文件夹", command=self.add_folder).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="清空", command=self.clear_files).pack(side='left', padx=5)
        
        # 进度信息
        self.send_status_label = ttk_boot.Label(btn_frame, text="")
        self.send_status_label.pack(side='left', padx=10)
        
        ttk_boot.Button(btn_frame, text="发送到选中节点", bootstyle="success",
                       command=self.send_files).pack(side='right', padx=5)
        
        # 加载节点列表
        self.load_nodes()
        
        return frame
    
    def create_receive_tab(self):
        """接收页面"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 配置
        cfg = ttk_boot.Labelframe(frame, text="SCP配置", padding=10)
        cfg.pack(fill='x', padx=10, pady=10)
        
        row = ttk_boot.Frame(cfg)
        row.pack(fill='x')
        
        ttk_boot.Label(row, text="AE:").pack(side='left', padx=5)
        self.local_ae = ttk_boot.Entry(row, width=12)
        self.local_ae.insert(0, "DICOM_TOOL")
        self.local_ae.pack(side='left', padx=5)
        
        ttk_boot.Label(row, text="Port:").pack(side='left', padx=5)
        self.local_port = ttk_boot.Spinbox(row, from_=1, to=65535, width=8)
        self.local_port.set(11112)
        self.local_port.pack(side='left', padx=5)
        
        ttk_boot.Label(row, text="存储:").pack(side='left', padx=5)
        self.storage_path = ttk_boot.Entry(row, width=30)
        self.storage_path.insert(0, "./storage")
        self.storage_path.pack(side='left', padx=5)
        
        # 控制按钮行
        btn_row = ttk_boot.Frame(cfg)
        btn_row.pack(fill='x', pady=10)
        
        # 自动转发选项
        self.auto_forward_enabled = ttk_boot.Checkbutton(
            btn_row,
            text="启用自动转发",
            bootstyle="success-round-toggle",
            variable=self.auto_forward_var
        )
        self.auto_forward_enabled.pack(side='left', padx=5)
        
        # 分隔线
        ttk_boot.Separator(btn_row, orient='vertical').pack(side='left', fill='y', padx=10)
        
        self.btn_start_scp = ttk_boot.Button(btn_row, text="▶ 启动", bootstyle="success",
                                            command=self.start_scp)
        self.btn_start_scp.pack(side='left', padx=5)
        
        self.btn_stop_scp = ttk_boot.Button(btn_row, text="⏹ 停止", bootstyle="danger",
                                           command=self.stop_scp, state='disabled')
        self.btn_stop_scp.pack(side='left', padx=5)
        
        # 日志
        log_frame = ttk_boot.Labelframe(frame, text="日志", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, font=('Consolas', 9), height=20)
        self.log_text.pack(fill='both', expand=True)
        
        return frame

    
    def create_worklist_tab(self):
        """Worklist标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        # ── 上半部分：Worklist SCP 服务 ──────────────────────────────
        scp_frame = ttk_boot.Labelframe(frame, text="Worklist SCP 服务（响应设备查询）", padding=10)
        scp_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        # 服务配置行
        cfg_row = ttk_boot.Frame(scp_frame)
        cfg_row.pack(fill='x', pady=5)
        
        ttk_boot.Label(cfg_row, text="AE Title:").pack(side='left', padx=5)
        self.wl_scp_ae = ttk_boot.Entry(cfg_row, width=14)
        self.wl_scp_ae.insert(0, "WORKLIST_SCP")
        self.wl_scp_ae.pack(side='left', padx=5)
        
        ttk_boot.Label(cfg_row, text="端口:").pack(side='left', padx=5)
        self.wl_scp_port = ttk_boot.Spinbox(cfg_row, from_=1, to=65535, width=8)
        self.wl_scp_port.set(11113)
        self.wl_scp_port.pack(side='left', padx=5)
        
        self.btn_start_wl = ttk_boot.Button(cfg_row, text="▶ 启动服务",
                                            bootstyle="success", command=self.start_worklist_scp)
        self.btn_start_wl.pack(side='left', padx=10)
        
        self.btn_stop_wl = ttk_boot.Button(cfg_row, text="⏹ 停止服务",
                                           bootstyle="danger", command=self.stop_worklist_scp,
                                           state='disabled')
        self.btn_stop_wl.pack(side='left', padx=5)
        
        self.wl_scp_status = ttk_boot.Label(cfg_row, text="● 未运行", bootstyle="secondary")
        self.wl_scp_status.pack(side='left', padx=10)
        
        # Worklist数据管理
        data_frame = ttk_boot.Labelframe(frame, text="Worklist 数据管理", padding=10)
        data_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 数据表格
        from tkinter import ttk as _ttk
        wl_cols = ('patient_id', 'patient_name', 'sex', 'age', 'study_date',
                   'study_time', 'modality', 'description', 'accession')
        self.wl_tree = _ttk.Treeview(data_frame, columns=wl_cols, show='headings', height=10)
        
        headers = [('patient_id', '患者ID', 90), ('patient_name', '患者姓名', 100),
                   ('sex', '性别', 50), ('age', '年龄', 60), ('study_date', '检查日期', 90),
                   ('study_time', '检查时间', 80), ('modality', '模态', 60),
                   ('description', '检查描述', 120), ('accession', 'AccessionNo', 110)]
        
        for col, heading, width in headers:
            self.wl_tree.heading(col, text=heading)
            self.wl_tree.column(col, width=width, anchor='center')
        
        wl_scroll = ttk_boot.Scrollbar(data_frame, orient='vertical', command=self.wl_tree.yview)
        self.wl_tree.configure(yscrollcommand=wl_scroll.set)
        self.wl_tree.pack(side='left', fill='both', expand=True)
        wl_scroll.pack(side='right', fill='y')
        
        # 数据操作按钮
        data_btn = ttk_boot.Frame(frame)
        data_btn.pack(fill='x', padx=10, pady=5)
        
        ttk_boot.Button(data_btn, text="➕ 添加项目", bootstyle="success",
                       command=self.add_worklist_item).pack(side='left', padx=5)
        ttk_boot.Button(data_btn, text="🗑 删除选中", bootstyle="danger",
                       command=self.delete_worklist_item).pack(side='left', padx=5)
        ttk_boot.Button(data_btn, text="🎲 生成测试数据", bootstyle="info",
                       command=self.generate_worklist_test_data).pack(side='left', padx=5)
        ttk_boot.Button(data_btn, text="🔄 刷新列表", bootstyle="secondary",
                       command=self.refresh_worklist_tree).pack(side='left', padx=5)
        ttk_boot.Button(data_btn, text="🗑 清空全部", bootstyle="warning",
                       command=self.clear_worklist_data).pack(side='left', padx=5)
        
        # ── 下半部分：Worklist SCU 查询 ──────────────────────────────
        scu_frame = ttk_boot.Labelframe(frame, text="Worklist SCU 查询（向服务器查询）", padding=10)
        scu_frame.pack(fill='x', padx=10, pady=(5, 10))
        
        # 查询目标配置
        scu_row1 = ttk_boot.Frame(scu_frame)
        scu_row1.pack(fill='x', pady=5)
        
        ttk_boot.Label(scu_row1, text="服务器AE:").pack(side='left', padx=5)
        self.wl_scu_ae = ttk_boot.Entry(scu_row1, width=14)
        self.wl_scu_ae.insert(0, "WORKLIST_SCP")
        self.wl_scu_ae.pack(side='left', padx=5)
        
        ttk_boot.Label(scu_row1, text="Host:").pack(side='left', padx=5)
        self.wl_scu_host = ttk_boot.Entry(scu_row1, width=14)
        self.wl_scu_host.insert(0, "127.0.0.1")
        self.wl_scu_host.pack(side='left', padx=5)
        
        ttk_boot.Label(scu_row1, text="Port:").pack(side='left', padx=5)
        self.wl_scu_port = ttk_boot.Spinbox(scu_row1, from_=1, to=65535, width=8)
        self.wl_scu_port.set(11113)
        self.wl_scu_port.pack(side='left', padx=5)
        
        # 查询条件
        scu_row2 = ttk_boot.Frame(scu_frame)
        scu_row2.pack(fill='x', pady=5)
        
        ttk_boot.Label(scu_row2, text="患者ID:").pack(side='left', padx=5)
        self.wl_query_pid = ttk_boot.Entry(scu_row2, width=14)
        self.wl_query_pid.pack(side='left', padx=5)
        
        ttk_boot.Label(scu_row2, text="患者姓名:").pack(side='left', padx=5)
        self.wl_query_name = ttk_boot.Entry(scu_row2, width=14)
        self.wl_query_name.pack(side='left', padx=5)
        
        ttk_boot.Label(scu_row2, text="模态:").pack(side='left', padx=5)
        self.wl_query_modality = ttk_boot.Combobox(scu_row2, width=8, state='readonly',
                                                   values=['', 'CR', 'DR', 'CT', 'MR', 'US', 'XA'])
        self.wl_query_modality.pack(side='left', padx=5)
        
        ttk_boot.Button(scu_row2, text="🔍 查询", bootstyle="primary",
                       command=self.query_worklist).pack(side='left', padx=10)
        
        # 查询结果
        result_frame = ttk_boot.Labelframe(scu_frame, text="查询结果", padding=5)
        result_frame.pack(fill='x', pady=5)
        
        res_cols = ('patient_id', 'patient_name', 'modality', 'study_date', 'description', 'accession')
        self.wl_result_tree = _ttk.Treeview(result_frame, columns=res_cols, show='headings', height=5)
        
        for col, heading, width in [('patient_id', '患者ID', 100), ('patient_name', '患者姓名', 100),
                                     ('modality', '模态', 60), ('study_date', '检查日期', 90),
                                     ('description', '描述', 150), ('accession', 'AccessionNo', 110)]:
            self.wl_result_tree.heading(col, text=heading)
            self.wl_result_tree.column(col, width=width, anchor='center')
        
        res_scroll = ttk_boot.Scrollbar(result_frame, orient='vertical', command=self.wl_result_tree.yview)
        self.wl_result_tree.configure(yscrollcommand=res_scroll.set)
        self.wl_result_tree.pack(side='left', fill='both', expand=True)
        res_scroll.pack(side='right', fill='y')
        
        return frame

    def create_editor_tab(self):
        """编辑器页面"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 按钮
        btn_frame = ttk_boot.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk_boot.Button(btn_frame, text="打开", command=self.open_dcm).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="匿名化", command=self.anonymize).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="修改UID", command=self.modify_uid).pack(side='left', padx=5)
        
        self.btn_calc_age = ttk_boot.Button(btn_frame, text="计算年龄", command=self.calc_age)
        self.btn_calc_age.pack(side='left', padx=5)
        self.btn_calc_age.pack_forget()  # 默认隐藏
        
        ttk_boot.Button(btn_frame, text="保存", bootstyle="success", command=self.save_dcm).pack(side='right', padx=5)
        
        # 内容区
        content = ttk_boot.Frame(frame)
        content.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 左侧图像
        left = ttk_boot.Labelframe(content, text="图像", padding=10)
        left.pack(side='left', fill='both', expand=True, padx=5)
        
        self.image_canvas = tk.Canvas(left, bg='black')
        self.image_canvas.pack(fill='both', expand=True)
        
        # 窗宽窗位控制
        ww_frame = ttk_boot.Frame(left)
        ww_frame.pack(fill='x', pady=5)
        
        ttk_boot.Label(ww_frame, text="窗位:").pack(side='left', padx=5)
        self.wc_var = tk.IntVar(value=0)
        self.wc_scale = ttk_boot.Scale(ww_frame, from_=-2000, to=2000, variable=self.wc_var,
                                      command=self.update_window, orient='horizontal')
        self.wc_scale.pack(side='left', fill='x', expand=True, padx=5)
        
        ttk_boot.Label(ww_frame, text="窗宽:").pack(side='left', padx=5)
        self.ww_var = tk.IntVar(value=400)
        self.ww_scale = ttk_boot.Scale(ww_frame, from_=1, to=4000, variable=self.ww_var,
                                      command=self.update_window, orient='horizontal')
        self.ww_scale.pack(side='left', fill='x', expand=True, padx=5)
        
        ttk_boot.Button(ww_frame, text="肺窗", bootstyle="info-outline",
                       command=lambda: self.apply_preset('lung')).pack(side='left', padx=2)
        
        # 右侧标签
        right = ttk_boot.Labelframe(content, text="DICOM标签", padding=10)
        right.pack(side='right', fill='both', expand=True, padx=5)
        
        self.tag_text = scrolledtext.ScrolledText(right, font=('Consolas', 9))
        self.tag_text.pack(fill='both', expand=True)
        
        return frame
    
    def create_browser_tab(self):
        """文件浏览器页面"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 工具栏
        toolbar = ttk_boot.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        
        ttk_boot.Button(toolbar, text="选择文件夹", command=self.select_folder).pack(side='left', padx=5)
        ttk_boot.Button(toolbar, text="导出Excel", bootstyle="success",
                       command=self.export_excel).pack(side='left', padx=5)
        
        # 批量操作菜单
        batch_menu = ttk_boot.Menubutton(toolbar, text="批量操作 ▼", bootstyle="info")
        batch_menu.pack(side='left', padx=5)
        
        menu = tk.Menu(batch_menu, tearoff=0)
        batch_menu['menu'] = menu
        menu.add_command(label="批量匿名化", command=self.batch_anonymize)
        menu.add_command(label="批量计算年龄", command=self.batch_calc_age)
        menu.add_command(label="批量修改UID", command=self.batch_modify_uid)
        
        # 进度条
        self.browser_progress = ttk_boot.Progressbar(toolbar, mode='determinate')
        self.browser_progress.pack(side='left', fill='x', expand=True, padx=10)
        
        # 表格
        from tkinter import ttk
        columns = ('path', 'name', 'patient_name', 'patient_id', 'sex', 'age', 'date', 'modality')
        self.browser_tree = ttk.Treeview(frame, columns=columns, show='headings', height=25)
        
        headers = ['路径', '文件名', '患者姓名', '病历号', '性别', '年龄', '检查日期', '模态']
        for col, header in zip(columns, headers):
            self.browser_tree.heading(col, text=header)
            self.browser_tree.column(col, width=100)
        
        scrollbar = ttk_boot.Scrollbar(frame, orient='vertical', command=self.browser_tree.yview)
        self.browser_tree.configure(yscrollcommand=scrollbar.set)
        
        self.browser_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)
        
        return frame
    
    # ========== 事件处理 ==========
    
    def load_nodes(self):
        """加载节点列表"""
        self.node_tree.delete(*self.node_tree.get_children())
        
        nodes = self.config.get_remote_nodes()
        for node in nodes:
            self.node_tree.insert('', 'end', values=(
                '☐',  # 未选中
                node.get('name', ''),
                node.get('ae', ''),
                node.get('host', ''),
                node.get('port', ''),
                '-'
            ), tags=('unselected',))
    
    def toggle_node_selection(self, event):
        """切换节点选中状态（单击）"""
        # 获取点击的行
        region = self.node_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        item = self.node_tree.identify_row(event.y)
        if not item:
            return
        
        # 获取点击的列
        column = self.node_tree.identify_column(event.x)
        
        # 只有点击第一列（选中列）时才切换状态
        if column == '#1':  # 第一列
            values = list(self.node_tree.item(item, 'values'))
            
            if values[0] == '☐':
                values[0] = '☑'
                self.node_tree.item(item, values=values, tags=('selected',))
                self.node_tree.tag_configure('selected', background='#d4edda')
            else:
                values[0] = '☐'
                self.node_tree.item(item, values=values, tags=('unselected',))
                self.node_tree.tag_configure('unselected', background='')
    
    def load_node_to_edit(self, event):
        """双击加载节点到编辑区"""
        item = self.node_tree.identify_row(event.y)
        if not item:
            return
        
        values = self.node_tree.item(item, 'values')
        
        # 填充到右侧编辑区
        self.node_name.delete(0, 'end')
        self.node_name.insert(0, values[1])  # 名称
        
        self.node_ae.delete(0, 'end')
        self.node_ae.insert(0, values[2])  # AE
        
        self.node_host.delete(0, 'end')
        self.node_host.insert(0, values[3])  # Host
        
        self.node_port.delete(0, 'end')
        self.node_port.insert(0, values[4])  # Port
        
        # 选中该行以便更新
        self.node_tree.selection_set(item)
    
    def select_all_nodes(self):
        """全选节点"""
        for item in self.node_tree.get_children():
            values = list(self.node_tree.item(item, 'values'))
            values[0] = '☑'
            self.node_tree.item(item, values=values, tags=('selected',))
        self.node_tree.tag_configure('selected', background='#d4edda')
    
    def deselect_all_nodes(self):
        """取消全选"""
        for item in self.node_tree.get_children():
            values = list(self.node_tree.item(item, 'values'))
            values[0] = '☐'
            self.node_tree.item(item, values=values, tags=('unselected',))
        self.node_tree.tag_configure('unselected', background='')
    
    def get_selected_nodes(self):
        """获取选中的节点"""
        selected = []
        for item in self.node_tree.get_children():
            values = self.node_tree.item(item, 'values')
            if values[0] == '☑':
                selected.append({
                    'name': values[1],
                    'ae': values[2],
                    'host': values[3],
                    'port': int(values[4])
                })
        return selected
    
    def test_selected_nodes(self):
        """测试选中的节点"""
        selected = self.get_selected_nodes()
        if not selected:
            messagebox.showwarning("警告", "请先选择要测试的节点")
            return
        
        def test_thread():
            results = []
            for idx, node in enumerate(selected):
                try:
                    success, msg, time_ms = DicomEcho.test(
                        node['host'],
                        node['port'],
                        node['ae']
                    )
                    
                    # 更新状态
                    status = '✓' if success else '✗'
                    self.update_node_status(idx, status)
                    
                    results.append((node['name'], success, msg))
                except Exception as e:
                    self.update_node_status(idx, '✗')
                    results.append((node['name'], False, str(e)))
            
            # 显示结果
            self.root.after(0, lambda: self.show_test_results(results))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def update_node_status(self, index, status):
        """更新节点状态"""
        items = self.node_tree.get_children()
        selected_items = [item for item in items if self.node_tree.item(item, 'values')[0] == '☑']
        
        if index < len(selected_items):
            item = selected_items[index]
            values = list(self.node_tree.item(item, 'values'))
            values[5] = status
            self.root.after(0, lambda: self.node_tree.item(item, values=values))
    
    def show_test_results(self, results):
        """显示测试结果"""
        msg = "连接测试结果:\n\n"
        for name, success, detail in results:
            status = "✓ 成功" if success else "✗ 失败"
            msg += f"{name}: {status}\n"
            if not success:
                msg += f"  {detail}\n"
            msg += "\n"
        
        messagebox.showinfo("测试结果", msg)
    
    def add_node(self):
        """添加节点"""
        name = self.node_name.get().strip()
        ae = self.node_ae.get().strip()
        host = self.node_host.get().strip()
        port = self.node_port.get()
        
        if not all([name, ae, host, port]):
            messagebox.showwarning("警告", "请填写完整的节点信息")
            return
        
        node = {
            'name': name,
            'ae': ae,
            'host': host,
            'port': int(port)
        }
        
        self.config.add_remote_node(node)
        self.load_nodes()
        
        # 清空输入
        self.node_name.delete(0, 'end')
        self.node_ae.delete(0, 'end')
        self.node_host.delete(0, 'end')
        self.node_port.set(104)
        
        messagebox.showinfo("成功", f"节点 '{name}' 已添加")
    
    def update_node(self):
        """更新节点"""
        selected = self.node_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要更新的节点")
            return
        
        item = selected[0]
        index = self.node_tree.index(item)
        
        name = self.node_name.get().strip()
        ae = self.node_ae.get().strip()
        host = self.node_host.get().strip()
        port = self.node_port.get()
        
        if not all([name, ae, host, port]):
            messagebox.showwarning("警告", "请填写完整的节点信息")
            return
        
        node = {
            'name': name,
            'ae': ae,
            'host': host,
            'port': int(port)
        }
        
        self.config.update_remote_node(index, node)
        self.load_nodes()
        messagebox.showinfo("成功", f"节点 '{name}' 已更新")
    
    def delete_node(self):
        """删除节点"""
        selected = self.node_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要删除的节点")
            return
        
        item = selected[0]
        values = self.node_tree.item(item, 'values')
        name = values[1]
        
        if messagebox.askyesno("确认", f"确定要删除节点 '{name}' 吗？"):
            index = self.node_tree.index(item)
            self.config.delete_remote_node(index)
            self.load_nodes()
            messagebox.showinfo("成功", f"节点 '{name}' 已删除")
    
    def clear_filesiles(self):
        """清空文件列表"""
        self.file_listbox.delete(0, 'end')
        self.file_paths.clear()
    
    def add_files(self):
        """添加文件"""
        files = filedialog.askopenfilenames(
            title="选择DICOM文件",
            filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
        )
        for f in files:
            if f not in self.file_paths:
                self.file_paths.append(f)
                self.file_listbox.insert('end', f)
    
    def add_folder(self):
        """添加文件夹"""
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.dcm'):
                        filepath = os.path.join(root, file)
                        if filepath not in self.file_paths:
                            self.file_paths.append(filepath)
                            self.file_listbox.insert('end', filepath)
    
    def send_files(self):
        """发送文件到选中的节点"""
        if not self.file_paths:
            messagebox.showwarning("警告", "请先添加文件")
            return
        
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            messagebox.showwarning("警告", "请先选择目标节点")
            return
        
        # 确认发送
        node_names = ', '.join([n['name'] for n in selected_nodes])
        if not messagebox.askyesno("确认发送", 
            f"将 {len(self.file_paths)} 个文件发送到以下节点:\n{node_names}\n\n确定继续吗？"):
            return
        
        def send_thread():
            total_files = len(self.file_paths)
            total_nodes = len(selected_nodes)
            total_tasks = total_files * total_nodes
            completed = 0
            
            results = {}
            
            for node in selected_nodes:
                node_name = node['name']
                results[node_name] = {'success': 0, 'failed': 0}
                
                self.root.after(0, lambda n=node_name: 
                    self.send_status_label.config(text=f"正在发送到 {n}..."))
                
                try:
                    scu = DicomSCU()
                    send_results = scu.send_batch(
                        self.file_paths,
                        node['host'],
                        node['port'],
                        node['ae']
                    )
                    
                    for filepath, success in send_results:
                        if success:
                            results[node_name]['success'] += 1
                        else:
                            results[node_name]['failed'] += 1
                        
                        completed += 1
                        progress = int((completed / total_tasks) * 100)
                        self.root.after(0, lambda p=progress, c=completed, t=total_tasks: 
                            self.send_status_label.config(text=f"进度: {c}/{t} ({p}%)"))
                    
                    self.logger.info(f"发送到 {node_name} 完成: 成功{results[node_name]['success']}, 失败{results[node_name]['failed']}")
                    
                except Exception as e:
                    self.logger.error(f"发送到 {node_name} 失败: {e}")
                    results[node_name]['error'] = str(e)
                    completed += total_files
            
            # 显示结果
            self.root.after(0, lambda: self.show_send_results(results, total_files))
            self.root.after(0, lambda: self.send_status_label.config(text=""))
        
        threading.Thread(target=send_thread, daemon=True).start()
    
    def show_send_results(self, results, total_files):
        """显示发送结果"""
        msg = f"发送完成！\n\n总文件数: {total_files}\n\n"
        
        for node_name, result in results.items():
            msg += f"【{node_name}】\n"
            if 'error' in result:
                msg += f"  ✗ 错误: {result['error']}\n"
            else:
                msg += f"  ✓ 成功: {result['success']}\n"
                if result['failed'] > 0:
                    msg += f"  ✗ 失败: {result['failed']}\n"
            msg += "\n"
        
        messagebox.showinfo("发送结果", msg)
    
    def start_scp(self):
        """启动SCP"""
        try:
            self.scp = DicomSCP(
                ae_title=self.local_ae.get(),
                port=int(self.local_port.get()),
                storage_path=self.storage_path.get(),
                on_received=self._on_file_received
            )
            self.scp.start()

            self.btn_start_scp.config(state='disabled')
            self.btn_stop_scp.config(state='normal')
            self.log_text.insert('end', f"✓ SCP已启动 端口:{self.local_port.get()}\n")
            self.log_text.see('end')
            self.logger.info(f"SCP已启动 AE:{self.local_ae.get()} 端口:{self.local_port.get()}")
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
            self.logger.error(f"SCP启动失败: {e}")

    def _on_file_received(self, filepath, dataset):
        """SCP收到文件后的回调"""
        patient = str(getattr(dataset, 'PatientName', ''))
        modality = str(getattr(dataset, 'Modality', ''))
        msg = f"✓ 收到文件: {os.path.basename(filepath)}  患者:{patient}  模态:{modality}\n"
        self.root.after(0, lambda: self._append_log(msg))
        self.logger.info(f"收到文件: {filepath} 患者:{patient} 模态:{modality}")

        # 自动转发
        if self.auto_forward_var.get():
            selected_nodes = self.get_selected_nodes()
            for node in selected_nodes:
                self.forward_queue.add_task(filepath, node)

    def _append_log(self, msg):
        """线程安全地追加日志"""
        self.log_text.insert('end', msg)
        self.log_text.see('end')
    
    def stop_scp(self):
        """停止SCP"""
        if self.scp:
            self.scp.stop()
            self.scp = None

        self.btn_start_scp.config(state='normal')
        self.btn_stop_scp.config(state='disabled')
        self.log_text.insert('end', "✓ SCP已停止\n")
        self.log_text.see('end')
        self.logger.info("SCP已停止")
    
    def open_dcm(self):
        """打开DCM文件"""
        filepath = filedialog.askopenfilename(
            title="打开DICOM文件",
            filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                self.current_dataset = DicomEditor.load_file(filepath)
                self.current_filepath = filepath
                
                # 显示标签
                self.tag_text.delete('1.0', 'end')
                self.tag_text.insert('1.0', DicomEditor.dataset_to_text(self.current_dataset))
                
                # 显示图像
                self.display_image()
                
                # 检查是否需要显示计算年龄按钮
                if not hasattr(self.current_dataset, 'PatientAge') or not self.current_dataset.PatientAge:
                    self.btn_calc_age.pack(side='left', padx=5)
                else:
                    self.btn_calc_age.pack_forget()
                
            except Exception as e:
                messagebox.showerror("错误", f"打开失败: {str(e)}")
    
    def display_image(self):
        """显示图像"""
        if not self.current_dataset:
            return
        
        try:
            # 加载图像
            pixel_array = DicomImageViewer.load_image(self.current_dataset)
            if pixel_array is None:
                return
            
            # 获取窗宽窗位
            ww_from_dicom = DicomImageViewer.get_window_from_dicom(self.current_dataset)
            if ww_from_dicom:
                center, width = ww_from_dicom
            else:
                center, width = DicomImageViewer.auto_window(pixel_array)
            
            self.wc_var.set(center)
            self.ww_var.set(width)
            
            # 显示
            self.update_image_display(pixel_array, center, width)
            
        except Exception as e:
            print(f"显示图像失败: {e}")
    
    def update_image_display(self, pixel_array, center, width):
        """更新图像显示"""
        try:
            # 转换为PIL图像
            pil_img = DicomImageViewer.to_pil_image(pixel_array, center, width)
            if pil_img is None:
                return
            
            # 调整大小
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()
            if canvas_width > 1 and canvas_height > 1:
                pil_img = DicomImageViewer.resize_image(pil_img, canvas_width, canvas_height)
            
            # 转换为Tkinter图像
            self.current_tk_image = DicomImageViewer.to_tk_image(pil_img)
            if self.current_tk_image:
                self.image_canvas.delete('all')
                self.image_canvas.create_image(
                    canvas_width//2, canvas_height//2,
                    image=self.current_tk_image
                )
        except Exception as e:
            print(f"更新图像显示失败: {e}")
    
    def update_window(self, event=None):
        """更新窗宽窗位"""
        if self.current_dataset:
            pixel_array = DicomImageViewer.load_image(self.current_dataset)
            if pixel_array is not None:
                self.update_image_display(
                    pixel_array,
                    self.wc_var.get(),
                    self.ww_var.get()
                )
    
    def apply_preset(self, preset_name):
        """应用窗宽窗位预设"""
        presets = self.config.get('ui_settings.window_presets', {})
        if preset_name in presets:
            preset = presets[preset_name]
            self.wc_var.set(preset['center'])
            self.ww_var.set(preset['width'])
            self.update_window()
    
    def anonymize(self):
        """匿名化"""
        if self.current_dataset:
            keep_digits = self.config.get('anonymize.keep_last_digits', 4)
            prefix = self.config.get('anonymize.prefix', 'ANON')
            self.current_dataset = DicomAnonymizer.anonymize(
                self.current_dataset, prefix, keep_digits
            )
            self.tag_text.delete('1.0', 'end')
            self.tag_text.insert('1.0', DicomEditor.dataset_to_text(self.current_dataset))
            messagebox.showinfo("成功", "匿名化完成")
        else:
            messagebox.showwarning("警告", "请先打开文件")
    
    def modify_uid(self):
        """修改UID"""
        if self.current_dataset:
            method = self.config.get('uid_strategy.method', 'append_timestamp')
            self.current_dataset = modify_uids(self.current_dataset, method)
            self.tag_text.delete('1.0', 'end')
            self.tag_text.insert('1.0', DicomEditor.dataset_to_text(self.current_dataset))
            messagebox.showinfo("成功", "UID已修改")
        else:
            messagebox.showwarning("警告", "请先打开文件")
    
    def calc_age(self):
        """计算年龄"""
        if self.current_dataset and hasattr(self.current_dataset, 'PatientBirthDate'):
            birth_date = self.current_dataset.PatientBirthDate
            study_date = getattr(self.current_dataset, 'StudyDate', None)
            age = calculate_age(birth_date, study_date)
            if age:
                self.current_dataset.PatientAge = age
                self.tag_text.delete('1.0', 'end')
                self.tag_text.insert('1.0', DicomEditor.dataset_to_text(self.current_dataset))
                self.btn_calc_age.pack_forget()
                messagebox.showinfo("成功", f"年龄已计算: {age}")
            else:
                messagebox.showerror("错误", "无法计算年龄")
        else:
            messagebox.showwarning("警告", "文件中没有出生日期")
    
    def save_dcm(self):
        """保存文件"""
        if self.current_dataset:
            filepath = filedialog.asksaveasfilename(
                title="保存DICOM文件",
                defaultextension=".dcm",
                filetypes=[("DICOM Files", "*.dcm")]
            )
            if filepath:
                try:
                    DicomEditor.save_file(self.current_dataset, filepath)
                    messagebox.showinfo("成功", "文件已保存")
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {str(e)}")
        else:
            messagebox.showwarning("警告", "没有可保存的文件")
    
    def select_folder(self):
        """选择文件夹并扫描"""
        folder = filedialog.askdirectory(title="选择文件夹")
        if not folder:
            return
        
        def scan_thread():
            self.browser_tree.delete(*self.browser_tree.get_children())
            self.browser_data = []
            
            files = []
            for root, dirs, filenames in os.walk(folder):
                for filename in filenames:
                    if filename.lower().endswith('.dcm'):
                        files.append(os.path.join(root, filename))
            
            total = len(files)
            for idx, filepath in enumerate(files):
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    fix_dataset_encoding(ds)  # 修复中文乱码

                    data = (
                        filepath,
                        os.path.basename(filepath),
                        safe_str(getattr(ds, 'PatientName', ''), ds),
                        safe_str(getattr(ds, 'PatientID', ''), ds),
                        safe_str(getattr(ds, 'PatientSex', ''), ds),
                        safe_str(getattr(ds, 'PatientAge', ''), ds),
                        str(getattr(ds, 'StudyDate', '')),
                        str(getattr(ds, 'Modality', ''))
                    )
                    
                    self.browser_data.append((filepath, ds))
                    self.root.after(0, lambda d=data: self.browser_tree.insert('', 'end', values=d))
                    
                    progress = (idx + 1) / total * 100
                    self.root.after(0, lambda p=progress: self.browser_progress.config(value=p))
                    
                except Exception as e:
                    print(f"读取失败 {filepath}: {e}")
            
            self.root.after(0, lambda: messagebox.showinfo("完成", f"扫描完成，共{total}个文件"))
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def export_excel(self):
        """导出Excel"""
        if not self.browser_data:
            messagebox.showwarning("警告", "没有数据可导出")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="保存Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")]
        )
        
        if filepath:
            try:
                headers = ['路径', '文件名', '患者姓名', '病历号', '性别', '年龄', '检查日期', '模态']
                data = []
                
                for fp, ds in self.browser_data:
                    data.append([
                        fp,
                        os.path.basename(fp),
                        safe_str(getattr(ds, 'PatientName', ''), ds),
                        safe_str(getattr(ds, 'PatientID', ''), ds),
                        str(getattr(ds, 'PatientSex', '')),
                        str(getattr(ds, 'PatientAge', '')),
                        str(getattr(ds, 'StudyDate', '')),
                        str(getattr(ds, 'Modality', ''))
                    ])
                
                ExcelExporter.export(data, filepath, headers)
                messagebox.showinfo("成功", "Excel导出完成")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def batch_anonymize(self):
        """批量匿名化"""
        if not self.browser_data:
            messagebox.showwarning("警告", "没有数据")
            return
        
        if not messagebox.askyesno("确认", f"确定要匿名化 {len(self.browser_data)} 个文件吗？"):
            return
        
        def process():
            keep_digits = self.config.get('anonymize.keep_last_digits', 4)
            prefix = self.config.get('anonymize.prefix', 'ANON')
            
            for idx, (filepath, ds) in enumerate(self.browser_data):
                try:
                    DicomAnonymizer.anonymize(ds, prefix, keep_digits)
                    DicomEditor.save_file(ds, filepath)
                    
                    progress = (idx + 1) / len(self.browser_data) * 100
                    self.root.after(0, lambda p=progress: self.browser_progress.config(value=p))
                except Exception as e:
                    print(f"处理失败 {filepath}: {e}")
            
            self.root.after(0, lambda: messagebox.showinfo("完成", "批量匿名化完成"))
            self.root.after(0, self.select_folder)  # 刷新列表
        
        threading.Thread(target=process, daemon=True).start()
    
    def batch_calc_age(self):
        """批量计算年龄"""
        if not self.browser_data:
            messagebox.showwarning("警告", "没有数据")
            return
        
        def process():
            count = 0
            for idx, (filepath, ds) in enumerate(self.browser_data):
                try:
                    # 只处理没有年龄的
                    if not hasattr(ds, 'PatientAge') or not ds.PatientAge:
                        if hasattr(ds, 'PatientBirthDate'):
                            birth_date = ds.PatientBirthDate
                            study_date = getattr(ds, 'StudyDate', None)
                            age = calculate_age(birth_date, study_date)
                            if age:
                                ds.PatientAge = age
                                DicomEditor.save_file(ds, filepath)
                                count += 1
                    
                    progress = (idx + 1) / len(self.browser_data) * 100
                    self.root.after(0, lambda p=progress: self.browser_progress.config(value=p))
                except Exception as e:
                    print(f"处理失败 {filepath}: {e}")
            
            self.root.after(0, lambda: messagebox.showinfo("完成", f"已处理 {count} 个文件"))
            self.root.after(0, self.select_folder)  # 刷新列表
        
        threading.Thread(target=process, daemon=True).start()
    
    def batch_modify_uid(self):
        """批量修改UID"""
        if not self.browser_data:
            messagebox.showwarning("警告", "没有数据")
            return
        
        if not messagebox.askyesno("确认", f"确定要修改 {len(self.browser_data)} 个文件的UID吗？"):
            return
        
        def process():
            method = self.config.get('uid_strategy.method', 'append_timestamp')
            batch_modify_uids(self.browser_data, method)
            
            for idx, (filepath, ds) in enumerate(self.browser_data):
                try:
                    DicomEditor.save_file(ds, filepath)
                    
                    progress = (idx + 1) / len(self.browser_data) * 100
                    self.root.after(0, lambda p=progress: self.browser_progress.config(value=p))
                except Exception as e:
                    print(f"保存失败 {filepath}: {e}")
            
            self.root.after(0, lambda: messagebox.showinfo("完成", "批量修改UID完成"))
        
        threading.Thread(target=process, daemon=True).start()

    # ========== Worklist 事件处理 ==========

    def start_worklist_scp(self):
        """启动Worklist SCP服务"""
        try:
            ae = self.wl_scp_ae.get().strip()
            port = int(self.wl_scp_port.get())
            self.worklist_scp = WorklistSCP(ae_title=ae, port=port)
            self.worklist_scp.start()
            self.btn_start_wl.config(state='disabled')
            self.btn_stop_wl.config(state='normal')
            self.wl_scp_status.config(text="● 运行中", bootstyle="success")
            self.logger.info(f"Worklist SCP已启动 AE:{ae} 端口:{port}")
        except Exception as e:
            messagebox.showerror("错误", f"启动Worklist SCP失败: {str(e)}")
            self.logger.error(f"启动Worklist SCP失败: {e}")

    def stop_worklist_scp(self):
        """停止Worklist SCP服务"""
        if self.worklist_scp:
            try:
                self.worklist_scp.stop()
            except Exception:
                pass
            self.worklist_scp = None
        self.btn_start_wl.config(state='normal')
        self.btn_stop_wl.config(state='disabled')
        self.wl_scp_status.config(text="● 未运行", bootstyle="secondary")
        self.logger.info("Worklist SCP已停止")

    def add_worklist_item(self):
        """弹窗添加Worklist项目"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加Worklist项目")
        dialog.geometry("400x320")
        dialog.grab_set()

        fields = [
            ("患者ID", "PatientID", ""),
            ("患者姓名", "PatientName", ""),
            ("性别 (M/F)", "PatientSex", "M"),
            ("年龄 (如 035Y)", "PatientAge", ""),
            ("出生日期 (YYYYMMDD)", "PatientBirthDate", ""),
            ("模态", "Modality", "DR"),
            ("检查描述", "StudyDescription", ""),
            ("AccessionNumber", "AccessionNumber", ""),
        ]

        entries = {}
        for i, (label, key, default) in enumerate(fields):
            ttk_boot.Label(dialog, text=label + ":").grid(row=i, column=0, sticky='w', padx=10, pady=4)
            e = ttk_boot.Entry(dialog, width=25)
            e.insert(0, default)
            e.grid(row=i, column=1, padx=10, pady=4)
            entries[key] = e

        def save():
            item = {
                "PatientID": entries["PatientID"].get().strip(),
                "PatientName": entries["PatientName"].get().strip(),
                "PatientSex": entries["PatientSex"].get().strip(),
                "PatientAge": entries["PatientAge"].get().strip(),
                "PatientBirthDate": entries["PatientBirthDate"].get().strip(),
                "StudyDate": datetime.now().strftime('%Y%m%d'),
                "StudyTime": datetime.now().strftime('%H%M%S'),
                "Modality": entries["Modality"].get().strip(),
                "StudyDescription": entries["StudyDescription"].get().strip(),
                "AccessionNumber": entries["AccessionNumber"].get().strip(),
            }
            if not item["PatientID"] or not item["PatientName"]:
                messagebox.showwarning("警告", "患者ID和姓名不能为空", parent=dialog)
                return

            # 保存到SCP或直接写文件
            if self.worklist_scp:
                self.worklist_scp.add_worklist_item(item)
            else:
                # SCP未启动时直接写数据文件
                tmp = WorklistSCP()
                tmp.worklist_data = tmp.load_data()
                tmp.worklist_data.append(item)
                tmp.save_data()

            self.refresh_worklist_tree()
            dialog.destroy()

        ttk_boot.Button(dialog, text="保存", bootstyle="success", command=save).grid(
            row=len(fields), column=0, columnspan=2, pady=10)

    def delete_worklist_item(self):
        """删除选中的Worklist项目"""
        selected = self.wl_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要删除的项目")
            return
        if not messagebox.askyesno("确认", "确定要删除选中的项目吗？"):
            return

        index = self.wl_tree.index(selected[0])
        if self.worklist_scp:
            self.worklist_scp.delete_worklist_item(index)
        else:
            tmp = WorklistSCP()
            tmp.worklist_data = tmp.load_data()
            tmp.delete_worklist_item(index)

        self.refresh_worklist_tree()

    def generate_worklist_test_data(self):
        """生成10条测试数据"""
        if self.worklist_scp:
            self.worklist_scp.generate_test_data(10)
        else:
            tmp = WorklistSCP()
            tmp.worklist_data = tmp.load_data()
            tmp.generate_test_data(10)

        self.refresh_worklist_tree()
        messagebox.showinfo("成功", "已生成10条测试数据")

    def refresh_worklist_tree(self):
        """刷新Worklist数据表格"""
        self.wl_tree.delete(*self.wl_tree.get_children())

        if self.worklist_scp:
            data = self.worklist_scp.worklist_data
        else:
            tmp = WorklistSCP()
            data = tmp.load_data()

        for item in data:
            self.wl_tree.insert('', 'end', values=(
                item.get('PatientID', ''),
                item.get('PatientName', ''),
                item.get('PatientSex', ''),
                item.get('PatientAge', ''),
                item.get('StudyDate', ''),
                item.get('StudyTime', ''),
                item.get('Modality', ''),
                item.get('StudyDescription', ''),
                item.get('AccessionNumber', ''),
            ))

    def clear_worklist_data(self):
        """清空所有Worklist数据"""
        if not messagebox.askyesno("确认", "确定要清空所有Worklist数据吗？"):
            return

        if self.worklist_scp:
            self.worklist_scp.worklist_data = []
            self.worklist_scp.save_data()
        else:
            tmp = WorklistSCP()
            tmp.worklist_data = []
            tmp.save_data()

        self.refresh_worklist_tree()

    def query_worklist(self):
        """SCU查询Worklist"""
        host = self.wl_scu_host.get().strip()
        port = int(self.wl_scu_port.get())
        ae = self.wl_scu_ae.get().strip()
        pid = self.wl_query_pid.get().strip()
        name = self.wl_query_name.get().strip()
        modality = self.wl_query_modality.get().strip()

        def query_thread():
            try:
                scu = WorklistSCU()
                results = scu.query(host, port, ae,
                                    patient_id=pid or None,
                                    patient_name=name or None,
                                    modality=modality or None)

                self.root.after(0, lambda: self._show_worklist_results(results))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("查询失败", str(e)))
                self.logger.error(f"Worklist查询失败: {e}")

        threading.Thread(target=query_thread, daemon=True).start()

    def _show_worklist_results(self, results):
        """显示查询结果"""
        self.wl_result_tree.delete(*self.wl_result_tree.get_children())
        for ds in results:
            sps = ds.ScheduledProcedureStepSequence[0] if hasattr(ds, 'ScheduledProcedureStepSequence') and ds.ScheduledProcedureStepSequence else None
            self.wl_result_tree.insert('', 'end', values=(
                str(getattr(ds, 'PatientID', '')),
                str(getattr(ds, 'PatientName', '')),
                str(getattr(sps, 'Modality', '')) if sps else '',
                str(getattr(sps, 'ScheduledProcedureStepStartDate', '')) if sps else '',
                str(getattr(sps, 'ScheduledProcedureStepDescription', '')) if sps else '',
                str(getattr(ds, 'AccessionNumber', '')),
            ))
        if not results:
            messagebox.showinfo("查询结果", "未找到匹配的Worklist项目")


def main():
    root = ttk_boot.Window(themename="cosmo")
    app = DicomToolApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()


# -*- coding: utf-8 -*-
"""主窗口界面"""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTabWidget, QTextEdit, QLabel,
                             QLineEdit, QFileDialog, QListWidget, QGroupBox,
                             QSpinBox, QMessageBox, QTableWidget, QTableWidgetItem,
                             QComboBox, QCheckBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                             QHeaderView, QProgressBar, QStatusBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dicom.scu import DicomSCU
from dicom.scp import DicomSCP
from dicom.editor import DicomEditor
from dicom.anonymizer import DicomAnonymizer
from dicom.worklist import WorklistSCU, WorklistSCP
from dicom.query_retrieve import QueryRetrieveSCU
from dicom.print_scu import PrintSCU
from dicom.validator import DicomValidator
from utils.uid_generator import modify_uids
from utils.age_calculator import calculate_age
from utils.excel_exporter import export_to_excel
from utils.config_manager import ConfigManager

class SCPThread(QThread):
    """SCP服务线程"""
    log_signal = pyqtSignal(str)
    
    def __init__(self, scp):
        super().__init__()
        self.scp = scp
        self.running = True
    
    def run(self):
        self.scp.start()
    
    def stop(self):
        self.running = False
        self.scp.stop()

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.scp = None
        self.scp_thread = None
        self.config_manager = ConfigManager()
        self.current_dataset = None
        self.current_filepath = None
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("DICOM运维工具 v2.0")
        self.setGeometry(50, 50, 1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self.create_send_tab(), "📤 发送")
        tabs.addTab(self.create_receive_tab(), "📥 接收")
        tabs.addTab(self.create_forward_tab(), "🔄 转发")
        tabs.addTab(self.create_worklist_tab(), "📋 Worklist")
        tabs.addTab(self.create_query_tab(), "🔍 查询检索")
        tabs.addTab(self.create_editor_tab(), "✏️ 编辑器")
        tabs.addTab(self.create_batch_tab(), "⚙️ 批量处理")
        tabs.addTab(self.create_export_tab(), "📊 导出表格")
        tabs.addTab(self.create_tools_tab(), "🛠️ 工具")
        tabs.addTab(self.create_config_tab(), "⚙️ 配置")
        
        layout.addWidget(tabs)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")
    
    def create_send_tab(self):
        """创建发送标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 远程配置
        config_group = QGroupBox("目标节点")
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("预设:"))
        self.send_preset = QComboBox()
        self.send_preset.addItems(self.config_manager.get_preset_names())
        self.send_preset.currentTextChanged.connect(self.load_send_preset)
        config_layout.addWidget(self.send_preset)
        config_layout.addWidget(QLabel("AE:"))
        self.remote_ae = QLineEdit("REMOTE_AE")
        self.remote_ae.setMaximumWidth(120)
        config_layout.addWidget(self.remote_ae)
        config_layout.addWidget(QLabel("Host:"))
        self.remote_host = QLineEdit("127.0.0.1")
        self.remote_host.setMaximumWidth(120)
        config_layout.addWidget(self.remote_host)
        config_layout.addWidget(QLabel("Port:"))
        self.remote_port = QSpinBox()
        self.remote_port.setRange(1, 65535)
        self.remote_port.setValue(104)
        self.remote_port.setMaximumWidth(80)
        config_layout.addWidget(self.remote_port)
        btn_echo = QPushButton("Echo测试")
        btn_echo.clicked.connect(self.test_echo)
        config_layout.addWidget(btn_echo)
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 文件列表和操作按钮
        btn_layout = QHBoxLayout()
        btn_add_files = QPushButton("添加文件")
        btn_add_files.clicked.connect(self.add_files)
        btn_add_folder = QPushButton("添加文件夹")
        btn_add_folder.clicked.connect(self.add_folder)
        btn_clear = QPushButton("清空列表")
        btn_clear.clicked.connect(lambda: self.file_list.clear())
        btn_send = QPushButton("发送全部")
        btn_send.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_send.clicked.connect(self.send_files)
        btn_layout.addWidget(btn_add_files)
        btn_layout.addWidget(btn_add_folder)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_send)
        layout.addLayout(btn_layout)
        
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        
        # 进度条
        self.send_progress = QProgressBar()
        layout.addWidget(self.send_progress)
        
        return widget
    
    def create_receive_tab(self):
        """创建接收标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # SCP配置
        config_group = QGroupBox("接收服务配置")
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("AE Title:"))
        self.local_ae = QLineEdit("DICOM_TOOL")
        self.local_ae.setMaximumWidth(120)
        config_layout.addWidget(self.local_ae)
        config_layout.addWidget(QLabel("端口:"))
        self.local_port = QSpinBox()
        self.local_port.setRange(1, 65535)
        self.local_port.setValue(11112)
        self.local_port.setMaximumWidth(80)
        config_layout.addWidget(self.local_port)
        config_layout.addWidget(QLabel("存储路径:"))
        self.storage_path = QLineEdit("./storage")
        config_layout.addWidget(self.storage_path)
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(self.browse_storage_path)
        config_layout.addWidget(btn_browse)
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        self.btn_start_scp = QPushButton("▶ 启动服务")
        self.btn_start_scp.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_start_scp.clicked.connect(self.start_scp)
        self.btn_stop_scp = QPushButton("⏹ 停止服务")
        self.btn_stop_scp.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.btn_stop_scp.clicked.connect(self.stop_scp)
        self.btn_stop_scp.setEnabled(False)
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.clicked.connect(lambda: self.log_text.clear())
        btn_layout.addWidget(self.btn_start_scp)
        btn_layout.addWidget(self.btn_stop_scp)
        btn_layout.addWidget(btn_clear_log)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)
        
        return widget
    
    def create_forward_tab(self):
        """创建转发标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("接收到的DICOM数据自动转发到指定节点")
        layout.addWidget(info)
        
        # 转发配置
        config_group = QGroupBox("转发规则")
        config_layout = QVBoxLayout()
        
        self.forward_enabled = QCheckBox("启用自动转发")
        config_layout.addWidget(self.forward_enabled)
        
        # 转发目标列表
        self.forward_targets = QTableWidget()
        self.forward_targets.setColumnCount(4)
        self.forward_targets.setHorizontalHeaderLabels(["AE Title", "Host", "Port", "启用"])
        self.forward_targets.horizontalHeader().setStretchLastSection(True)
        config_layout.addWidget(self.forward_targets)
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("添加目标")
        btn_add.clicked.connect(self.add_forward_target)
        btn_remove = QPushButton("删除选中")
        btn_remove.clicked.connect(self.remove_forward_target)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        config_layout.addLayout(btn_layout)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        return widget
    
    def create_worklist_tab(self):
        """创建Worklist标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Worklist查询
        query_group = QGroupBox("Worklist查询 (SCU)")
        query_layout = QVBoxLayout()
        
        # 服务器配置
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("服务器:"))
        self.wl_server = QComboBox()
        self.wl_server.addItems(self.config_manager.get_preset_names())
        server_layout.addWidget(self.wl_server)
        server_layout.addStretch()
        query_layout.addLayout(server_layout)
        
        # 查询条件
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("患者ID:"))
        self.wl_patient_id = QLineEdit()
        search_layout.addWidget(self.wl_patient_id)
        search_layout.addWidget(QLabel("患者姓名:"))
        self.wl_patient_name = QLineEdit()
        search_layout.addWidget(self.wl_patient_name)
        btn_query = QPushButton("查询")
        btn_query.clicked.connect(self.query_worklist)
        search_layout.addWidget(btn_query)
        query_layout.addLayout(search_layout)
        
        # 结果表格
        self.wl_results = QTableWidget()
        self.wl_results.setColumnCount(6)
        self.wl_results.setHorizontalHeaderLabels(["患者ID", "患者姓名", "检查日期", "检查时间", "模态", "描述"])
        self.wl_results.horizontalHeader().setStretchLastSection(True)
        query_layout.addWidget(self.wl_results)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # Worklist服务
        service_group = QGroupBox("Worklist服务 (SCP)")
        service_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_start_wl = QPushButton("启动Worklist服务")
        self.btn_start_wl.clicked.connect(self.start_worklist_scp)
        self.btn_stop_wl = QPushButton("停止Worklist服务")
        self.btn_stop_wl.clicked.connect(self.stop_worklist_scp)
        self.btn_stop_wl.setEnabled(False)
        btn_layout.addWidget(self.btn_start_wl)
        btn_layout.addWidget(self.btn_stop_wl)
        btn_layout.addStretch()
        service_layout.addLayout(btn_layout)
        
        service_group.setLayout(service_layout)
        layout.addWidget(service_group)
        
        return widget
    
    def create_query_tab(self):
        """创建查询检索标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 服务器配置
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("PACS服务器:"))
        self.qr_server = QComboBox()
        self.qr_server.addItems(self.config_manager.get_preset_names())
        config_layout.addWidget(self.qr_server)
        config_layout.addStretch()
        layout.addLayout(config_layout)
        
        # 查询条件
        search_group = QGroupBox("查询条件")
        search_layout = QVBoxLayout()
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("患者ID:"))
        self.qr_patient_id = QLineEdit()
        row1.addWidget(self.qr_patient_id)
        row1.addWidget(QLabel("患者姓名:"))
        self.qr_patient_name = QLineEdit()
        row1.addWidget(self.qr_patient_name)
        search_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("检查日期:"))
        self.qr_study_date = QLineEdit()
        self.qr_study_date.setPlaceholderText("YYYYMMDD")
        row2.addWidget(self.qr_study_date)
        row2.addWidget(QLabel("模态:"))
        self.qr_modality = QComboBox()
        self.qr_modality.addItems(["全部", "CR", "DR", "CT", "MR", "US", "XA"])
        row2.addWidget(self.qr_modality)
        btn_search = QPushButton("查询")
        btn_search.clicked.connect(self.query_pacs)
        row2.addWidget(btn_search)
        search_layout.addLayout(row2)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # 结果表格
        self.qr_results = QTableWidget()
        self.qr_results.setColumnCount(7)
        self.qr_results.setHorizontalHeaderLabels(["患者ID", "患者姓名", "检查日期", "模态", "描述", "影像数", "操作"])
        self.qr_results.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.qr_results)
        
        return widget
    
    def create_editor_tab(self):
        """创建编辑器标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 文件操作
        btn_layout = QHBoxLayout()
        btn_open = QPushButton("打开DCM文件")
        btn_open.clicked.connect(self.open_dcm_file)
        btn_anon = QPushButton("匿名化")
        btn_anon.clicked.connect(self.anonymize_file)
        btn_uid = QPushButton("修改UID")
        btn_uid.clicked.connect(self.modify_uid)
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_dcm_file)
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_anon)
        btn_layout.addWidget(btn_uid)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        # 标签显示
        self.tag_text = QTextEdit()
        layout.addWidget(self.tag_text)
        
        self.current_dataset = None
        self.current_filepath = None
        
        return widget
    
    def add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择DICOM文件", "", "DICOM Files (*.dcm)")
        self.file_list.addItems(files)
    
    def send_files(self):
        """发送文件"""
        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        if not files:
            return
        
        scu = DicomSCU()
        results = scu.send_batch(files, self.remote_host.text(), 
                                self.remote_port.value(), self.remote_ae.text())
        
        success_count = sum(1 for _, success in results if success)
        QMessageBox.information(self, "发送完成", f"成功: {success_count}/{len(files)}")
    
    def start_scp(self):
        """启动SCP"""
        self.scp = DicomSCP(port=self.local_port.value())
        self.scp.start()
        self.btn_start_scp.setEnabled(False)
        self.btn_stop_scp.setEnabled(True)
        self.log_text.append(f"SCP服务已启动在端口 {self.local_port.value()}")
    
    def stop_scp(self):
        """停止SCP"""
        if self.scp:
            self.scp.stop()
            self.scp = None
        self.btn_start_scp.setEnabled(True)
        self.btn_stop_scp.setEnabled(False)
        self.log_text.append("SCP服务已停止")
    
    def open_dcm_file(self):
        """打开DCM文件"""
        filepath, _ = QFileDialog.getOpenFileName(self, "打开DICOM文件", "", "DICOM Files (*.dcm)")
        if filepath:
            self.current_dataset = DicomEditor.load_file(filepath)
            self.current_filepath = filepath
            self.tag_text.setText(str(self.current_dataset))
    
    def anonymize_file(self):
        """匿名化"""
        if self.current_dataset:
            self.current_dataset = DicomAnonymizer.anonymize(self.current_dataset)
            self.tag_text.setText(str(self.current_dataset))
    
    def modify_uid(self):
        """修改UID"""
        if self.current_dataset:
            self.current_dataset = modify_uids(self.current_dataset)
            self.tag_text.setText(str(self.current_dataset))
    
    def save_dcm_file(self):
        """保存文件"""
        if self.current_dataset:
            filepath, _ = QFileDialog.getSaveFileName(self, "保存DICOM文件", "", "DICOM Files (*.dcm)")
            if filepath:
                DicomEditor.save_file(self.current_dataset, filepath)
                QMessageBox.information(self, "保存成功", "文件已保存")

    
    def create_editor_tab(self):
        """创建编辑器标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧：文件树和操作
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_layout = QHBoxLayout()
        btn_open = QPushButton("打开文件")
        btn_open.clicked.connect(self.open_dcm_file)
        btn_open_folder = QPushButton("打开文件夹")
        btn_open_folder.clicked.connect(self.open_dcm_folder)
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_open_folder)
        left_layout.addLayout(btn_layout)
        
        self.file_tree = QListWidget()
        self.file_tree.itemClicked.connect(self.load_selected_dcm)
        left_layout.addWidget(self.file_tree)
        
        left_panel.setMaximumWidth(300)
        layout.addWidget(left_panel)
        
        # 右侧：标签显示和编辑
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        btn_anon = QPushButton("匿名化")
        btn_anon.clicked.connect(self.anonymize_file)
        btn_uid = QPushButton("修改UID")
        btn_uid.clicked.connect(self.modify_uid)
        btn_validate = QPushButton("验证修复")
        btn_validate.clicked.connect(self.validate_file)
        btn_calc_age = QPushButton("计算年龄")
        btn_calc_age.clicked.connect(self.calculate_patient_age)
        btn_save = QPushButton("保存")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white;")
        btn_save.clicked.connect(self.save_dcm_file)
        btn_save_as = QPushButton("另存为")
        btn_save_as.clicked.connect(self.save_dcm_file_as)
        action_layout.addWidget(btn_anon)
        action_layout.addWidget(btn_uid)
        action_layout.addWidget(btn_validate)
        action_layout.addWidget(btn_calc_age)
        action_layout.addStretch()
        action_layout.addWidget(btn_save)
        action_layout.addWidget(btn_save_as)
        right_layout.addLayout(action_layout)
        
        # 标签树形显示
        self.tag_tree = QTreeWidget()
        self.tag_tree.setHeaderLabels(["标签", "值", "VR", "描述"])
        self.tag_tree.setColumnWidth(0, 150)
        self.tag_tree.setColumnWidth(1, 300)
        self.tag_tree.setFont(QFont("Consolas", 9))
        right_layout.addWidget(self.tag_tree)
        
        layout.addWidget(right_panel)
        
        self.current_dataset = None
        self.current_filepath = None
        self.dcm_files = []
        
        return widget
    
    def create_batch_tab(self):
        """创建批量处理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("添加文件夹")
        btn_add.clicked.connect(self.batch_add_folder)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(lambda: self.batch_file_list.clear())
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)
        
        self.batch_file_list = QListWidget()
        file_layout.addWidget(self.batch_file_list)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 批量操作
        action_group = QGroupBox("批量操作")
        action_layout = QVBoxLayout()
        
        row1 = QHBoxLayout()
        btn_batch_anon = QPushButton("批量匿名化")
        btn_batch_anon.clicked.connect(self.batch_anonymize)
        btn_batch_uid = QPushButton("批量修改UID")
        btn_batch_uid.clicked.connect(self.batch_modify_uid)
        btn_batch_validate = QPushButton("批量验证修复")
        btn_batch_validate.clicked.connect(self.batch_validate)
        row1.addWidget(btn_batch_anon)
        row1.addWidget(btn_batch_uid)
        row1.addWidget(btn_batch_validate)
        action_layout.addLayout(row1)
        
        # 批量修改标签
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("批量修改标签:"))
        self.batch_tag_name = QLineEdit()
        self.batch_tag_name.setPlaceholderText("如: InstitutionName")
        row2.addWidget(self.batch_tag_name)
        row2.addWidget(QLabel("新值:"))
        self.batch_tag_value = QLineEdit()
        row2.addWidget(self.batch_tag_value)
        btn_batch_modify = QPushButton("执行修改")
        btn_batch_modify.clicked.connect(self.batch_modify_tag)
        row2.addWidget(btn_batch_modify)
        action_layout.addLayout(row2)
        
        self.batch_progress = QProgressBar()
        action_layout.addWidget(self.batch_progress)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        return widget
    
    def create_export_tab(self):
        """创建导出表格标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("选择包含DICOM文件的文件夹，自动扫描并导出为Excel表格")
        layout.addWidget(info)
        
        # 文件夹选择
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("源文件夹:"))
        self.export_folder = QLineEdit()
        folder_layout.addWidget(self.export_folder)
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(self.select_export_folder)
        folder_layout.addWidget(btn_browse)
        layout.addLayout(folder_layout)
        
        # 导出选项
        options_group = QGroupBox("导出字段")
        options_layout = QVBoxLayout()
        
        self.export_fields = {}
        fields = [
            ("文件路径", "filepath", True),
            ("文件名", "filename", True),
            ("患者姓名", "PatientName", True),
            ("患者ID", "PatientID", True),
            ("患者性别", "PatientSex", True),
            ("患者年龄", "PatientAge", True),
            ("患者生日", "PatientBirthDate", True),
            ("检查日期", "StudyDate", True),
            ("检查时间", "StudyTime", True),
            ("检查描述", "StudyDescription", True),
            ("序列描述", "SeriesDescription", True),
            ("模态", "Modality", True),
            ("设备厂商", "Manufacturer", False),
            ("设备型号", "ManufacturerModelName", False),
            ("机构名称", "InstitutionName", False),
            ("检查医生", "PerformingPhysicianName", False),
        ]
        
        row_layout = QHBoxLayout()
        for i, (label, field, checked) in enumerate(fields):
            cb = QCheckBox(label)
            cb.setChecked(checked)
            self.export_fields[field] = cb
            row_layout.addWidget(cb)
            if (i + 1) % 4 == 0:
                options_layout.addLayout(row_layout)
                row_layout = QHBoxLayout()
        if row_layout.count() > 0:
            options_layout.addLayout(row_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 导出按钮
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("导出到Excel")
        btn_export.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        btn_export.clicked.connect(self.export_to_excel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_export)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 进度
        self.export_progress = QProgressBar()
        layout.addWidget(self.export_progress)
        
        # 预览
        self.export_preview = QTableWidget()
        layout.addWidget(QLabel("预览 (前100条):"))
        layout.addWidget(self.export_preview)
        
        return widget
    
    def create_tools_tab(self):
        """创建工具标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Echo测试工具
        echo_group = QGroupBox("DICOM Echo 连通性测试")
        echo_layout = QVBoxLayout()
        
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("预设:"))
        self.echo_preset = QComboBox()
        self.echo_preset.addItems(self.config_manager.get_preset_names())
        config_layout.addWidget(self.echo_preset)
        config_layout.addWidget(QLabel("AE:"))
        self.echo_ae = QLineEdit("REMOTE_AE")
        config_layout.addWidget(self.echo_ae)
        config_layout.addWidget(QLabel("Host:"))
        self.echo_host = QLineEdit("127.0.0.1")
        config_layout.addWidget(self.echo_host)
        config_layout.addWidget(QLabel("Port:"))
        self.echo_port = QSpinBox()
        self.echo_port.setRange(1, 65535)
        self.echo_port.setValue(104)
        config_layout.addWidget(self.echo_port)
        btn_test = QPushButton("测试连接")
        btn_test.clicked.connect(self.test_echo_tool)
        config_layout.addWidget(btn_test)
        echo_layout.addLayout(config_layout)
        
        self.echo_result = QTextEdit()
        self.echo_result.setReadOnly(True)
        self.echo_result.setMaximumHeight(150)
        echo_layout.addWidget(self.echo_result)
        
        echo_group.setLayout(echo_layout)
        layout.addWidget(echo_group)
        
        # DICOM打印
        print_group = QGroupBox("DICOM打印")
        print_layout = QVBoxLayout()
        
        print_config = QHBoxLayout()
        print_config.addWidget(QLabel("打印机AE:"))
        self.print_ae = QLineEdit("PRINT_SCP")
        print_config.addWidget(self.print_ae)
        print_config.addWidget(QLabel("Host:"))
        self.print_host = QLineEdit("127.0.0.1")
        print_config.addWidget(self.print_host)
        print_config.addWidget(QLabel("Port:"))
        self.print_port = QSpinBox()
        self.print_port.setRange(1, 65535)
        self.print_port.setValue(104)
        print_config.addWidget(self.print_port)
        print_layout.addLayout(print_config)
        
        print_btn_layout = QHBoxLayout()
        btn_select_print = QPushButton("选择DICOM文件")
        btn_select_print.clicked.connect(self.select_print_file)
        btn_print = QPushButton("发送打印")
        btn_print.clicked.connect(self.send_print)
        print_btn_layout.addWidget(btn_select_print)
        print_btn_layout.addWidget(btn_print)
        print_layout.addLayout(print_btn_layout)
        
        self.print_file = QLineEdit()
        self.print_file.setReadOnly(True)
        print_layout.addWidget(self.print_file)
        
        print_group.setLayout(print_layout)
        layout.addWidget(print_group)
        
        # DR模拟器
        dr_group = QGroupBox("DR设备模拟器")
        dr_layout = QVBoxLayout()
        
        dr_info = QLabel("使用预设的DR设备参数模板生成DICOM文件")
        dr_layout.addWidget(dr_info)
        
        dr_template_layout = QHBoxLayout()
        dr_template_layout.addWidget(QLabel("设备模板:"))
        self.dr_template = QComboBox()
        self.dr_template.addItems(["通用DR", "GE DR", "Siemens DR", "Philips DR", "自定义"])
        dr_template_layout.addWidget(self.dr_template)
        btn_load_template = QPushButton("加载模板")
        btn_load_template.clicked.connect(self.load_dr_template)
        dr_template_layout.addWidget(btn_load_template)
        dr_layout.addLayout(dr_template_layout)
        
        dr_group.setLayout(dr_layout)
        layout.addWidget(dr_group)
        
        layout.addStretch()
        
        return widget
    
    def create_config_tab(self):
        """创建配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 预设配置管理
        preset_group = QGroupBox("DICOM节点预设配置")
        preset_layout = QVBoxLayout()
        
        self.preset_table = QTableWidget()
        self.preset_table.setColumnCount(4)
        self.preset_table.setHorizontalHeaderLabels(["名称", "AE Title", "Host", "Port"])
        self.preset_table.horizontalHeader().setStretchLastSection(True)
        self.load_presets()
        preset_layout.addWidget(self.preset_table)
        
        btn_layout = QHBoxLayout()
        btn_add_preset = QPushButton("添加")
        btn_add_preset.clicked.connect(self.add_preset)
        btn_edit_preset = QPushButton("编辑")
        btn_edit_preset.clicked.connect(self.edit_preset)
        btn_del_preset = QPushButton("删除")
        btn_del_preset.clicked.connect(self.delete_preset)
        btn_layout.addWidget(btn_add_preset)
        btn_layout.addWidget(btn_edit_preset)
        btn_layout.addWidget(btn_del_preset)
        btn_layout.addStretch()
        preset_layout.addLayout(btn_layout)
        
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # 日志配置
        log_group = QGroupBox("日志设置")
        log_layout = QVBoxLayout()
        
        self.log_enabled = QCheckBox("启用详细日志")
        self.log_enabled.setChecked(True)
        log_layout.addWidget(self.log_enabled)
        
        log_path_layout = QHBoxLayout()
        log_path_layout.addWidget(QLabel("日志路径:"))
        self.log_path = QLineEdit("./logs")
        log_path_layout.addWidget(self.log_path)
        log_layout.addLayout(log_path_layout)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        
        return widget

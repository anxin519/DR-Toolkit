# -*- coding: utf-8 -*-
"""主窗口界面 - Tkinter版本"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import ttkbootstrap as ttk_boot
from ttkbootstrap.constants import *
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dicom.scu import DicomSCU
from dicom.scp import DicomSCP
from dicom.editor import DicomEditor
from dicom.anonymizer import DicomAnonymizer
from dicom.worklist import WorklistSCU
from utils.uid_generator import modify_uids
from utils.age_calculator import calculate_age

class MainWindow:
    """主窗口"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM运维工具")
        self.root.geometry("1100x750")
        
        self.scp = None
        self.current_dataset = None
        self.current_filepath = None
        self.file_paths = []
        
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        # 创建标签页
        self.notebook = ttk_boot.Notebook(self.root, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 添加各个标签页
        self.notebook.add(self.create_send_tab(), text="📤 发送")
        self.notebook.add(self.create_receive_tab(), text="📥 接收")
        self.notebook.add(self.create_worklist_tab(), text="📋 Worklist")
        self.notebook.add(self.create_editor_tab(), text="✏️ 编辑器")
        self.notebook.add(self.create_about_tab(), text="ℹ️ 关于")
    
    def create_send_tab(self):
        """创建发送标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 远程配置组
        config_frame = ttk_boot.Labelframe(frame, text="远程DICOM节点配置", bootstyle="info", padding=10)
        config_frame.pack(fill='x', padx=10, pady=10)
        
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
        self.local_ae.insert(0, "DICOM_TOOL")
        self.local_ae.pack(side='left', padx=5)
        
        ttk_boot.Label(row1, text="端口:", width=8).pack(side='left', padx=5)
        self.local_port = ttk_boot.Spinbox(row1, from_=1, to=65535, width=10)
        self.local_port.set(11112)
        self.local_port.pack(side='left', padx=5)
        
        ttk_boot.Label(row1, text="存储路径:", width=10).pack(side='left', padx=5)
        self.storage_path = ttk_boot.Entry(row1, width=30)
        self.storage_path.insert(0, "./storage")
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
    
    def create_worklist_tab(self):
        """创建Worklist标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        info_frame = ttk_boot.Frame(frame)
        info_frame.pack(fill='x', padx=10, pady=20)
        
        ttk_boot.Label(info_frame, text="Worklist查询功能", 
                      font=('Arial', 12, 'bold')).pack()
        ttk_boot.Label(info_frame, text="用于查询和响应DICOM Worklist请求", 
                      font=('Arial', 10)).pack(pady=5)
        
        return frame
    
    def create_editor_tab(self):
        """创建编辑器标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        # 操作按钮
        btn_frame = ttk_boot.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk_boot.Button(btn_frame, text="打开DCM文件", bootstyle="primary", 
                       command=self.open_dcm_file).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="匿名化", bootstyle="info", 
                       command=self.anonymize_file).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="修改UID", bootstyle="info", 
                       command=self.modify_uid).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="计算年龄", bootstyle="info", 
                       command=self.calculate_age).pack(side='left', padx=5)
        ttk_boot.Button(btn_frame, text="保存", bootstyle="success", 
                       command=self.save_dcm_file).pack(side='right', padx=5)
        
        # 标签显示
        tag_frame = ttk_boot.Labelframe(frame, text="DICOM标签信息", bootstyle="secondary", padding=10)
        tag_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.tag_text = scrolledtext.ScrolledText(tag_frame, font=('Consolas', 9), 
                                                  wrap='word')
        self.tag_text.pack(fill='both', expand=True)
        
        return frame
    
    def create_about_tab(self):
        """创建关于标签页"""
        frame = ttk_boot.Frame(self.notebook)
        
        content = ttk_boot.Frame(frame)
        content.pack(expand=True)
        
        ttk_boot.Label(content, text="DICOM运维工具", 
                      font=('Arial', 18, 'bold')).pack(pady=20)
        ttk_boot.Label(content, text="版本: 1.0.0", 
                      font=('Arial', 12)).pack(pady=5)
        ttk_boot.Label(content, text="用于日常DICOM设备运维", 
                      font=('Arial', 10)).pack(pady=5)
        
        features = """
        主要功能：
        • DICOM批量收发 (C-STORE)
        • DICOM接收服务 (SCP)
        • Worklist查询与响应
        • DCM文件读取与编辑
        • 患者信息匿名化
        • UID自动生成与修改
        • 年龄自动计算
        """
        
        ttk_boot.Label(content, text=features, font=('Arial', 10), 
                      justify='left').pack(pady=20)
        
        return frame
    
    # 事件处理方法
    def add_files(self):
        """添加文件"""
        files = filedialog.askopenfilenames(
            title="选择DICOM文件",
            filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
        )
        for file in files:
            if file not in self.file_paths:
                self.file_paths.append(file)
                self.file_listbox.insert('end', file)
    
    def add_folder(self):
        """添加文件夹"""
        folder = filedialog.askdirectory(title="选择包含DICOM文件的文件夹")
        if folder:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.dcm'):
                        filepath = os.path.join(root, file)
                        if filepath not in self.file_paths:
                            self.file_paths.append(filepath)
                            self.file_listbox.insert('end', filepath)
    
    def clear_files(self):
        """清空文件列表"""
        self.file_listbox.delete(0, 'end')
        self.file_paths.clear()
    
    def send_files(self):
        """发送文件"""
        if not self.file_paths:
            messagebox.showwarning("警告", "请先添加文件")
            return
        
        try:
            scu = DicomSCU()
            results = scu.send_batch(
                self.file_paths,
                self.remote_host.get(),
                int(self.remote_port.get()),
                self.remote_ae.get()
            )
            
            success_count = sum(1 for _, success in results if success)
            messagebox.showinfo("发送完成", f"成功: {success_count}/{len(self.file_paths)}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {str(e)}")
    
    def browse_storage(self):
        """浏览存储路径"""
        folder = filedialog.askdirectory(title="选择存储路径")
        if folder:
            self.storage_path.delete(0, 'end')
            self.storage_path.insert(0, folder)
    
    def start_scp(self):
        """启动SCP"""
        try:
            port = int(self.local_port.get())
            storage = self.storage_path.get()
            
            self.scp = DicomSCP(ae_title=self.local_ae.get(), port=port, storage_path=storage)
            self.scp.start()
            
            self.btn_start_scp.config(state='disabled')
            self.btn_stop_scp.config(state='normal')
            self.log_text.insert('end', f"✓ SCP服务已启动在端口 {port}\n")
            self.log_text.insert('end', f"✓ 存储路径: {storage}\n")
            self.log_text.see('end')
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
    
    def stop_scp(self):
        """停止SCP"""
        if self.scp:
            self.scp.stop()
            self.scp = None
        
        self.btn_start_scp.config(state='normal')
        self.btn_stop_scp.config(state='disabled')
        self.log_text.insert('end', "✓ SCP服务已停止\n")
        self.log_text.see('end')
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', 'end')
    
    def open_dcm_file(self):
        """打开DCM文件"""
        filepath = filedialog.askopenfilename(
            title="打开DICOM文件",
            filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                self.current_dataset = DicomEditor.load_file(filepath)
                self.current_filepath = filepath
                self.tag_text.delete('1.0', 'end')
                self.tag_text.insert('1.0', str(self.current_dataset))
            except Exception as e:
                messagebox.showerror("错误", f"打开文件失败: {str(e)}")
    
    def anonymize_file(self):
        """匿名化"""
        if self.current_dataset:
            self.current_dataset = DicomAnonymizer.anonymize(self.current_dataset)
            self.tag_text.delete('1.0', 'end')
            self.tag_text.insert('1.0', str(self.current_dataset))
            messagebox.showinfo("成功", "匿名化完成")
        else:
            messagebox.showwarning("警告", "请先打开文件")
    
    def modify_uid(self):
        """修改UID"""
        if self.current_dataset:
            self.current_dataset = modify_uids(self.current_dataset)
            self.tag_text.delete('1.0', 'end')
            self.tag_text.insert('1.0', str(self.current_dataset))
            messagebox.showinfo("成功", "UID已修改")
        else:
            messagebox.showwarning("警告", "请先打开文件")
    
    def calculate_age(self):
        """计算年龄"""
        if self.current_dataset:
            if hasattr(self.current_dataset, 'PatientBirthDate'):
                birth_date = self.current_dataset.PatientBirthDate
                study_date = getattr(self.current_dataset, 'StudyDate', None)
                age = calculate_age(birth_date, study_date)
                if age:
                    self.current_dataset.PatientAge = age
                    self.tag_text.delete('1.0', 'end')
                    self.tag_text.insert('1.0', str(self.current_dataset))
                    messagebox.showinfo("成功", f"年龄已计算: {age}")
                else:
                    messagebox.showerror("错误", "无法计算年龄")
            else:
                messagebox.showwarning("警告", "文件中没有出生日期信息")
        else:
            messagebox.showwarning("警告", "请先打开文件")
    
    def save_dcm_file(self):
        """保存文件"""
        if self.current_dataset:
            filepath = filedialog.asksaveasfilename(
                title="保存DICOM文件",
                defaultextension=".dcm",
                filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
            )
            if filepath:
                try:
                    DicomEditor.save_file(self.current_dataset, filepath)
                    messagebox.showinfo("成功", "文件已保存")
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {str(e)}")
        else:
            messagebox.showwarning("警告", "没有可保存的文件")

def main():
    root = ttk_boot.Window(themename="cosmo")  # 可选主题: cosmo, flatly, litera, minty, lumen, sandstone, yeti, pulse, united, morph, journal, darkly, superhero, solar, cyborg, vapor, simplex, cerculean
    app = MainWindow(root)
    root.mainloop()

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Worklist标签页"""
import ttkbootstrap as ttk_boot
from tkinter import messagebox
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def create_worklist_tab(parent):
    """创建Worklist标签页"""
    frame = ttk_boot.Frame(parent.notebook)
    
    # Worklist查询 (SCU)
    query_frame = ttk_boot.Labelframe(frame, text="Worklist查询 (SCU)", bootstyle="info", padding=10)
    query_frame.pack(fill='x', padx=10, pady=10)
    
    # 服务器配置
    server_row = ttk_boot.Frame(query_frame)
    server_row.pack(fill='x', pady=5)
    ttk_boot.Label(server_row, text="服务器:", width=10).pack(side='left', padx=5)
    parent.wl_server = ttk_boot.Combobox(server_row, width=20, state='readonly')
    parent.wl_server['values'] = [node['name'] for node in parent.config.get_remote_nodes()]
    parent.wl_server.pack(side='left', padx=5)
    
    # 查询条件
    search_row = ttk_boot.Frame(query_frame)
    search_row.pack(fill='x', pady=5)
    ttk_boot.Label(search_row, text="患者ID:", width=10).pack(side='left', padx=5)
    parent.wl_patient_id = ttk_boot.Entry(search_row, width=15)
    parent.wl_patient_id.pack(side='left', padx=5)
    ttk_boot.Label(search_row, text="患者姓名:", width=10).pack(side='left', padx=5)
    parent.wl_patient_name = ttk_boot.Entry(search_row, width=15)
    parent.wl_patient_name.pack(side='left', padx=5)
    ttk_boot.Button(search_row, text="查询", bootstyle="primary",
                   command=lambda: query_worklist(parent)).pack(side='left', padx=10)
    
    # Worklist服务 (SCP)
    service_frame = ttk_boot.Labelframe(frame, text="Worklist服务 (SCP)", bootstyle="success", padding=10)
    service_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # 服务控制
    control_row = ttk_boot.Frame(service_frame)
    control_row.pack(fill='x', pady=5)
    
    parent.btn_start_wl = ttk_boot.Button(control_row, text="▶ 启动Worklist服务",
                                         bootstyle="success", command=lambda: start_worklist_scp(parent))
    parent.btn_start_wl.pack(side='left', padx=5)
    
    parent.btn_stop_wl = ttk_boot.Button(control_row, text="⏹ 停止Worklist服务",
                                        bootstyle="danger", command=lambda: stop_worklist_scp(parent),
                                        state='disabled')
    parent.btn_stop_wl.pack(side='left', padx=5)
    
    ttk_boot.Button(control_row, text="生成测试数据", bootstyle="info",
                   command=lambda: generate_test_worklist(parent)).pack(side='left', padx=5)
    
    # Worklist数据表格
    from tkinter import ttk
    columns = ('patient_id', 'patient_name', 'study_date', 'study_time', 'modality', 'description')
    parent.worklist_tree = ttk.Treeview(service_frame, columns=columns, show='headings', height=15)
    
    parent.worklist_tree.heading('patient_id', text='患者ID')
    parent.worklist_tree.heading('patient_name', text='患者姓名')
    parent.worklist_tree.heading('study_date', text='检查日期')
    parent.worklist_tree.heading('study_time', text='检查时间')
    parent.worklist_tree.heading('modality', text='模态')
    parent.worklist_tree.heading('description', text='描述')
    
    for col in columns:
        parent.worklist_tree.column(col, width=120)
    
    scrollbar = ttk_boot.Scrollbar(service_frame, orient='vertical', command=parent.worklist_tree.yview)
    parent.worklist_tree.configure(yscrollcommand=scrollbar.set)
    
    parent.worklist_tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    
    # 数据管理按钮
    data_btn_frame = ttk_boot.Frame(service_frame)
    data_btn_frame.pack(fill='x', pady=5)
    
    ttk_boot.Button(data_btn_frame, text="添加项", bootstyle="success",
                   command=lambda: add_worklist_item(parent)).pack(side='left', padx=5)
    ttk_boot.Button(data_btn_frame, text="删除选中", bootstyle="danger",
                   command=lambda: delete_worklist_item(parent)).pack(side='left', padx=5)
    ttk_boot.Button(data_btn_frame, text="刷新列表", bootstyle="info",
                   command=lambda: refresh_worklist_list(parent)).pack(side='left', padx=5)
    
    return frame

def query_worklist(parent):
    """查询Worklist"""
    messagebox.showinfo("提示", "Worklist查询功能")

def start_worklist_scp(parent):
    """启动Worklist SCP"""
    try:
        from dicom.worklist_scp import WorklistSCP
        parent.worklist_scp = WorklistSCP()
        parent.worklist_scp.start()
        parent.btn_start_wl.config(state='disabled')
        parent.btn_stop_wl.config(state='normal')
        messagebox.showinfo("成功", "Worklist服务已启动")
        refresh_worklist_list(parent)
    except Exception as e:
        messagebox.showerror("错误", f"启动失败: {str(e)}")

def stop_worklist_scp(parent):
    """停止Worklist SCP"""
    if parent.worklist_scp:
        parent.worklist_scp.stop()
        parent.worklist_scp = None
    parent.btn_start_wl.config(state='normal')
    parent.btn_stop_wl.config(state='disabled')
    messagebox.showinfo("成功", "Worklist服务已停止")

def generate_test_worklist(parent):
    """生成测试数据"""
    if not parent.worklist_scp:
        parent.worklist_scp = WorklistSCP()
    
    parent.worklist_scp.generate_test_data(10)
    refresh_worklist_list(parent)
    messagebox.showinfo("成功", "已生成10条测试数据")

def add_worklist_item(parent):
    """添加Worklist项"""
    messagebox.showinfo("提示", "添加Worklist项功能")

def delete_worklist_item(parent):
    """删除Worklist项"""
    selected = parent.worklist_tree.selection()
    if not selected:
        messagebox.showwarning("警告", "请先选择要删除的项")
        return
    
    if messagebox.askyesno("确认", "确定要删除选中的项吗？"):
        # 实现删除逻辑
        pass

def refresh_worklist_list(parent):
    """刷新Worklist列表"""
    parent.worklist_tree.delete(*parent.worklist_tree.get_children())
    
    if parent.worklist_scp:
        for item in parent.worklist_scp.worklist_data:
            parent.worklist_tree.insert('', 'end', values=(
                item.get('PatientID', ''),
                item.get('PatientName', ''),
                item.get('StudyDate', ''),
                item.get('StudyTime', ''),
                item.get('Modality', ''),
                item.get('StudyDescription', '')
            ))

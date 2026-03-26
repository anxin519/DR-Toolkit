# -*- coding: utf-8 -*-
"""接收标签页 UI + 事件（含转发队列面板）"""
import os
import tkinter as tk
from tkinter import messagebox, scrolledtext
import ttkbootstrap as ttk_boot
from tkinter import ttk

from dicom.scp import DicomSCP
from utils.charset_helper import safe_str


def build(app) -> ttk_boot.Frame:
    frame = ttk_boot.Frame(app.notebook)

    # ── SCP 配置 ──────────────────────────────────────────────────────
    cfg = ttk_boot.Labelframe(frame, text="SCP 配置", padding=10)
    cfg.pack(fill='x', padx=10, pady=10)

    row = ttk_boot.Frame(cfg)
    row.pack(fill='x')

    for label, attr, default, widget_type in [
        ("AE:", 'local_ae', 'DICOM_TOOL', 'entry'),
        ("Port:", 'local_port', 11112, 'spinbox'),
        ("存储路径:", 'storage_path', './storage', 'entry'),
    ]:
        ttk_boot.Label(row, text=label).pack(side='left', padx=5)
        if widget_type == 'spinbox':
            w = ttk_boot.Spinbox(row, from_=1, to=65535, width=8)
            w.set(default)
        else:
            w = ttk_boot.Entry(row, width=30 if attr == 'storage_path' else 12)
            w.insert(0, default)
        w.pack(side='left', padx=5)
        setattr(app, attr, w)

    # 控制行
    ctrl = ttk_boot.Frame(cfg)
    ctrl.pack(fill='x', pady=8)

    app.auto_forward_enabled = ttk_boot.Checkbutton(
        ctrl, text="启用自动转发", bootstyle="success-round-toggle",
        variable=app.auto_forward_var)
    app.auto_forward_enabled.pack(side='left', padx=5)

    ttk_boot.Separator(ctrl, orient='vertical').pack(side='left', fill='y', padx=10)

    app.btn_start_scp = ttk_boot.Button(ctrl, text="▶ 启动", bootstyle="success",
                                         command=lambda: _start_scp(app))
    app.btn_start_scp.pack(side='left', padx=5)

    app.btn_stop_scp = ttk_boot.Button(ctrl, text="⏹ 停止", bootstyle="danger",
                                        command=lambda: _stop_scp(app), state='disabled')
    app.btn_stop_scp.pack(side='left', padx=5)

    ttk_boot.Button(ctrl, text="清空日志", bootstyle="secondary",
                    command=lambda: app.log_text.delete('1.0', 'end')).pack(side='left', padx=5)

    # ── 接收日志 ──────────────────────────────────────────────────────
    log_frame = ttk_boot.Labelframe(frame, text="接收日志", padding=10)
    log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 5))

    app.log_text = scrolledtext.ScrolledText(log_frame, font=('Consolas', 9), height=12)
    app.log_text.pack(fill='both', expand=True)

    # ── 转发队列面板 ──────────────────────────────────────────────────
    q_frame = ttk_boot.Labelframe(frame, text="转发队列", padding=10)
    q_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    q_cols = ('id', 'file', 'target', 'status', 'retry', 'error')
    app.queue_tree = ttk.Treeview(q_frame, columns=q_cols, show='headings', height=6)
    for col, heading, width in [
        ('id', 'ID', 60), ('file', '文件', 180), ('target', '目标节点', 100),
        ('status', '状态', 70), ('retry', '重试', 50), ('error', '错误信息', 200),
    ]:
        app.queue_tree.heading(col, text=heading)
        app.queue_tree.column(col, width=width, anchor='w')

    qsb = ttk_boot.Scrollbar(q_frame, orient='vertical', command=app.queue_tree.yview)
    app.queue_tree.configure(yscrollcommand=qsb.set)
    app.queue_tree.pack(side='left', fill='both', expand=True)
    qsb.pack(side='right', fill='y')

    q_btn = ttk_boot.Frame(frame)
    q_btn.pack(fill='x', padx=10, pady=(0, 8))
    ttk_boot.Button(q_btn, text="🔄 刷新队列", bootstyle="secondary",
                    command=lambda: refresh_queue(app)).pack(side='left', padx=5)
    ttk_boot.Button(q_btn, text="▶ 重试失败", bootstyle="warning",
                    command=lambda: _retry_failed(app)).pack(side='left', padx=5)
    ttk_boot.Button(q_btn, text="🗑 清除已完成", bootstyle="info",
                    command=lambda: _clear_done(app)).pack(side='left', padx=5)

    # 启动队列 worker
    app.forward_queue.start_worker(_forward_callback(app))

    # 每5秒自动刷新队列面板
    def _auto_refresh():
        refresh_queue(app)
        app.root.after(5000, _auto_refresh)
    app.root.after(5000, _auto_refresh)

    return frame


# ── SCP 控制 ──────────────────────────────────────────────────────────

def _start_scp(app):
    try:
        app.scp = DicomSCP(
            ae_title=app.local_ae.get(),
            port=int(app.local_port.get()),
            storage_path=app.storage_path.get(),
            on_received=lambda fp, ds: _on_received(app, fp, ds)
        )
        app.scp.start()
        app.btn_start_scp.config(state='disabled')
        app.btn_stop_scp.config(state='normal')
        _log(app, f"✓ SCP已启动  AE:{app.local_ae.get()}  端口:{app.local_port.get()}\n")
        app.logger.info(f"SCP已启动 AE:{app.local_ae.get()} 端口:{app.local_port.get()}")
    except Exception as e:
        messagebox.showerror("错误", f"启动失败: {e}")
        app.logger.error(f"SCP启动失败: {e}")


def _stop_scp(app):
    if app.scp:
        app.scp.stop()
        app.scp = None
    app.btn_start_scp.config(state='normal')
    app.btn_stop_scp.config(state='disabled')
    _log(app, "✓ SCP已停止\n")
    app.logger.info("SCP已停止")


def _on_received(app, filepath, dataset):
    patient = safe_str(getattr(dataset, 'PatientName', ''), dataset)
    modality = str(getattr(dataset, 'Modality', ''))
    msg = f"✓ 收到: {os.path.basename(filepath)}  患者:{patient}  模态:{modality}\n"
    app.root.after(0, lambda: _log(app, msg))
    app.logger.info(f"收到文件: {filepath} 患者:{patient} 模态:{modality}")

    if app.auto_forward_var.get():
        from gui.tab_send import get_selected_nodes
        for node in get_selected_nodes(app):
            app.forward_queue.add_task(filepath, node)
        app.root.after(0, lambda: refresh_queue(app))


def _log(app, msg):
    app.log_text.insert('end', msg)
    app.log_text.see('end')


# ── 转发队列 ──────────────────────────────────────────────────────────

def refresh_queue(app):
    app.queue_tree.delete(*app.queue_tree.get_children())
    for task in app.forward_queue.queue:
        status_map = {'pending': '⏳ 等待', 'success': '✓ 成功', 'failed': '✗ 失败'}
        app.queue_tree.insert('', 'end', values=(
            task['id'][-6:],
            os.path.basename(task.get('filepath', '')),
            task.get('target_node', {}).get('name', ''),
            status_map.get(task['status'], task['status']),
            task.get('retry_count', 0),
            task.get('error', '') or '',
        ))


def _retry_failed(app):
    for task in app.forward_queue.get_failed_tasks():
        app.forward_queue.retry_task(task['id'])
    refresh_queue(app)
    messagebox.showinfo("提示", "已将失败任务重置为待发送")


def _clear_done(app):
    app.forward_queue.clear_completed()
    refresh_queue(app)


def _forward_callback(app):
    """返回转发队列 worker 使用的回调函数"""
    def callback(filepath, target_node):
        from dicom.scu import DicomSCU
        scu = DicomSCU()
        results = scu.send_batch([filepath], target_node['host'],
                                  target_node['port'], target_node['ae'])
        ok = results[0][1] if results else False
        app.root.after(0, lambda: refresh_queue(app))
        return ok
    return callback

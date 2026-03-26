# -*- coding: utf-8 -*-
"""接收标签页 UI + 事件（含转发队列、条件转发规则）"""
import os
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
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

    # 从配置文件读取上次保存的值
    scp_cfg = app.config.get('local_scp', {})
    defaults = {
        'local_ae':     ('AE:',      scp_cfg.get('ae', 'DICOM_TOOL'),      'entry',   12),
        'local_port':   ('Port:',    scp_cfg.get('port', 11112),            'spinbox',  8),
        'storage_path': ('存储路径:', scp_cfg.get('storage_path','./storage'),'entry',  30),
    }
    for attr, (label, default, wtype, width) in defaults.items():
        ttk_boot.Label(row, text=label).pack(side='left', padx=5)
        if wtype == 'spinbox':
            w = ttk_boot.Spinbox(row, from_=1, to=65535, width=width)
            w.set(default)
        else:
            w = ttk_boot.Entry(row, width=width)
            w.insert(0, str(default))
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

    # ── 转发规则 ──────────────────────────────────────────────────────
    rule_frame = ttk_boot.Labelframe(frame, text="条件转发规则（空=不过滤，匹配则转发到指定节点）", padding=8)
    rule_frame.pack(fill='x', padx=10, pady=(0, 5))

    rule_cols = ('modality', 'source_ae', 'target_node')
    app.rule_tree = ttk.Treeview(rule_frame, columns=rule_cols, show='headings', height=3)
    for col, heading, width in [
        ('modality', '模态过滤', 80), ('source_ae', '来源AE过滤', 120), ('target_node', '转发目标节点', 200)
    ]:
        app.rule_tree.heading(col, text=heading)
        app.rule_tree.column(col, width=width, anchor='w')

    rsb = ttk_boot.Scrollbar(rule_frame, orient='vertical', command=app.rule_tree.yview)
    app.rule_tree.configure(yscrollcommand=rsb.set)
    app.rule_tree.pack(side='left', fill='both', expand=True)
    rsb.pack(side='right', fill='y')

    rule_btn = ttk_boot.Frame(frame)
    rule_btn.pack(fill='x', padx=10, pady=(0, 5))
    ttk_boot.Button(rule_btn, text="➕ 添加规则", bootstyle="success",
                    command=lambda: _add_rule(app)).pack(side='left', padx=5)
    ttk_boot.Button(rule_btn, text="🗑 删除规则", bootstyle="danger",
                    command=lambda: _delete_rule(app)).pack(side='left', padx=5)

    _load_rules(app)

    # ── 接收日志 ──────────────────────────────────────────────────────
    log_frame = ttk_boot.Labelframe(frame, text="接收日志", padding=10)
    log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 5))

    app.log_text = scrolledtext.ScrolledText(log_frame, font=('Consolas', 9), height=10)
    app.log_text.pack(fill='both', expand=True)

    # ── 转发队列面板 ──────────────────────────────────────────────────
    q_frame = ttk_boot.Labelframe(frame, text="转发队列", padding=10)
    q_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    q_cols = ('id', 'file', 'target', 'status', 'retry', 'error')
    app.queue_tree = ttk.Treeview(q_frame, columns=q_cols, show='headings', height=5)
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
        ae = app.local_ae.get()
        port = int(app.local_port.get())
        storage = app.storage_path.get()

        app.scp = DicomSCP(
            ae_title=ae, port=port, storage_path=storage,
            on_received=lambda fp, ds: _on_received(app, fp, ds)
        )
        app.scp.start()
        app.btn_start_scp.config(state='disabled')
        app.btn_stop_scp.config(state='normal')
        ts = datetime.now().strftime('%H:%M:%S')
        _log(app, f"[{ts}] ✓ SCP已启动  AE:{ae}  端口:{port}\n")
        app.logger.info(f"SCP已启动 AE:{ae} 端口:{port}")

        # 持久化 SCP 配置
        app.config.set('local_scp.ae', ae)
        app.config.set('local_scp.port', port)
        app.config.set('local_scp.storage_path', storage)
    except Exception as e:
        messagebox.showerror("错误", f"启动失败: {e}")
        app.logger.error(f"SCP启动失败: {e}")


def _stop_scp(app):
    if app.scp:
        app.scp.stop()
        app.scp = None
    app.btn_start_scp.config(state='normal')
    app.btn_stop_scp.config(state='disabled')
    ts = datetime.now().strftime('%H:%M:%S')
    _log(app, f"[{ts}] ✓ SCP已停止\n")
    app.logger.info("SCP已停止")


def _on_received(app, filepath, dataset):
    patient = safe_str(getattr(dataset, 'PatientName', ''), dataset)
    modality = str(getattr(dataset, 'Modality', ''))
    source_ae = str(getattr(dataset, 'SourceApplicationEntityTitle', ''))
    ts = datetime.now().strftime('%H:%M:%S')
    msg = f"[{ts}] ✓ 收到: {os.path.basename(filepath)}  患者:{patient}  模态:{modality}\n"
    app.root.after(0, lambda: _log(app, msg))
    app.logger.info(f"收到文件: {filepath} 患者:{patient} 模态:{modality}")

    if app.auto_forward_var.get():
        _auto_forward(app, filepath, modality, source_ae)
        app.root.after(0, lambda: refresh_queue(app))


def _auto_forward(app, filepath, modality, source_ae):
    """根据转发规则决定转发到哪些节点"""
    rules = app.config.get('forward_rules', [])

    if rules:
        # 有规则：按规则匹配
        matched_nodes = set()
        for rule in rules:
            rule_modality = rule.get('modality', '').strip()
            rule_ae = rule.get('source_ae', '').strip()
            target = rule.get('target_node', '')

            modality_ok = (not rule_modality) or (rule_modality.upper() == modality.upper())
            ae_ok = (not rule_ae) or (rule_ae.upper() == source_ae.upper())

            if modality_ok and ae_ok and target:
                matched_nodes.add(target)

        # 找到匹配的节点配置
        all_nodes = {n['name']: n for n in app.config.get_remote_nodes()}
        for node_name in matched_nodes:
            if node_name in all_nodes:
                app.forward_queue.add_task(filepath, all_nodes[node_name])
    else:
        # 无规则：转发到发送页勾选的节点
        from gui.tab_send import get_selected_nodes
        for node in get_selected_nodes(app):
            app.forward_queue.add_task(filepath, node)


def _log(app, msg):
    app.log_text.insert('end', msg)
    app.log_text.see('end')


# ── 转发规则管理 ──────────────────────────────────────────────────────

def _load_rules(app):
    app.rule_tree.delete(*app.rule_tree.get_children())
    for rule in app.config.get('forward_rules', []):
        app.rule_tree.insert('', 'end', values=(
            rule.get('modality', '*'),
            rule.get('source_ae', '*'),
            rule.get('target_node', ''),
        ))


def _add_rule(app):
    dialog = tk.Toplevel(app.root)
    dialog.title("添加转发规则")
    dialog.geometry("380x200")
    dialog.grab_set()

    fields = [
        ("模态过滤 (空=全部)", "modality", ""),
        ("来源AE过滤 (空=全部)", "source_ae", ""),
    ]
    entries = {}
    for i, (label, key, default) in enumerate(fields):
        ttk_boot.Label(dialog, text=label + ":").grid(row=i, column=0, sticky='w', padx=10, pady=6)
        e = ttk_boot.Entry(dialog, width=25)
        e.insert(0, default)
        e.grid(row=i, column=1, padx=10, pady=6)
        entries[key] = e

    ttk_boot.Label(dialog, text="转发目标节点:").grid(row=2, column=0, sticky='w', padx=10, pady=6)
    node_names = [n['name'] for n in app.config.get_remote_nodes()]
    target_var = tk.StringVar()
    cb = ttk_boot.Combobox(dialog, textvariable=target_var, values=node_names,
                            state='readonly', width=23)
    if node_names:
        cb.set(node_names[0])
    cb.grid(row=2, column=1, padx=10, pady=6)

    def save():
        target = target_var.get()
        if not target:
            messagebox.showwarning("警告", "请选择目标节点", parent=dialog)
            return
        rule = {
            'modality': entries['modality'].get().strip().upper(),
            'source_ae': entries['source_ae'].get().strip().upper(),
            'target_node': target,
        }
        rules = app.config.get('forward_rules', [])
        rules.append(rule)
        app.config.set('forward_rules', rules)
        _load_rules(app)
        dialog.destroy()

    ttk_boot.Button(dialog, text="保存", bootstyle="success", command=save).grid(
        row=3, column=0, columnspan=2, pady=12)


def _delete_rule(app):
    sel = app.rule_tree.selection()
    if not sel:
        messagebox.showwarning("警告", "请先选择要删除的规则")
        return
    idx = app.rule_tree.index(sel[0])
    rules = app.config.get('forward_rules', [])
    if 0 <= idx < len(rules):
        del rules[idx]
        app.config.set('forward_rules', rules)
        _load_rules(app)


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
    def callback(filepath, target_node):
        from dicom.scu import DicomSCU
        scu = DicomSCU()
        results = scu.send_batch([filepath], target_node['host'],
                                  target_node['port'], target_node['ae'])
        ok = results[0][1] if results else False
        app.root.after(0, lambda: refresh_queue(app))
        return ok
    return callback

# -*- coding: utf-8 -*-
"""Worklist 标签页 UI + 事件"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import ttkbootstrap as ttk_boot

from dicom.worklist import WorklistSCU
from dicom.worklist_scp import WorklistSCP
from utils.charset_helper import fix_dataset_encoding, safe_str


def build(app) -> ttk_boot.Frame:
    frame = ttk_boot.Frame(app.notebook)

    # ── SCP 服务 ──────────────────────────────────────────────────────
    scp_f = ttk_boot.Labelframe(frame, text="Worklist SCP 服务（响应设备查询）", padding=10)
    scp_f.pack(fill='x', padx=10, pady=(10, 5))

    cfg = ttk_boot.Frame(scp_f)
    cfg.pack(fill='x', pady=5)

    ttk_boot.Label(cfg, text="AE Title:").pack(side='left', padx=5)
    app.wl_scp_ae = ttk_boot.Entry(cfg, width=14)
    app.wl_scp_ae.insert(0, "WORKLIST_SCP")
    app.wl_scp_ae.pack(side='left', padx=5)

    ttk_boot.Label(cfg, text="端口:").pack(side='left', padx=5)
    app.wl_scp_port = ttk_boot.Spinbox(cfg, from_=1, to=65535, width=8)
    app.wl_scp_port.set(11113)
    app.wl_scp_port.pack(side='left', padx=5)

    app.btn_start_wl = ttk_boot.Button(cfg, text="▶ 启动服务", bootstyle="success",
                                        command=lambda: _start_scp(app))
    app.btn_start_wl.pack(side='left', padx=10)

    app.btn_stop_wl = ttk_boot.Button(cfg, text="⏹ 停止服务", bootstyle="danger",
                                       command=lambda: _stop_scp(app), state='disabled')
    app.btn_stop_wl.pack(side='left', padx=5)

    app.wl_scp_status = ttk_boot.Label(cfg, text="● 未运行", bootstyle="secondary")
    app.wl_scp_status.pack(side='left', padx=10)

    # ── 数据管理 ──────────────────────────────────────────────────────
    data_f = ttk_boot.Labelframe(frame, text="Worklist 数据管理", padding=10)
    data_f.pack(fill='both', expand=True, padx=10, pady=5)

    wl_cols = ('patient_id', 'patient_name', 'sex', 'age', 'study_date',
               'study_time', 'modality', 'description', 'accession')
    app.wl_tree = ttk.Treeview(data_f, columns=wl_cols, show='headings', height=10)
    for col, heading, width in [
        ('patient_id', '患者ID', 90), ('patient_name', '患者姓名', 100),
        ('sex', '性别', 50), ('age', '年龄', 60), ('study_date', '检查日期', 90),
        ('study_time', '检查时间', 80), ('modality', '模态', 60),
        ('description', '检查描述', 120), ('accession', 'AccessionNo', 110),
    ]:
        app.wl_tree.heading(col, text=heading)
        app.wl_tree.column(col, width=width, anchor='center')

    wsb = ttk_boot.Scrollbar(data_f, orient='vertical', command=app.wl_tree.yview)
    app.wl_tree.configure(yscrollcommand=wsb.set)
    app.wl_tree.pack(side='left', fill='both', expand=True)
    wsb.pack(side='right', fill='y')

    btn_bar = ttk_boot.Frame(frame)
    btn_bar.pack(fill='x', padx=10, pady=5)
    for text, style, cmd in [
        ("➕ 添加项目", "success", lambda: _add_item(app)),
        ("🗑 删除选中", "danger",  lambda: _delete_item(app)),
        ("🎲 生成测试数据", "info", lambda: _gen_test(app)),
        ("🔄 刷新列表", "secondary", lambda: refresh_tree(app)),
        ("🗑 清空全部", "warning", lambda: _clear_all(app)),
    ]:
        ttk_boot.Button(btn_bar, text=text, bootstyle=style, command=cmd).pack(side='left', padx=5)

    # ── SCU 查询 ──────────────────────────────────────────────────────
    scu_f = ttk_boot.Labelframe(frame, text="Worklist SCU 查询（向服务器查询）", padding=10)
    scu_f.pack(fill='x', padx=10, pady=(5, 10))

    r1 = ttk_boot.Frame(scu_f)
    r1.pack(fill='x', pady=5)
    for label, attr, default, width in [
        ("服务器AE:", 'wl_scu_ae', 'WORKLIST_SCP', 14),
        ("Host:", 'wl_scu_host', '127.0.0.1', 14),
    ]:
        ttk_boot.Label(r1, text=label).pack(side='left', padx=5)
        w = ttk_boot.Entry(r1, width=width)
        w.insert(0, default)
        w.pack(side='left', padx=5)
        setattr(app, attr, w)

    ttk_boot.Label(r1, text="Port:").pack(side='left', padx=5)
    app.wl_scu_port = ttk_boot.Spinbox(r1, from_=1, to=65535, width=8)
    app.wl_scu_port.set(11113)
    app.wl_scu_port.pack(side='left', padx=5)

    r2 = ttk_boot.Frame(scu_f)
    r2.pack(fill='x', pady=5)
    for label, attr in [("患者ID:", 'wl_query_pid'), ("患者姓名:", 'wl_query_name')]:
        ttk_boot.Label(r2, text=label).pack(side='left', padx=5)
        w = ttk_boot.Entry(r2, width=14)
        w.pack(side='left', padx=5)
        setattr(app, attr, w)

    ttk_boot.Label(r2, text="模态:").pack(side='left', padx=5)
    app.wl_query_modality = ttk_boot.Combobox(r2, width=8, state='readonly',
                                               values=['', 'CR', 'DR', 'CT', 'MR', 'US', 'XA'])
    app.wl_query_modality.pack(side='left', padx=5)
    ttk_boot.Button(r2, text="🔍 查询", bootstyle="primary",
                    command=lambda: _query(app)).pack(side='left', padx=10)

    res_f = ttk_boot.Labelframe(scu_f, text="查询结果", padding=5)
    res_f.pack(fill='x', pady=5)
    res_cols = ('patient_id', 'patient_name', 'modality', 'study_date', 'description', 'accession')
    app.wl_result_tree = ttk.Treeview(res_f, columns=res_cols, show='headings', height=5)
    for col, heading, width in [
        ('patient_id', '患者ID', 100), ('patient_name', '患者姓名', 100),
        ('modality', '模态', 60), ('study_date', '检查日期', 90),
        ('description', '描述', 150), ('accession', 'AccessionNo', 110),
    ]:
        app.wl_result_tree.heading(col, text=heading)
        app.wl_result_tree.column(col, width=width, anchor='center')

    rsb = ttk_boot.Scrollbar(res_f, orient='vertical', command=app.wl_result_tree.yview)
    app.wl_result_tree.configure(yscrollcommand=rsb.set)
    app.wl_result_tree.pack(side='left', fill='both', expand=True)
    rsb.pack(side='right', fill='y')

    return frame


# ── SCP 控制 ──────────────────────────────────────────────────────────

def _start_scp(app):
    try:
        ae, port = app.wl_scp_ae.get().strip(), int(app.wl_scp_port.get())
        app.worklist_scp = WorklistSCP(ae_title=ae, port=port)
        app.worklist_scp.start()
        app.btn_start_wl.config(state='disabled')
        app.btn_stop_wl.config(state='normal')
        app.wl_scp_status.config(text="● 运行中", bootstyle="success")
        app.logger.info(f"Worklist SCP已启动 AE:{ae} 端口:{port}")
    except Exception as e:
        messagebox.showerror("错误", f"启动Worklist SCP失败: {e}")


def _stop_scp(app):
    if app.worklist_scp:
        try:
            app.worklist_scp.stop()
        except Exception:
            pass
        app.worklist_scp = None
    app.btn_start_wl.config(state='normal')
    app.btn_stop_wl.config(state='disabled')
    app.wl_scp_status.config(text="● 未运行", bootstyle="secondary")


# ── 数据管理 ──────────────────────────────────────────────────────────

def _get_scp(app) -> WorklistSCP:
    """获取或临时创建 SCP 实例（用于数据读写）"""
    if app.worklist_scp:
        return app.worklist_scp
    tmp = WorklistSCP()
    tmp.worklist_data = tmp.load_data()
    return tmp


def refresh_tree(app):
    app.wl_tree.delete(*app.wl_tree.get_children())
    scp = _get_scp(app)
    for item in scp.worklist_data:
        app.wl_tree.insert('', 'end', values=(
            item.get('PatientID', ''), item.get('PatientName', ''),
            item.get('PatientSex', ''), item.get('PatientAge', ''),
            item.get('StudyDate', ''), item.get('StudyTime', ''),
            item.get('Modality', ''), item.get('StudyDescription', ''),
            item.get('AccessionNumber', ''),
        ))


def _add_item(app):
    dialog = tk.Toplevel(app.root)
    dialog.title("添加Worklist项目")
    dialog.geometry("420x340")
    dialog.grab_set()

    fields = [
        ("患者ID *", "PatientID", ""),
        ("患者姓名 *", "PatientName", ""),
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
        e = ttk_boot.Entry(dialog, width=26)
        e.insert(0, default)
        e.grid(row=i, column=1, padx=10, pady=4)
        entries[key] = e

    def save():
        item = {k: entries[k].get().strip() for k in entries}
        if not item["PatientID"] or not item["PatientName"]:
            messagebox.showwarning("警告", "患者ID和姓名不能为空", parent=dialog)
            return
        item["StudyDate"] = datetime.now().strftime('%Y%m%d')
        item["StudyTime"] = datetime.now().strftime('%H%M%S')
        scp = _get_scp(app)
        scp.add_worklist_item(item)
        refresh_tree(app)
        dialog.destroy()

    ttk_boot.Button(dialog, text="保存", bootstyle="success", command=save).grid(
        row=len(fields), column=0, columnspan=2, pady=12)


def _delete_item(app):
    sel = app.wl_tree.selection()
    if not sel:
        messagebox.showwarning("警告", "请先选择要删除的项目")
        return
    if not messagebox.askyesno("确认", "确定要删除选中的项目吗？"):
        return
    scp = _get_scp(app)
    scp.delete_worklist_item(app.wl_tree.index(sel[0]))
    refresh_tree(app)


def _gen_test(app):
    scp = _get_scp(app)
    scp.generate_test_data(10)
    refresh_tree(app)
    messagebox.showinfo("成功", "已生成10条测试数据")


def _clear_all(app):
    if not messagebox.askyesno("确认", "确定要清空所有Worklist数据吗？"):
        return
    scp = _get_scp(app)
    scp.worklist_data = []
    scp.save_data()
    refresh_tree(app)


# ── SCU 查询 ──────────────────────────────────────────────────────────

def _query(app):
    host = app.wl_scu_host.get().strip()
    port = int(app.wl_scu_port.get())
    ae = app.wl_scu_ae.get().strip()
    pid = app.wl_query_pid.get().strip() or None
    name = app.wl_query_name.get().strip() or None
    modality = app.wl_query_modality.get().strip() or None

    def run():
        try:
            scu = WorklistSCU()
            results = scu.query(host, port, ae, patient_id=pid,
                                patient_name=name, modality=modality)
            app.root.after(0, lambda: _show_results(app, results))
        except Exception as e:
            app.root.after(0, lambda: messagebox.showerror("查询失败", str(e)))

    threading.Thread(target=run, daemon=True).start()


def _show_results(app, results):
    app.wl_result_tree.delete(*app.wl_result_tree.get_children())
    for ds in results:
        fix_dataset_encoding(ds)
        sps = (ds.ScheduledProcedureStepSequence[0]
               if hasattr(ds, 'ScheduledProcedureStepSequence')
               and ds.ScheduledProcedureStepSequence else None)
        app.wl_result_tree.insert('', 'end', values=(
            safe_str(getattr(ds, 'PatientID', ''), ds),
            safe_str(getattr(ds, 'PatientName', ''), ds),
            str(getattr(sps, 'Modality', '')) if sps else '',
            str(getattr(sps, 'ScheduledProcedureStepStartDate', '')) if sps else '',
            safe_str(getattr(sps, 'ScheduledProcedureStepDescription', '')) if sps else '',
            str(getattr(ds, 'AccessionNumber', '')),
        ))
    if not results:
        messagebox.showinfo("查询结果", "未找到匹配的Worklist项目")

# -*- coding: utf-8 -*-
"""发送标签页 UI + 事件"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as ttk_boot

from dicom.scu import DicomSCU
from dicom.echo import DicomEcho


def build(app) -> ttk_boot.Frame:
    """构建发送页，返回 Frame；所有控件挂在 app 上"""
    frame = ttk_boot.Frame(app.notebook)

    # ── 节点管理区 ────────────────────────────────────────────────────
    node_frame = ttk_boot.Labelframe(frame, text="目标节点管理", padding=10)
    node_frame.pack(fill='both', expand=True, padx=10, pady=10)

    left = ttk_boot.Frame(node_frame)
    left.pack(side='left', fill='both', expand=True, padx=5)

    ttk_boot.Label(left, text="可用节点列表（勾选要发送的节点）:").pack(anchor='w', pady=5)

    cols = ('selected', 'name', 'ae', 'host', 'port', 'status')
    app.node_tree = ttk.Treeview(left, columns=cols, show='headings', height=8)
    for col, heading, width, anchor in [
        ('selected', '✓', 40, 'center'), ('name', '名称', 120, 'w'),
        ('ae', 'AE Title', 100, 'w'), ('host', 'Host', 120, 'w'),
        ('port', 'Port', 60, 'center'), ('status', '状态', 80, 'center'),
    ]:
        app.node_tree.heading(col, text=heading)
        app.node_tree.column(col, width=width, anchor=anchor)

    app.node_tree.bind('<Double-1>', lambda e: _load_node_to_edit(app, e))
    app.node_tree.bind('<Button-1>', lambda e: _toggle_node_selection(app, e))

    sb = ttk_boot.Scrollbar(left, orient='vertical', command=app.node_tree.yview)
    app.node_tree.configure(yscrollcommand=sb.set)
    app.node_tree.pack(side='left', fill='both', expand=True)
    sb.pack(side='right', fill='y')

    btn_col = ttk_boot.Frame(left)
    btn_col.pack(fill='x', pady=5)
    ttk_boot.Button(btn_col, text="全选", bootstyle="info-outline",
                    command=lambda: _select_all(app)).pack(fill='x', pady=2)
    ttk_boot.Button(btn_col, text="全不选", bootstyle="info-outline",
                    command=lambda: _deselect_all(app)).pack(fill='x', pady=2)
    ttk_boot.Button(btn_col, text="测试选中", bootstyle="info",
                    command=lambda: _test_selected(app)).pack(fill='x', pady=2)

    # 右侧编辑区
    right = ttk_boot.Frame(node_frame)
    right.pack(side='right', fill='y', padx=5)
    ttk_boot.Label(right, text="添加/编辑节点:").pack(anchor='w', pady=5)

    ef = ttk_boot.Frame(right)
    ef.pack(fill='x', pady=5)
    for row, (label, attr, default) in enumerate([
        ("名称:", 'node_name', ''), ("AE Title:", 'node_ae', ''),
        ("Host:", 'node_host', ''), ("Port:", 'node_port', None),
    ]):
        ttk_boot.Label(ef, text=label, width=8).grid(row=row, column=0, sticky='w', pady=2)
        if attr == 'node_port':
            w = ttk_boot.Spinbox(ef, from_=1, to=65535, width=18)
            w.set(104)
        else:
            w = ttk_boot.Entry(ef, width=20)
            if default:
                w.insert(0, default)
        w.grid(row=row, column=1, pady=2)
        setattr(app, attr, w)

    for text, style, cmd in [
        ("添加节点", "success", lambda: _add_node(app)),
        ("更新节点", "info",    lambda: _update_node(app)),
        ("删除节点", "danger",  lambda: _delete_node(app)),
    ]:
        ttk_boot.Button(right, text=text, bootstyle=style, command=cmd).pack(fill='x', pady=2)

    # ── 文件列表 ──────────────────────────────────────────────────────
    file_frame = ttk_boot.Labelframe(frame, text="待发送文件列表", padding=10)
    file_frame.pack(fill='both', expand=True, padx=10, pady=10)

    app.file_listbox = tk.Listbox(file_frame, font=('Consolas', 9), height=8)
    fsb = ttk_boot.Scrollbar(file_frame, orient='vertical', command=app.file_listbox.yview)
    app.file_listbox.configure(yscrollcommand=fsb.set)
    app.file_listbox.pack(side='left', fill='both', expand=True)
    fsb.pack(side='right', fill='y')

    # ── 底部按钮栏 ────────────────────────────────────────────────────
    btn_bar = ttk_boot.Frame(frame)
    btn_bar.pack(fill='x', padx=10, pady=8)

    ttk_boot.Button(btn_bar, text="添加文件",
                    command=lambda: _add_files(app)).pack(side='left', padx=5)
    ttk_boot.Button(btn_bar, text="添加文件夹",
                    command=lambda: _add_folder(app)).pack(side='left', padx=5)
    ttk_boot.Button(btn_bar, text="清空",
                    command=lambda: _clear_files(app)).pack(side='left', padx=5)

    app.send_status_label = ttk_boot.Label(btn_bar, text="")
    app.send_status_label.pack(side='left', padx=10)

    ttk_boot.Button(btn_bar, text="发送到选中节点", bootstyle="success",
                    command=lambda: _send_files(app)).pack(side='right', padx=5)

    _load_nodes(app)
    return frame


# ── 节点管理 ──────────────────────────────────────────────────────────

def _load_nodes(app):
    app.node_tree.delete(*app.node_tree.get_children())
    for node in app.config.get_remote_nodes():
        app.node_tree.insert('', 'end', values=(
            '☐', node.get('name', ''), node.get('ae', ''),
            node.get('host', ''), node.get('port', ''), '-'
        ), tags=('unselected',))


def _toggle_node_selection(app, event):
    region = app.node_tree.identify_region(event.x, event.y)
    if region != "cell":
        return
    item = app.node_tree.identify_row(event.y)
    if not item:
        return
    if app.node_tree.identify_column(event.x) == '#1':
        vals = list(app.node_tree.item(item, 'values'))
        if vals[0] == '☐':
            vals[0] = '☑'
            app.node_tree.item(item, values=vals, tags=('selected',))
            app.node_tree.tag_configure('selected', background='#d4edda')
        else:
            vals[0] = '☐'
            app.node_tree.item(item, values=vals, tags=('unselected',))
            app.node_tree.tag_configure('unselected', background='')


def _load_node_to_edit(app, event):
    item = app.node_tree.identify_row(event.y)
    if not item:
        return
    vals = app.node_tree.item(item, 'values')
    for widget, val in [(app.node_name, vals[1]), (app.node_ae, vals[2]),
                        (app.node_host, vals[3])]:
        widget.delete(0, 'end')
        widget.insert(0, val)
    app.node_port.delete(0, 'end')
    app.node_port.insert(0, vals[4])
    app.node_tree.selection_set(item)


def _select_all(app):
    for item in app.node_tree.get_children():
        vals = list(app.node_tree.item(item, 'values'))
        vals[0] = '☑'
        app.node_tree.item(item, values=vals, tags=('selected',))
    app.node_tree.tag_configure('selected', background='#d4edda')


def _deselect_all(app):
    for item in app.node_tree.get_children():
        vals = list(app.node_tree.item(item, 'values'))
        vals[0] = '☐'
        app.node_tree.item(item, values=vals, tags=('unselected',))
    app.node_tree.tag_configure('unselected', background='')


def get_selected_nodes(app):
    return [
        {'name': v[1], 'ae': v[2], 'host': v[3], 'port': int(v[4])}
        for item in app.node_tree.get_children()
        if (v := app.node_tree.item(item, 'values'))[0] == '☑'
    ]


def _test_selected(app):
    selected = get_selected_nodes(app)
    if not selected:
        messagebox.showwarning("警告", "请先选择要测试的节点")
        return

    def run():
        results = []
        for idx, node in enumerate(selected):
            try:
                success, msg, _ = DicomEcho.test(node['host'], node['port'], node['ae'])
                _update_status(app, idx, '✓' if success else '✗')
                results.append((node['name'], success, msg))
            except Exception as e:
                _update_status(app, idx, '✗')
                results.append((node['name'], False, str(e)))
        app.root.after(0, lambda: _show_test_results(results))

    threading.Thread(target=run, daemon=True).start()


def _update_status(app, index, status):
    items = [i for i in app.node_tree.get_children()
             if app.node_tree.item(i, 'values')[0] == '☑']
    if index < len(items):
        vals = list(app.node_tree.item(items[index], 'values'))
        vals[5] = status
        app.root.after(0, lambda i=items[index], v=vals: app.node_tree.item(i, values=v))


def _show_test_results(results):
    msg = "连接测试结果:\n\n"
    for name, ok, detail in results:
        msg += f"{'✓' if ok else '✗'} {name}: {'成功' if ok else '失败'}\n"
        if not ok:
            msg += f"  {detail}\n"
    messagebox.showinfo("测试结果", msg)


def _add_node(app):
    name, ae, host, port = (app.node_name.get().strip(), app.node_ae.get().strip(),
                             app.node_host.get().strip(), app.node_port.get())
    if not all([name, ae, host, port]):
        messagebox.showwarning("警告", "请填写完整的节点信息")
        return
    app.config.add_remote_node({'name': name, 'ae': ae, 'host': host, 'port': int(port)})
    _load_nodes(app)
    for w in (app.node_name, app.node_ae, app.node_host):
        w.delete(0, 'end')
    app.node_port.set(104)
    messagebox.showinfo("成功", f"节点 '{name}' 已添加")


def _update_node(app):
    sel = app.node_tree.selection()
    if not sel:
        messagebox.showwarning("警告", "请先选择要更新的节点")
        return
    name, ae, host, port = (app.node_name.get().strip(), app.node_ae.get().strip(),
                             app.node_host.get().strip(), app.node_port.get())
    if not all([name, ae, host, port]):
        messagebox.showwarning("警告", "请填写完整的节点信息")
        return
    app.config.update_remote_node(app.node_tree.index(sel[0]),
                                   {'name': name, 'ae': ae, 'host': host, 'port': int(port)})
    _load_nodes(app)
    messagebox.showinfo("成功", f"节点 '{name}' 已更新")


def _delete_node(app):
    sel = app.node_tree.selection()
    if not sel:
        messagebox.showwarning("警告", "请先选择要删除的节点")
        return
    name = app.node_tree.item(sel[0], 'values')[1]
    if messagebox.askyesno("确认", f"确定要删除节点 '{name}' 吗？"):
        app.config.delete_remote_node(app.node_tree.index(sel[0]))
        _load_nodes(app)


# ── 文件操作 ──────────────────────────────────────────────────────────

def _add_files(app):
    files = filedialog.askopenfilenames(
        title="选择DICOM文件", filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")])
    for f in files:
        if f not in app.file_paths:
            app.file_paths.append(f)
            app.file_listbox.insert('end', f)


def _add_folder(app):
    folder = filedialog.askdirectory(title="选择文件夹")
    if folder:
        for root, _, files in os.walk(folder):
            for fn in files:
                if fn.lower().endswith('.dcm'):
                    fp = os.path.join(root, fn)
                    if fp not in app.file_paths:
                        app.file_paths.append(fp)
                        app.file_listbox.insert('end', fp)


def _clear_files(app):
    app.file_listbox.delete(0, 'end')
    app.file_paths.clear()


def _send_files(app):
    if not app.file_paths:
        messagebox.showwarning("警告", "请先添加文件")
        return
    nodes = get_selected_nodes(app)
    if not nodes:
        messagebox.showwarning("警告", "请先选择目标节点")
        return
    names = ', '.join(n['name'] for n in nodes)
    if not messagebox.askyesno("确认发送",
                                f"将 {len(app.file_paths)} 个文件发送到:\n{names}\n\n确定继续吗？"):
        return

    def run():
        total = len(app.file_paths) * len(nodes)
        done = 0
        results = {}
        for node in nodes:
            nn = node['name']
            results[nn] = {'success': 0, 'failed': 0}
            app.root.after(0, lambda n=nn: app.send_status_label.config(text=f"正在发送到 {n}..."))
            try:
                scu = DicomSCU()
                for fp, ok in scu.send_batch(app.file_paths, node['host'], node['port'], node['ae']):
                    results[nn]['success' if ok else 'failed'] += 1
                    done += 1
                    pct = int(done / total * 100)
                    app.root.after(0, lambda c=done, t=total, p=pct:
                                   app.send_status_label.config(text=f"进度: {c}/{t} ({p}%)"))
                app.logger.info(f"发送到 {nn}: 成功{results[nn]['success']} 失败{results[nn]['failed']}")
            except Exception as e:
                app.logger.error(f"发送到 {nn} 失败: {e}")
                results[nn]['error'] = str(e)
                done += len(app.file_paths)
        app.root.after(0, lambda: _show_send_results(results, len(app.file_paths)))
        app.root.after(0, lambda: app.send_status_label.config(text=""))

    threading.Thread(target=run, daemon=True).start()


def _show_send_results(results, total):
    msg = f"发送完成！总文件数: {total}\n\n"
    for nn, r in results.items():
        msg += f"【{nn}】\n"
        if 'error' in r:
            msg += f"  ✗ 错误: {r['error']}\n"
        else:
            msg += f"  ✓ 成功: {r['success']}\n"
            if r['failed']:
                msg += f"  ✗ 失败: {r['failed']}\n"
        msg += "\n"
    messagebox.showinfo("发送结果", msg)

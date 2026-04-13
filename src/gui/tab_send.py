import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as ttk_boot

from dicom.scu import DicomSCU
from dicom.echo import DicomEcho
from utils.ui_helper import ProgressThrottler

class SendTab(ttk_boot.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.file_paths = []
        self._build_ui()

    def _build_ui(self):
        # ── 节点管理区 ──
        node_frame = ttk_boot.Labelframe(self, text="目标节点管理", padding=10)
        node_frame.pack(fill='both', expand=True, padx=10, pady=10)

        left = ttk_boot.Frame(node_frame)
        left.pack(side='left', fill='both', expand=True, padx=5)

        ttk_boot.Label(left, text="可用节点列表（勾选要发送的节点）:").pack(anchor='w', pady=5)

        cols = ('selected', 'name', 'ae', 'host', 'port', 'status')
        self.node_tree = ttk.Treeview(left, columns=cols, show='headings', height=8)
        for col, heading, width, anchor in [
            ('selected', '✓', 40, 'center'), ('name', '名称', 120, 'w'),
            ('ae', 'AE Title', 100, 'w'), ('host', 'Host', 120, 'w'),
            ('port', 'Port', 60, 'center'), ('status', '状态', 80, 'center'),
        ]:
            self.node_tree.heading(col, text=heading)
            self.node_tree.column(col, width=width, anchor=anchor)

        self.node_tree.bind('<Double-1>', self._load_node_to_edit)
        self.node_tree.bind('<Button-1>', self._toggle_node_selection)

        sb = ttk_boot.Scrollbar(left, orient='vertical', command=self.node_tree.yview)
        self.node_tree.configure(yscrollcommand=sb.set)
        self.node_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        btn_col = ttk_boot.Frame(left)
        btn_col.pack(fill='x', pady=5)
        ttk_boot.Button(btn_col, text="全选", bootstyle="info-outline", command=self._select_all).pack(fill='x', pady=2)
        ttk_boot.Button(btn_col, text="全不选", bootstyle="info-outline", command=self._deselect_all).pack(fill='x', pady=2)
        ttk_boot.Button(btn_col, text="测试选中", bootstyle="info", command=self._test_selected).pack(fill='x', pady=2)

        # 右侧编辑区
        right = ttk_boot.Frame(node_frame)
        right.pack(side='right', fill='y', padx=5)
        ttk_boot.Label(right, text="添加/编辑节点:").pack(anchor='w', pady=5)

        ef = ttk_boot.Frame(right)
        ef.pack(fill='x', pady=5)
        
        self.node_name_var = tk.StringVar()
        self.node_ae_var = tk.StringVar()
        self.node_host_var = tk.StringVar()
        self.node_port_var = tk.StringVar(value="104")

        ttk_boot.Label(ef, text="名称:", width=8).grid(row=0, column=0, sticky='w', pady=2)
        self.node_entry_name = ttk_boot.Entry(ef, textvariable=self.node_name_var, width=20)
        self.node_entry_name.grid(row=0, column=1, pady=2)

        ttk_boot.Label(ef, text="AE Title:", width=8).grid(row=1, column=0, sticky='w', pady=2)
        self.node_entry_ae = ttk_boot.Entry(ef, textvariable=self.node_ae_var, width=20)
        self.node_entry_ae.grid(row=1, column=1, pady=2)

        ttk_boot.Label(ef, text="Host:", width=8).grid(row=2, column=0, sticky='w', pady=2)
        self.node_entry_host = ttk_boot.Entry(ef, textvariable=self.node_host_var, width=20)
        self.node_entry_host.grid(row=2, column=1, pady=2)

        ttk_boot.Label(ef, text="Port:", width=8).grid(row=3, column=0, sticky='w', pady=2)
        self.node_entry_port = ttk_boot.Spinbox(ef, from_=1, to=65535, textvariable=self.node_port_var, width=18)
        self.node_entry_port.grid(row=3, column=1, pady=2)

        ttk_boot.Button(right, text="添加节点", bootstyle="success", command=self._add_node).pack(fill='x', pady=2)
        ttk_boot.Button(right, text="更新节点", bootstyle="info", command=self._update_node).pack(fill='x', pady=2)
        ttk_boot.Button(right, text="删除节点", bootstyle="danger", command=self._delete_node).pack(fill='x', pady=2)

        # ── 文件列表 ──
        file_frame = ttk_boot.Labelframe(self, text="待发送文件列表", padding=10)
        file_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.file_listbox = tk.Listbox(file_frame, font=('Consolas', 9), height=8)
        fsb = ttk_boot.Scrollbar(file_frame, orient='vertical', command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=fsb.set)
        self.file_listbox.pack(side='left', fill='both', expand=True)
        fsb.pack(side='right', fill='y')

        # ── 底部按钮栏 ──
        btn_bar = ttk_boot.Frame(self)
        btn_bar.pack(fill='x', padx=10, pady=8)

        ttk_boot.Button(btn_bar, text="添加文件", command=self._add_files).pack(side='left', padx=5)
        ttk_boot.Button(btn_bar, text="添加文件夹", command=self._add_folder).pack(side='left', padx=5)
        ttk_boot.Button(btn_bar, text="清空", command=self._clear_files).pack(side='left', padx=5)

        self.send_status_label = ttk_boot.Label(btn_bar, text="")
        self.send_status_label.pack(side='left', padx=10)

        self.send_progress = ttk_boot.Progressbar(btn_bar, mode='determinate', length=200)
        self.send_progress.pack(side='left', fill='x', expand=True, padx=10)

        ttk_boot.Button(btn_bar, text="发送到选中节点", bootstyle="success", command=self._send_files).pack(side='right', padx=5)

        self._load_nodes()

    # ── 节点管理 ──
    def _load_nodes(self):
        self.node_tree.delete(*self.node_tree.get_children())
        for node in self.app.config.get_remote_nodes():
            self.node_tree.insert('', 'end', values=(
                '☐', node.get('name', ''), node.get('ae', ''),
                node.get('host', ''), node.get('port', ''), '-'
            ), tags=('unselected',))

    def _toggle_node_selection(self, event):
        region = self.node_tree.identify_region(event.x, event.y)
        if region != "cell": return
        item = self.node_tree.identify_row(event.y)
        if not item: return
        if self.node_tree.identify_column(event.x) == '#1':
            vals = list(self.node_tree.item(item, 'values'))
            if vals[0] == '☐':
                vals[0] = '☑'
                self.node_tree.item(item, values=vals, tags=('selected',))
                self.node_tree.tag_configure('selected', background='#d4edda')
            else:
                vals[0] = '☐'
                self.node_tree.item(item, values=vals, tags=('unselected',))
                self.node_tree.tag_configure('unselected', background='')

    def _load_node_to_edit(self, event):
        item = self.node_tree.identify_row(event.y)
        if not item: return
        vals = self.node_tree.item(item, 'values')
        self.node_name_var.set(vals[1])
        self.node_ae_var.set(vals[2])
        self.node_host_var.set(vals[3])
        self.node_port_var.set(vals[4])
        self.node_tree.selection_set(item)

    def _select_all(self):
        for item in self.node_tree.get_children():
            vals = list(self.node_tree.item(item, 'values'))
            vals[0] = '☑'
            self.node_tree.item(item, values=vals, tags=('selected',))
        self.node_tree.tag_configure('selected', background='#d4edda')

    def _deselect_all(self):
        for item in self.node_tree.get_children():
            vals = list(self.node_tree.item(item, 'values'))
            vals[0] = '☐'
            self.node_tree.item(item, values=vals, tags=('unselected',))
        self.node_tree.tag_configure('unselected', background='')

    def get_selected_nodes(self):
        return [
            {'item_id': item, 'name': v[1], 'ae': v[2], 'host': v[3], 'port': int(v[4])}
            for item in self.node_tree.get_children()
            if (v := self.node_tree.item(item, 'values'))[0] == '☑'
        ]

    def _test_selected(self):
        selected = self.get_selected_nodes()
        if not selected:
            messagebox.showwarning("警告", "请先选择要测试的节点")
            return

        def run():
            results = []
            for node in selected:
                try:
                    success, msg, _ = DicomEcho.test(node['host'], node['port'], node['ae'])
                    self._update_status(node['item_id'], '✓' if success else '✗')
                    results.append((node['name'], success, msg))
                except Exception as e:
                    self._update_status(node['item_id'], '✗')
                    results.append((node['name'], False, str(e)))
            self.app.root.after(0, lambda: self._show_test_results(results))

        threading.Thread(target=run, daemon=True).start()

    def _update_status(self, item_id, status):
        def _update():
            if self.node_tree.exists(item_id):
                vals = list(self.node_tree.item(item_id, 'values'))
                vals[5] = status
                self.node_tree.item(item_id, values=vals)
        self.app.root.after(0, _update)

    def _show_test_results(self, results):
        msg = "连接测试结果:\n\n"
        for name, ok, detail in results:
            msg += f"{'✓' if ok else '✗'} {name}: {'成功' if ok else '失败'}\n"
            if not ok: msg += f"  {detail}\n"
        messagebox.showinfo("测试结果", msg)

    def _add_node(self):
        name, ae, host, port = (self.node_name_var.get().strip(), self.node_ae_var.get().strip(),
                                 self.node_host_var.get().strip(), self.node_port_var.get())
        if not all([name, ae, host, port]):
            messagebox.showwarning("警告", "请填写完整的节点信息")
            return
        self.app.config.add_remote_node({'name': name, 'ae': ae, 'host': host, 'port': int(port)})
        self._load_nodes()
        for var in (self.node_name_var, self.node_ae_var, self.node_host_var):
            var.set('')
        self.node_port_var.set('104')
        messagebox.showinfo("成功", f"节点 '{name}' 已添加")

    def _update_node(self):
        sel = self.node_tree.selection()
        if not sel:
            messagebox.showwarning("警告", "请先选择要更新的节点")
            return
        name, ae, host, port = (self.node_name_var.get().strip(), self.node_ae_var.get().strip(),
                                 self.node_host_var.get().strip(), self.node_port_var.get())
        if not all([name, ae, host, port]):
            messagebox.showwarning("警告", "请填写完整的节点信息")
            return
        self.app.config.update_remote_node(self.node_tree.index(sel[0]),
                                       {'name': name, 'ae': ae, 'host': host, 'port': int(port)})
        self._load_nodes()
        messagebox.showinfo("成功", f"节点 '{name}' 已更新")

    def _delete_node(self):
        sel = self.node_tree.selection()
        if not sel:
            messagebox.showwarning("警告", "请先选择要删除的节点")
            return
        name = self.node_tree.item(sel[0], 'values')[1]
        if messagebox.askyesno("确认", f"确定要删除节点 '{name}' 吗？"):
            self.app.config.delete_remote_node(self.node_tree.index(sel[0]))
            self._load_nodes()

    # ── 文件操作 ──
    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="选择DICOM文件", filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")])
        for f in files:
            if f not in self.file_paths:
                self.file_paths.append(f)
                self.file_listbox.insert('end', f)

    def _add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            for root, _, files in os.walk(folder):
                for fn in files:
                    if fn.lower().endswith('.dcm'):
                        fp = os.path.join(root, fn)
                        if fp not in self.file_paths:
                            self.file_paths.append(fp)
                            self.file_listbox.insert('end', fp)

    def _clear_files(self):
        self.file_listbox.delete(0, 'end')
        self.file_paths.clear()

    def _send_files(self):
        if not self.file_paths:
            messagebox.showwarning("警告", "请先添加文件")
            return
        nodes = self.get_selected_nodes()
        if not nodes:
            messagebox.showwarning("警告", "请先选择目标节点")
            return
        names = ', '.join(n['name'] for n in nodes)
        if not messagebox.askyesno("确认发送",
                                    f"将 {len(self.file_paths)} 个文件发送到:\n{names}\n\n确定继续吗？"):
            return

        # Snapshot data for background thread
        files_to_send = list(self.file_paths)
        
        def run():
            total = len(files_to_send) * len(nodes)
            done = 0
            results = {}
            self.app.root.after(0, lambda: self.send_progress.config(value=0))
            
            def update_ui(p):
                self.send_status_label.config(text=f"进度: {done}/{total} ({p}%)")
                self.send_progress.config(value=p)

            throttler = ProgressThrottler(lambda p: self.app.root.after(0, lambda: update_ui(p)))
            
            for node in nodes:
                nn = node['name']
                results[nn] = {'success': 0, 'failed': 0}
                self.app.root.after(0, lambda n=nn: self.send_status_label.config(text=f"正在发送到 {n}..."))
                try:
                    scu = DicomSCU()
                    for fp, ok in scu.send_batch(files_to_send, node['host'], node['port'], node['ae']):
                        results[nn]['success' if ok else 'failed'] += 1
                        done += 1
                        pct = int(done / total * 100)
                        throttler.update(pct)
                    self.app.logger.info(f"发送到 {nn}: 成功{results[nn]['success']} 失败{results[nn]['failed']}")
                except Exception as e:
                    self.app.logger.exception(f"发送到 {nn} 失败: {e}")
                    results[nn]['error'] = str(e)
                    done += len(files_to_send)
                    pct = int(done / total * 100)
                    throttler.update(pct)
            
            throttler.finalize(100)
            self.app.root.after(0, lambda: self._show_send_results(results, len(files_to_send)))
            self.app.root.after(0, lambda: self.send_status_label.config(text=""))
            self.app.root.after(0, lambda: self.send_progress.config(value=0))

        threading.Thread(target=run, daemon=True).start()

    def _show_send_results(self, results, total):
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

def build(app) -> ttk_boot.Frame:
    return SendTab(app.notebook, app)

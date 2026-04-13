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


class WorklistTab(ttk_boot.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.worklist_scp = None
        self._offline_wl_scp = None
        self._build_ui()

    def _build_ui(self):

    # ── SCP 服务 ──────────────────────────────────────────────────────
        scp_f = ttk_boot.Labelframe(self, text="Worklist SCP 服务（响应设备查询）", padding=10)
        scp_f.pack(fill='x', padx=10, pady=(10, 5))

        cfg = ttk_boot.Frame(scp_f)
        cfg.pack(fill='x', pady=5)

        ttk_boot.Label(cfg, text="AE Title:").pack(side='left', padx=5)
        self.wl_scp_ae = ttk_boot.Entry(cfg, width=14)
        self.wl_scp_ae.insert(0, "WORKLIST_SCP")
        self.wl_scp_ae.pack(side='left', padx=5)

        ttk_boot.Label(cfg, text="端口:").pack(side='left', padx=5)
        self.wl_scp_port = ttk_boot.Spinbox(cfg, from_=1, to=65535, width=8)
        self.wl_scp_port.set(11113)
        self.wl_scp_port.pack(side='left', padx=5)

        self.btn_start_wl = ttk_boot.Button(cfg, text="▶ 启动服务", bootstyle="success",
                                            command=self._start_scp)
        self.btn_start_wl.pack(side='left', padx=10)

        self.btn_stop_wl = ttk_boot.Button(cfg, text="⏹ 停止服务", bootstyle="danger",
                                           command=self._stop_scp, state='disabled')
        self.btn_stop_wl.pack(side='left', padx=5)

        self.wl_scp_status = ttk_boot.Label(cfg, text="● 未运行", bootstyle="secondary")
        self.wl_scp_status.pack(side='left', padx=10)

        # ── 数据管理 ──────────────────────────────────────────────────────
        data_f = ttk_boot.Labelframe(self, text="Worklist 数据管理", padding=10)
        data_f.pack(fill='both', expand=True, padx=10, pady=5)

        wl_cols = ('patient_id', 'patient_name', 'sex', 'age', 'study_date',
                   'study_time', 'modality', 'description', 'accession')
        self.wl_tree = ttk.Treeview(data_f, columns=wl_cols, show='headings', height=10)
        for col, heading, width in [
            ('patient_id', '患者ID', 90), ('patient_name', '患者姓名', 100),
            ('sex', '性别', 50), ('age', '年龄', 60), ('study_date', '检查日期', 90),
            ('study_time', '检查时间', 80), ('modality', '模态', 60),
            ('description', '检查描述', 120), ('accession', 'AccessionNo', 110),
        ]:
            self.wl_tree.heading(col, text=heading)
            self.wl_tree.column(col, width=width, anchor='center')

        wsb = ttk_boot.Scrollbar(data_f, orient='vertical', command=self.wl_tree.yview)
        self.wl_tree.configure(yscrollcommand=wsb.set)
        self.wl_tree.pack(side='left', fill='both', expand=True)
        wsb.pack(side='right', fill='y')

        btn_bar = ttk_boot.Frame(self)
        btn_bar.pack(fill='x', padx=10, pady=5)
        for text, style, cmd in [
            ("➕ 添加项目", "success", self._add_item),
            ("🗑 删除选中", "danger",  self._delete_item),
            ("🎲 生成测试数据", "info", self._gen_test),
            ("🔄 刷新列表", "secondary", self._refresh_tree),
            ("🗑 清空全部", "warning", self._clear_all),
        ]:
            ttk_boot.Button(btn_bar, text=text, bootstyle=style, command=cmd).pack(side='left', padx=5)

        # ── SCU 查询 ──────────────────────────────────────────────────────
        scu_f = ttk_boot.Labelframe(self, text="Worklist SCU 查询（向服务器查询）", padding=10)
        scu_f.pack(fill='x', padx=10, pady=(5, 10))

        r1 = ttk_boot.Frame(scu_f)
        r1.pack(fill='x', pady=5)
        
        ttk_boot.Label(r1, text="服务器AE:").pack(side='left', padx=5)
        self.wl_scu_ae = ttk_boot.Entry(r1, width=14)
        self.wl_scu_ae.insert(0, 'WORKLIST_SCP')
        self.wl_scu_ae.pack(side='left', padx=5)

        ttk_boot.Label(r1, text="Host:").pack(side='left', padx=5)
        self.wl_scu_host = ttk_boot.Entry(r1, width=14)
        self.wl_scu_host.insert(0, '127.0.0.1')
        self.wl_scu_host.pack(side='left', padx=5)

        ttk_boot.Label(r1, text="Port:").pack(side='left', padx=5)
        self.wl_scu_port = ttk_boot.Spinbox(r1, from_=1, to=65535, width=8)
        self.wl_scu_port.set(11113)
        self.wl_scu_port.pack(side='left', padx=5)

        r2 = ttk_boot.Frame(scu_f)
        r2.pack(fill='x', pady=5)
        
        ttk_boot.Label(r2, text="患者ID:").pack(side='left', padx=5)
        self.wl_query_pid = ttk_boot.Entry(r2, width=14)
        self.wl_query_pid.pack(side='left', padx=5)

        ttk_boot.Label(r2, text="患者姓名:").pack(side='left', padx=5)
        self.wl_query_name = ttk_boot.Entry(r2, width=14)
        self.wl_query_name.pack(side='left', padx=5)

        ttk_boot.Label(r2, text="模态:").pack(side='left', padx=5)
        self.wl_query_modality = ttk_boot.Combobox(r2, width=8, state='readonly',
                                                   values=['', 'CR', 'DR', 'CT', 'MR', 'US', 'XA'])
        self.wl_query_modality.pack(side='left', padx=5)
        ttk_boot.Button(r2, text="🔍 查询", bootstyle="primary",
                        command=self._query).pack(side='left', padx=10)

        res_f = ttk_boot.Labelframe(scu_f, text="查询结果", padding=5)
        res_f.pack(fill='x', pady=5)
        res_cols = ('patient_id', 'patient_name', 'modality', 'study_date', 'description', 'accession')
        self.wl_result_tree = ttk.Treeview(res_f, columns=res_cols, show='headings', height=5)
        for col, heading, width in [
            ('patient_id', '患者ID', 100), ('patient_name', '患者姓名', 100),
            ('modality', '模态', 60), ('study_date', '检查日期', 90),
            ('description', '描述', 150), ('accession', 'AccessionNo', 110),
        ]:
            self.wl_result_tree.heading(col, text=heading)
            self.wl_result_tree.column(col, width=width, anchor='center')

        rsb = ttk_boot.Scrollbar(res_f, orient='vertical', command=self.wl_result_tree.yview)
        self.wl_result_tree.configure(yscrollcommand=rsb.set)
        self.wl_result_tree.pack(side='left', fill='both', expand=True)
        rsb.pack(side='right', fill='y')

        # 初次加载时刷新列表
        self._refresh_tree()

    # ── SCP 控制 ──────────────────────────────────────────────────────────

    def _start_scp(self):
        try:
            ae, port = self.wl_scp_ae.get().strip(), int(self.wl_scp_port.get())
            self.worklist_scp = WorklistSCP(ae_title=ae, port=port)
            self.worklist_scp.start()
            self.btn_start_wl.config(state='disabled')
            self.btn_stop_wl.config(state='normal')
            self.wl_scp_status.config(text="● 运行中", bootstyle="success")
            self.app.logger.info(f"Worklist SCP已启动 AE:{ae} 端口:{port}")
        except OSError as e:
            if 'address already in use' in str(e).lower() or '10048' in str(e):
                messagebox.showerror("端口被占用",
                    f"端口 {self.wl_scp_port.get()} 已被其他程序占用\n\n"
                    f"建议：\n"
                    f"1. 更换一个端口号\n"
                    f"2. 关闭占用该端口的其他程序")
            else:
                messagebox.showerror("启动失败", f"网络错误: {e}")
        except Exception as e:
            messagebox.showerror("错误", f"启动Worklist SCP失败: {e}")

    def _stop_scp(self):
        if self.worklist_scp:
            try:
                self.worklist_scp.stop()
            except Exception:
                pass
            self.worklist_scp = None
        self.btn_start_wl.config(state='normal')
        self.btn_stop_wl.config(state='disabled')
        self.wl_scp_status.config(text="● 未运行", bootstyle="secondary")

    # ── 数据管理 ──────────────────────────────────────────────────────────

    def _get_scp(self) -> WorklistSCP:
        """获取或临时创建 SCP 实例（用于数据读写）"""
        if self.worklist_scp:
            return self.worklist_scp
        if not self._offline_wl_scp:
            self._offline_wl_scp = WorklistSCP()
        else:
            # 重载数据以防被其他实例修改
            self._offline_wl_scp.worklist_data = self._offline_wl_scp.load_data()
        return self._offline_wl_scp

    def _refresh_tree(self):
        self.wl_tree.delete(*self.wl_tree.get_children())
        scp = self._get_scp()
        for item in scp.worklist_data:
            self.wl_tree.insert('', 'end', values=(
                item.get('PatientID', ''), item.get('PatientName', ''),
                item.get('PatientSex', ''), item.get('PatientAge', ''),
                item.get('StudyDate', ''), item.get('StudyTime', ''),
                item.get('Modality', ''), item.get('StudyDescription', ''),
                item.get('AccessionNumber', ''),
            ))


    def _add_item(self):
        dialog = tk.Toplevel(self.app.root)
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
            scp = self._get_scp()
            scp.add_worklist_item(item)
            self._refresh_tree()
            dialog.destroy()

        ttk_boot.Button(dialog, text="保存", bootstyle="success", command=save).grid(
            row=len(fields), column=0, columnspan=2, pady=12)

    def _delete_item(self):
        sel = self.wl_tree.selection()
        if not sel:
            messagebox.showwarning("警告", "请先选择要删除的项目")
            return
        if not messagebox.askyesno("确认", "确定要删除选中的项目吗？"):
            return
        scp = self._get_scp()
        scp.delete_worklist_item(self.wl_tree.index(sel[0]))
        self._refresh_tree()

    def _gen_test(self):
        scp = self._get_scp()
        scp.generate_test_data(10)
        self._refresh_tree()
        messagebox.showinfo("成功", "已生成10条测试数据")

    def _clear_all(self):
        if not messagebox.askyesno("确认", "确定要清空所有Worklist数据吗？"):
            return
        scp = self._get_scp()
        scp.worklist_data = []
        scp.save_data()
        self._refresh_tree()


    # ── SCU 查询 ──────────────────────────────────────────────────────────

    def _query(self):
        host = self.wl_scu_host.get().strip()
        port = int(self.wl_scu_port.get())
        ae = self.wl_scu_ae.get().strip()
        pid = self.wl_query_pid.get().strip() or None
        name = self.wl_query_name.get().strip() or None
        modality = self.wl_query_modality.get().strip() or None

        def run():
            try:
                scu = WorklistSCU()
                results = scu.query(host, port, ae, patient_id=pid,
                                    patient_name=name, modality=modality)
                self.app.root.after(0, lambda: self._show_results(results))
            except Exception as e:
                self.app.root.after(0, lambda: messagebox.showerror("查询失败", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _show_results(self, results):
        self.wl_result_tree.delete(*self.wl_result_tree.get_children())
        for ds in results:
            fix_dataset_encoding(ds)
            sps = (ds.ScheduledProcedureStepSequence[0]
                   if hasattr(ds, 'ScheduledProcedureStepSequence')
                   and ds.ScheduledProcedureStepSequence else None)
            self.wl_result_tree.insert('', 'end', values=(
                safe_str(getattr(ds, 'PatientID', ''), ds),
                safe_str(getattr(ds, 'PatientName', ''), ds),
                str(getattr(sps, 'Modality', '')) if sps else '',
                str(getattr(sps, 'ScheduledProcedureStepStartDate', '')) if sps else '',
                safe_str(getattr(sps, 'ScheduledProcedureStepDescription', '')) if sps else '',
                str(getattr(ds, 'AccessionNumber', '')),
            ))
        if not results:
            messagebox.showinfo("查询结果", "未找到匹配的Worklist项目")

def build(app) -> ttk_boot.Frame:
    return WorklistTab(app.notebook, app)

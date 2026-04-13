import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pydicom
import ttkbootstrap as ttk_boot

from dicom.editor import DicomEditor
from dicom.anonymizer import DicomAnonymizer
from utils.age_calculator import calculate_age
from utils.excel_exporter import ExcelExporter
from utils.charset_helper import fix_dataset_encoding, safe_str
from utils.ui_helper import ProgressThrottler
import concurrent.futures

def get_max_workers():
    return min(32, (os.cpu_count() or 1) * 2)

class BrowserTab(ttk_boot.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.data = []
        self._batch_cancel = threading.Event()
        self._sort_state = {}
        self.is_busy = False
        
        self._build_ui()

    def _build_ui(self):
        # ── 工具栏 ──
        self.toolbar = ttk_boot.Frame(self)
        self.toolbar.pack(fill='x', padx=10, pady=8)

        self.btn_scan = ttk_boot.Button(self.toolbar, text="📂 选择文件夹", command=self._scan)
        self.btn_scan.pack(side='left', padx=5)

        self.btn_export = ttk_boot.Button(self.toolbar, text="📊 导出Excel", bootstyle="success", command=self._export)
        self.btn_export.pack(side='left', padx=5)

        self.btn_batch = ttk_boot.Menubutton(self.toolbar, text="批量操作 ▼", bootstyle="info")
        self.btn_batch.pack(side='left', padx=5)
        self.menu = tk.Menu(self.btn_batch, tearoff=0)
        self.btn_batch['menu'] = self.menu
        self.menu.add_command(label="批量匿名化", command=self._batch_anonymize)
        self.menu.add_command(label="批量计算年龄", command=self._batch_age)
        self.menu.add_command(label="批量修改UID（保持Study关联）", command=lambda: self._batch_uid(force_unique=False))
        self.menu.add_separator()
        self.menu.add_command(label="批量修改UID（每文件独立Study）", command=lambda: self._batch_uid(force_unique=True))

        self.progress = ttk_boot.Progressbar(self.toolbar, mode='determinate')
        self.progress.pack(side='left', fill='x', expand=True, padx=10)

        self.count_label = ttk_boot.Label(self.toolbar, text="")
        self.count_label.pack(side='left', padx=5)

        # ── 文件表格 ──
        cols = ('path', 'name', 'patient_name', 'patient_id', 'sex', 'age', 'date', 'modality',
                'study_uid', 'series_uid', 'sop_uid')
        headers = ['路径', '文件名', '患者姓名', '病历号', '性别', '年龄', '检查日期', '模态',
                   'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
        widths  = [200, 120, 100, 100, 50, 60, 90, 60, 200, 200, 200]

        self.tree = ttk.Treeview(self, columns=cols, show='headings', height=28)
        for col, header, width in zip(cols, headers, widths):
            self.tree.heading(col, text=header, command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width)

        sb = ttk_boot.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=5)
        sb.pack(side='right', fill='y', pady=5, padx=(0, 5))

    def _set_busy(self, busy: bool):
        self.is_busy = busy
        state = 'disabled' if busy else 'normal'
        self.btn_scan.config(state=state)
        self.btn_export.config(state=state)
        self.btn_batch.config(state=state)
        self.app.root.update_idletasks()

    def _scan(self):
        if self.is_busy: return
        folder = filedialog.askdirectory(title="选择文件夹")
        if not folder:
            return

        self._set_busy(True)

        def run():
            self.tree.delete(*self.tree.get_children())
            self.data = []
            files = [os.path.join(r, fn)
                     for r, _, fns in os.walk(folder)
                     for fn in fns if fn.lower().endswith('.dcm')]
            total = len(files)
            self.app.root.after(0, lambda: self.count_label.config(text=f"共 {total} 个文件"))

            if not files:
                self.app.root.after(0, lambda: self._set_busy(False))
                return

            def process_file(fp):
                try:
                    ds = pydicom.dcmread(fp, stop_before_pixels=True)
                    fix_dataset_encoding(ds)
                    # 仅保留元数据，不常驻内存
                    meta_dict = {
                        'patient_name': safe_str(getattr(ds, 'PatientName', ''), ds),
                        'patient_id': safe_str(getattr(ds, 'PatientID', ''), ds),
                        'sex': str(getattr(ds, 'PatientSex', '')),
                        'age': str(getattr(ds, 'PatientAge', '')),
                        'date': str(getattr(ds, 'StudyDate', '')),
                        'modality': str(getattr(ds, 'Modality', '')),
                        'study_uid': str(getattr(ds, 'StudyInstanceUID', '')),
                        'series_uid': str(getattr(ds, 'SeriesInstanceUID', '')),
                        'sop_uid': str(getattr(ds, 'SOPInstanceUID', '')),
                        'PatientBirthDate': getattr(ds, 'PatientBirthDate', None),
                        'StudyDate': getattr(ds, 'StudyDate', None),
                    }
                    row = (
                        fp, os.path.basename(fp),
                        meta_dict['patient_name'],
                        meta_dict['patient_id'],
                        meta_dict['sex'],
                        meta_dict['age'],
                        meta_dict['date'],
                        meta_dict['modality'],
                        meta_dict['study_uid'],
                        meta_dict['series_uid'],
                        meta_dict['sop_uid']
                    )
                    return fp, meta_dict, row, None
                except Exception as e:
                    return fp, None, None, e

            workers = get_max_workers()
            throttler = ProgressThrottler(lambda p: self.app.root.after(0, lambda: self.progress.config(value=p)))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(process_file, fp) for fp in files]
                for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                    fp, meta, row, err = future.result()
                    if err:
                        self.app.logger.error(f"读取失败 {fp}: {err}")
                    else:
                        self.data.append((fp, meta))
                        self.app.root.after(0, lambda r=row: self.tree.insert('', 'end', values=r))

                    pct = (idx + 1) / total * 100
                    throttler.update(pct)
            
            throttler.finalize(100)
            self.app.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=run, daemon=True).start()

    def _export(self):
        if self.is_busy: return
        if not self.data:
            messagebox.showwarning("警告", "没有数据可导出")
            return
        fp = filedialog.asksaveasfilename(
            title="保存Excel", defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")])
        if not fp:
            return
        try:
            headers = ['路径', '文件名', '患者姓名', '病历号', '性别', '年龄', '检查日期', '模态',
                       'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
            data = [[p, os.path.basename(p),
                     m['patient_name'],
                     m['patient_id'],
                     m['sex'],
                     m['age'],
                     m['date'],
                     m['modality'],
                     m['study_uid'],
                     m['series_uid'],
                     m['sop_uid']]
                    for p, m in self.data]
            ExcelExporter.export(data, fp, headers)
            messagebox.showinfo("成功", "Excel导出完成")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
            self.app.logger.exception(f"导出失败: {e}")

    def _batch_run(self, fn, confirm_msg, done_msg):
        if self.is_busy or not self.data:
            if not self.data: messagebox.showwarning("警告", "没有数据")
            return
        if not messagebox.askyesno("确认", confirm_msg):
            return

        self._set_busy(True)
        src_root = self._find_common_root([fp for fp, _ in self.data])
        out_root = os.path.join(os.path.dirname(src_root),
                                os.path.basename(src_root) + "_updated")
        os.makedirs(out_root, exist_ok=True)

        self._batch_cancel.clear()
        cancel_btn = ttk_boot.Button(
            self.progress.master, text="✕ 取消", bootstyle="danger",
            command=self._batch_cancel.set)
        cancel_btn.pack(side='left', padx=5)

        def run():
            count = fn(src_root, out_root, self._batch_cancel)
            self.app.root.after(0, cancel_btn.destroy)
            self.app.root.after(0, lambda: self._set_busy(False))
            
            if self._batch_cancel.is_set():
                self.app.root.after(0, lambda: messagebox.showinfo("已取消", f"操作已取消，已处理 {count} 个文件"))
            else:
                self.app.root.after(0, lambda: messagebox.showinfo("完成", done_msg.format(count) + f"\n\n输出目录:\n{out_root}"))

        threading.Thread(target=run, daemon=True).start()

    def _find_common_root(self, paths: list[str]) -> str:
        if not paths: return ''
        common = os.path.commonpath(paths)
        return common if os.path.isdir(common) else os.path.dirname(common)

    def _out_path(self, fp: str, src_root: str, out_root: str) -> str:
        rel = os.path.relpath(fp, src_root)
        out_fp = os.path.join(out_root, rel)
        os.makedirs(os.path.dirname(out_fp), exist_ok=True)
        return out_fp

    def _batch_anonymize(self):
        def fn(src_root, out_root, cancel):
            keep = self.app.config.get('anonymize.keep_last_digits', 4)
            prefix = self.app.config.get('anonymize.prefix', 'ANON')
            def process_file(fp):
                if cancel.is_set(): return False
                try:
                    ds = pydicom.dcmread(fp)
                    DicomAnonymizer.anonymize(ds, prefix, keep)
                    DicomEditor.save_file(ds, self._out_path(fp, src_root, out_root))
                    return True
                except Exception as e:
                    self.app.logger.exception(f"匿名化失败 {fp}: {e}")
                    return False

            count = 0
            total = len(self.data)
            workers = get_max_workers()
            throttler = ProgressThrottler(lambda p: self.app.root.after(0, lambda: self.progress.config(value=p)))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(process_file, fp) for fp, _ in self.data]
                for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                    if future.result(): count += 1
                    pct = (idx + 1) / total * 100
                    throttler.update(pct)
            throttler.finalize(100)
            return count

        self._batch_run(fn,
                   f"确定要匿名化 {len(self.data)} 个文件吗？\n（输出到源文件夹同级的 _updated 目录）",
                   "批量匿名化完成，共处理 {} 个文件")

    def _batch_age(self):
        def fn(src_root, out_root, cancel):
            def process_file(fp, meta):
                if cancel.is_set(): return False
                try:
                    if not meta.get('age') and meta.get('PatientBirthDate'):
                        age = calculate_age(meta['PatientBirthDate'], meta.get('StudyDate'))
                        if age:
                            ds = pydicom.dcmread(fp)
                            ds.PatientAge = age
                            DicomEditor.save_file(ds, self._out_path(fp, src_root, out_root))
                            meta['age'] = age
                            return True
                except Exception as e:
                    self.app.logger.exception(f"计算年龄失败 {fp}: {e}")
                return False

            count = 0
            total = len(self.data)
            workers = get_max_workers()
            throttler = ProgressThrottler(lambda p: self.app.root.after(0, lambda: self.progress.config(value=p)))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(process_file, fp, meta) for fp, meta in self.data]
                for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                    if future.result(): count += 1
                    pct = (idx + 1) / total * 100
                    throttler.update(pct)
            throttler.finalize(100)
            return count

        self._batch_run(fn,
                   "批量计算并填充缺失年龄？\n（输出到源文件夹同级的 _updated 目录）",
                   "已处理 {} 个文件")

    def _batch_uid(self, force_unique=False):
        def fn(src_root, out_root, cancel):
            method = self.app.config.get('uid_strategy.method', 'regenerate')
            new_accession = self.app.config.get('uid_strategy.new_accession', True)
            modify_pid = self.app.config.get('uid_strategy.modify_patient_id', True)
            from utils.uid_generator import batch_modify_uids

            datasets = []
            total = len(self.data)
            workers = get_max_workers()

            def read_file(fp):
                if cancel.is_set(): return None
                try:
                    return fp, pydicom.dcmread(fp)
                except Exception as e:
                    self.app.logger.exception(f"读取失败 {fp}: {e}")
                    return None

            self.app.root.after(0, lambda: self.count_label.config(text="读取文件中..."))
            throttler = ProgressThrottler(lambda p: self.app.root.after(0, lambda: self.progress.config(value=p)))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(read_file, fp) for fp, _ in self.data]
                for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                    res = future.result()
                    if res: datasets.append(res)
                    pct = (idx + 1) / total * 50
                    throttler.update(pct)
            throttler.finalize(50)

            if cancel.is_set() or not datasets:
                self.app.root.after(0, lambda: self.count_label.config(text=""))
                return 0

            self.app.root.after(0, lambda: self.count_label.config(text="分配 UID 中..."))
            batch_modify_uids(datasets, method=method, new_accession=new_accession,
                              modify_patient_id=modify_pid, force_unique_study=force_unique)

            count = 0
            self.app.root.after(0, lambda: self.count_label.config(text="保存文件中..."))

            def save_file(fp, ds):
                if cancel.is_set(): return False
                try:
                    DicomEditor.save_file(ds, self._out_path(fp, src_root, out_root))
                    return True
                except Exception as e:
                    self.app.logger.exception(f"保存失败 {fp}: {e}")
                    return False

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(save_file, fp, ds) for fp, ds in datasets]
                for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                    if future.result(): count += 1
                    pct = 50 + (idx + 1) / len(datasets) * 50
                    throttler.update(pct)
            throttler.finalize(100)

            self.app.root.after(0, lambda: self.count_label.config(text=""))
            return count

        mode_tip = "（每文件独立Study）" if force_unique else "（保持Study关联）"
        self._batch_run(fn,
                   f"确定要修改 {len(self.data)} 个文件的UID吗？{mode_tip}\n（输出到源文件夹同级的 _updated 目录）",
                   "批量修改UID完成，共处理 {} 个文件")

    def _sort(self, col):
        if self.is_busy: return
        reverse = self._sort_state.get(col, False)
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            self.tree.move(k, '', idx)
        self._sort_state[col] = not reverse

def build(app) -> ttk_boot.Frame:
    return BrowserTab(app.notebook, app)

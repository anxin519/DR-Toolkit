# -*- coding: utf-8 -*-
"""文件浏览标签页 UI + 事件"""
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


def build(app) -> ttk_boot.Frame:
    frame = ttk_boot.Frame(app.notebook)

    # ── 工具栏 ────────────────────────────────────────────────────────
    toolbar = ttk_boot.Frame(frame)
    toolbar.pack(fill='x', padx=10, pady=8)

    ttk_boot.Button(toolbar, text="📂 选择文件夹",
                    command=lambda: _scan(app)).pack(side='left', padx=5)
    ttk_boot.Button(toolbar, text="📊 导出Excel", bootstyle="success",
                    command=lambda: _export(app)).pack(side='left', padx=5)

    batch_btn = ttk_boot.Menubutton(toolbar, text="批量操作 ▼", bootstyle="info")
    batch_btn.pack(side='left', padx=5)
    menu = tk.Menu(batch_btn, tearoff=0)
    batch_btn['menu'] = menu
    menu.add_command(label="批量匿名化", command=lambda: _batch_anonymize(app))
    menu.add_command(label="批量计算年龄", command=lambda: _batch_age(app))
    menu.add_command(label="批量修改UID（保持Study关联）", command=lambda: _batch_uid(app, force_unique=False))
    menu.add_separator()
    menu.add_command(label="批量修改UID（每文件独立Study）", command=lambda: _batch_uid(app, force_unique=True))

    app.browser_progress = ttk_boot.Progressbar(toolbar, mode='determinate')
    app.browser_progress.pack(side='left', fill='x', expand=True, padx=10)

    app.browser_count_label = ttk_boot.Label(toolbar, text="")
    app.browser_count_label.pack(side='left', padx=5)

    # ── 文件表格 ──────────────────────────────────────────────────────
    cols = ('path', 'name', 'patient_name', 'patient_id', 'sex', 'age', 'date', 'modality',
            'study_uid', 'series_uid', 'sop_uid')
    headers = ['路径', '文件名', '患者姓名', '病历号', '性别', '年龄', '检查日期', '模态',
               'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
    widths  = [200, 120, 100, 100, 50, 60, 90, 60, 200, 200, 200]

    app.browser_tree = ttk.Treeview(frame, columns=cols, show='headings', height=28)
    for col, header, width in zip(cols, headers, widths):
        app.browser_tree.heading(col, text=header,
                                  command=lambda c=col: _sort(app, c))
        app.browser_tree.column(col, width=width)

    sb = ttk_boot.Scrollbar(frame, orient='vertical', command=app.browser_tree.yview)
    app.browser_tree.configure(yscrollcommand=sb.set)
    app.browser_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=5)
    sb.pack(side='right', fill='y', pady=5, padx=(0, 5))

    return frame


# ── 扫描 ──────────────────────────────────────────────────────────────

def _scan(app):
    folder = filedialog.askdirectory(title="选择文件夹")
    if not folder:
        return

    def run():
        app.browser_tree.delete(*app.browser_tree.get_children())
        app.browser_data = []
        files = [os.path.join(r, fn)
                 for r, _, fns in os.walk(folder)
                 for fn in fns if fn.lower().endswith('.dcm')]
        total = len(files)
        app.root.after(0, lambda: app.browser_count_label.config(text=f"共 {total} 个文件"))

        for idx, fp in enumerate(files):
            try:
                ds = pydicom.dcmread(fp, stop_before_pixels=True)
                fix_dataset_encoding(ds)
                row = (
                    fp, os.path.basename(fp),
                    safe_str(getattr(ds, 'PatientName', ''), ds),
                    safe_str(getattr(ds, 'PatientID', ''), ds),
                    str(getattr(ds, 'PatientSex', '')),
                    str(getattr(ds, 'PatientAge', '')),
                    str(getattr(ds, 'StudyDate', '')),
                    str(getattr(ds, 'Modality', '')),
                    str(getattr(ds, 'StudyInstanceUID', '')),
                    str(getattr(ds, 'SeriesInstanceUID', '')),
                    str(getattr(ds, 'SOPInstanceUID', '')),
                )
                app.browser_data.append((fp, ds))
                app.root.after(0, lambda r=row: app.browser_tree.insert('', 'end', values=r))
            except Exception as e:
                print(f"读取失败 {fp}: {e}")

            pct = (idx + 1) / total * 100
            app.root.after(0, lambda p=pct: app.browser_progress.config(value=p))

    threading.Thread(target=run, daemon=True).start()


# ── 导出 ──────────────────────────────────────────────────────────────

def _export(app):
    if not app.browser_data:
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
                 safe_str(getattr(ds, 'PatientName', ''), ds),
                 safe_str(getattr(ds, 'PatientID', ''), ds),
                 str(getattr(ds, 'PatientSex', '')),
                 str(getattr(ds, 'PatientAge', '')),
                 str(getattr(ds, 'StudyDate', '')),
                 str(getattr(ds, 'Modality', '')),
                 str(getattr(ds, 'StudyInstanceUID', '')),
                 str(getattr(ds, 'SeriesInstanceUID', '')),
                 str(getattr(ds, 'SOPInstanceUID', ''))]
                for p, ds in app.browser_data]
        ExcelExporter.export(data, fp, headers)
        messagebox.showinfo("成功", "Excel导出完成")
    except Exception as e:
        messagebox.showerror("错误", f"导出失败: {e}")


# ── 批量操作 ──────────────────────────────────────────────────────────

def _batch_run(app, fn, confirm_msg, done_msg):
    """
    批量操作通用入口，支持中断。
    输出到源文件夹同级的 <原文件夹名>_updated 目录。
    """
    if not app.browser_data:
        messagebox.showwarning("警告", "没有数据")
        return
    if not messagebox.askyesno("确认", confirm_msg):
        return

    src_root = _find_common_root([fp for fp, _ in app.browser_data])
    out_root = os.path.join(os.path.dirname(src_root),
                            os.path.basename(src_root) + "_updated")
    os.makedirs(out_root, exist_ok=True)

    # 中断事件
    import threading
    app._batch_cancel = threading.Event()

    # 显示取消按钮
    cancel_btn = ttk_boot.Button(
        app.browser_progress.master, text="✕ 取消", bootstyle="danger",
        command=lambda: app._batch_cancel.set())
    cancel_btn.pack(side='left', padx=5)

    def run():
        count = fn(app, src_root, out_root, app._batch_cancel)
        app.root.after(0, cancel_btn.destroy)
        if app._batch_cancel.is_set():
            app.root.after(0, lambda: messagebox.showinfo("已取消", f"操作已取消，已处理 {count} 个文件"))
        else:
            app.root.after(0, lambda: messagebox.showinfo("完成", done_msg.format(count) + f"\n\n输出目录:\n{out_root}"))

    threading.Thread(target=run, daemon=True).start()


def _find_common_root(paths: list[str]) -> str:
    """找出所有文件路径的最长公共父目录"""
    if not paths:
        return ''
    common = os.path.commonpath(paths)
    # 如果 common 本身是文件，取其父目录
    return common if os.path.isdir(common) else os.path.dirname(common)


def _out_path(fp: str, src_root: str, out_root: str) -> str:
    """将源文件路径映射到输出目录，保持相对子目录结构"""
    rel = os.path.relpath(fp, src_root)
    out_fp = os.path.join(out_root, rel)
    os.makedirs(os.path.dirname(out_fp), exist_ok=True)
    return out_fp


def _batch_anonymize(app):
    def fn(app, src_root, out_root, cancel):
        keep = app.config.get('anonymize.keep_last_digits', 4)
        prefix = app.config.get('anonymize.prefix', 'ANON')
        count = 0
        for idx, (fp, _) in enumerate(app.browser_data):
            if cancel.is_set():
                break
            try:
                ds = pydicom.dcmread(fp)
                DicomAnonymizer.anonymize(ds, prefix, keep)
                DicomEditor.save_file(ds, _out_path(fp, src_root, out_root))
                count += 1
            except Exception as e:
                print(f"匿名化失败 {fp}: {e}")
            pct = (idx + 1) / len(app.browser_data) * 100
            app.root.after(0, lambda p=pct: app.browser_progress.config(value=p))
        return count

    _batch_run(app, fn,
               f"确定要匿名化 {len(app.browser_data)} 个文件吗？\n（输出到源文件夹同级的 _updated 目录）",
               "批量匿名化完成，共处理 {} 个文件")



def _batch_age(app):
    def fn(app, src_root, out_root, cancel):
        count = 0
        for idx, (fp, meta_ds) in enumerate(app.browser_data):
            if cancel.is_set():
                break
            try:
                if not getattr(meta_ds, 'PatientAge', None) and getattr(meta_ds, 'PatientBirthDate', None):
                    age = calculate_age(meta_ds.PatientBirthDate, getattr(meta_ds, 'StudyDate', None))
                    if age:
                        ds = pydicom.dcmread(fp)
                        ds.PatientAge = age
                        DicomEditor.save_file(ds, _out_path(fp, src_root, out_root))
                        meta_ds.PatientAge = age
                        count += 1
            except Exception as e:
                print(f"计算年龄失败 {fp}: {e}")
            pct = (idx + 1) / len(app.browser_data) * 100
            app.root.after(0, lambda p=pct: app.browser_progress.config(value=p))
        return count

    _batch_run(app, fn,
               "批量计算并填充缺失年龄？\n（输出到源文件夹同级的 _updated 目录）",
               "已处理 {} 个文件")


def _batch_uid(app, force_unique=False):
    def fn(app, src_root, out_root, cancel):
        method = app.config.get('uid_strategy.method', 'regenerate')
        new_accession = app.config.get('uid_strategy.new_accession', True)
        modify_pid = app.config.get('uid_strategy.modify_patient_id', True)
        from utils.uid_generator import batch_modify_uids

        datasets = []
        for fp, _ in app.browser_data:
            if cancel.is_set():
                break
            try:
                ds = pydicom.dcmread(fp)
                datasets.append((fp, ds))
            except Exception as e:
                print(f"读取失败 {fp}: {e}")

        if not cancel.is_set():
            batch_modify_uids(datasets, method=method, new_accession=new_accession,
                              modify_patient_id=modify_pid, force_unique_study=force_unique)

        count = 0
        for idx, (fp, ds) in enumerate(datasets):
            if cancel.is_set():
                break
            try:
                DicomEditor.save_file(ds, _out_path(fp, src_root, out_root))
                count += 1
            except Exception as e:
                print(f"保存失败 {fp}: {e}")
            pct = (idx + 1) / len(datasets) * 100
            app.root.after(0, lambda p=pct: app.browser_progress.config(value=p))

        return count

    mode_tip = "（每文件独立Study）" if force_unique else "（保持Study关联）"
    _batch_run(app, fn,
               f"确定要修改 {len(app.browser_data)} 个文件的UID吗？{mode_tip}\n（输出到源文件夹同级的 _updated 目录）",
               "批量修改UID完成，共处理 {} 个文件")


# ── 列排序 ────────────────────────────────────────────────────────────

def _sort(app, col):
    if not hasattr(app, '_browser_sort_state'):
        app._browser_sort_state = {}
    reverse = app._browser_sort_state.get(col, False)
    data = [(app.browser_tree.set(k, col), k) for k in app.browser_tree.get_children('')]
    data.sort(reverse=reverse)
    for idx, (_, k) in enumerate(data):
        app.browser_tree.move(k, '', idx)
    app._browser_sort_state[col] = not reverse

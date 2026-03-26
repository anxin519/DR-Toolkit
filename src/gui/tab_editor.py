# -*- coding: utf-8 -*-
"""编辑器标签页 UI + 事件"""
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import ttkbootstrap as ttk_boot

from dicom.editor import DicomEditor
from dicom.anonymizer import DicomAnonymizer
from dicom.image_viewer import DicomImageViewer
from utils.uid_generator import modify_uids
from utils.age_calculator import calculate_age


def build(app) -> ttk_boot.Frame:
    frame = ttk_boot.Frame(app.notebook)

    # ── 工具栏 ────────────────────────────────────────────────────────
    toolbar = ttk_boot.Frame(frame)
    toolbar.pack(fill='x', padx=10, pady=8)

    ttk_boot.Button(toolbar, text="📂 打开", command=lambda: _open(app)).pack(side='left', padx=5)
    ttk_boot.Button(toolbar, text="🔒 匿名化", command=lambda: _anonymize(app)).pack(side='left', padx=5)
    ttk_boot.Button(toolbar, text="🔑 修改UID", command=lambda: _modify_uid(app)).pack(side='left', padx=5)

    app.btn_calc_age = ttk_boot.Button(toolbar, text="🎂 计算年龄", command=lambda: _calc_age(app))
    # 默认隐藏，有出生日期且无年龄时才显示
    app.btn_calc_age.pack(side='left', padx=5)
    app.btn_calc_age.pack_forget()

    ttk_boot.Button(toolbar, text="💾 保存", bootstyle="success",
                    command=lambda: _save(app)).pack(side='right', padx=5)
    # ── 内容区（左图像 + 右标签） ─────────────────────────────────────
    content = ttk_boot.Frame(frame)
    content.pack(fill='both', expand=True, padx=10, pady=5)

    # 左：图像
    img_frame = ttk_boot.Labelframe(content, text="图像", padding=8)
    img_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

    app.image_canvas = tk.Canvas(img_frame, bg='black')
    app.image_canvas.pack(fill='both', expand=True)

    ww_bar = ttk_boot.Frame(img_frame)
    ww_bar.pack(fill='x', pady=4)

    ttk_boot.Label(ww_bar, text="窗位:").pack(side='left', padx=4)
    app.wc_var = tk.IntVar(value=0)
    ttk_boot.Scale(ww_bar, from_=-2000, to=2000, variable=app.wc_var,
                   command=lambda _: _update_window(app), orient='horizontal'
                   ).pack(side='left', fill='x', expand=True, padx=4)

    ttk_boot.Label(ww_bar, text="窗宽:").pack(side='left', padx=4)
    app.ww_var = tk.IntVar(value=400)
    ttk_boot.Scale(ww_bar, from_=1, to=4000, variable=app.ww_var,
                   command=lambda _: _update_window(app), orient='horizontal'
                   ).pack(side='left', fill='x', expand=True, padx=4)

    for label, preset in [("肺窗", 'lung'), ("纵隔", 'mediastinum'),
                           ("骨窗", 'bone'), ("软组织", 'soft_tissue')]:
        ttk_boot.Button(ww_bar, text=label, bootstyle="info-outline", width=5,
                        command=lambda p=preset: _apply_preset(app, p)).pack(side='left', padx=2)

    # 右：标签
    tag_frame = ttk_boot.Labelframe(content, text="DICOM 标签", padding=8)
    tag_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

    # 标签操作按钮行
    tag_btn = ttk_boot.Frame(tag_frame)
    tag_btn.pack(fill='x', pady=(0, 4))
    ttk_boot.Label(tag_btn, text="直接编辑下方文本后点「应用修改」", bootstyle="secondary").pack(side='left', padx=4)
    ttk_boot.Button(tag_btn, text="应用标签修改", bootstyle="warning",
                    command=lambda: _apply_tag_edits(app)).pack(side='right', padx=4)

    app.tag_text = scrolledtext.ScrolledText(tag_frame, font=('Consolas', 9))
    app.tag_text.pack(fill='both', expand=True)

    return frame


# ── 事件处理 ──────────────────────────────────────────────────────────

def _open(app):
    fp = filedialog.askopenfilename(
        title="打开DICOM文件", filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")])
    if not fp:
        return
    try:
        app.current_dataset = DicomEditor.load_file(fp)
        app.current_filepath = fp
        _refresh_tags(app)
        _display_image(app)
        _check_age_btn(app)
    except Exception as e:
        messagebox.showerror("错误", f"打开失败: {e}")


def _refresh_tags(app):
    app.tag_text.delete('1.0', 'end')
    app.tag_text.insert('1.0', DicomEditor.dataset_to_text(app.current_dataset))


def _display_image(app):
    if not app.current_dataset:
        return
    try:
        px = DicomImageViewer.load_image(app.current_dataset)
        if px is None:
            return
        ww = DicomImageViewer.get_window_from_dicom(app.current_dataset)
        center, width = ww if ww else DicomImageViewer.auto_window(px)
        app.wc_var.set(center)
        app.ww_var.set(width)
        _render(app, px, center, width)
    except Exception as e:
        print(f"显示图像失败: {e}")


def _render(app, px, center, width):
    try:
        pil = DicomImageViewer.to_pil_image(px, center, width)
        if pil is None:
            return
        cw = app.image_canvas.winfo_width()
        ch = app.image_canvas.winfo_height()
        if cw > 1 and ch > 1:
            pil = DicomImageViewer.resize_image(pil, cw, ch)
        app.current_tk_image = DicomImageViewer.to_tk_image(pil)
        if app.current_tk_image:
            app.image_canvas.delete('all')
            app.image_canvas.create_image(cw // 2, ch // 2, image=app.current_tk_image)
    except Exception as e:
        print(f"渲染图像失败: {e}")


def _update_window(app):
    if not app.current_dataset:
        return
    px = DicomImageViewer.load_image(app.current_dataset)
    if px is not None:
        _render(app, px, app.wc_var.get(), app.ww_var.get())


def _apply_preset(app, preset_name):
    presets = app.config.get('ui_settings.window_presets', {})
    if preset_name in presets:
        p = presets[preset_name]
        app.wc_var.set(p['center'])
        app.ww_var.set(p['width'])
        _update_window(app)


def _check_age_btn(app):
    ds = app.current_dataset
    if ds and (not getattr(ds, 'PatientAge', None)):
        app.btn_calc_age.pack(side='left', padx=5)
    else:
        app.btn_calc_age.pack_forget()


def _anonymize(app):
    if not app.current_dataset:
        messagebox.showwarning("警告", "请先打开文件")
        return
    keep = app.config.get('anonymize.keep_last_digits', 4)
    prefix = app.config.get('anonymize.prefix', 'ANON')
    DicomAnonymizer.anonymize(app.current_dataset, prefix, keep)
    _refresh_tags(app)
    messagebox.showinfo("成功", "匿名化完成")


def _modify_uid(app):
    if not app.current_dataset:
        messagebox.showwarning("警告", "请先打开文件")
        return
    method = app.config.get('uid_strategy.method', 'regenerate')
    new_accession = app.config.get('uid_strategy.new_accession', True)
    modify_pid = app.config.get('uid_strategy.modify_patient_id', True)

    app.current_dataset = modify_uids(app.current_dataset, method,
                                       modify_patient_id=modify_pid)
    if new_accession:
        import random
        from datetime import datetime
        app.current_dataset.AccessionNumber = f"{datetime.now().strftime('%Y%m%d')}{random.randint(1000,9999)}"

    _refresh_tags(app)
    changed = ["SOPInstanceUID", "SeriesInstanceUID", "StudyInstanceUID", "AccessionNumber"]
    if modify_pid:
        changed.append("PatientID")
    messagebox.showinfo("成功", "已重新生成:\n" + "\n".join(f"  • {f}" for f in changed))


def _calc_age(app):
    ds = app.current_dataset
    if not ds or not getattr(ds, 'PatientBirthDate', None):
        messagebox.showwarning("警告", "文件中没有出生日期")
        return
    age = calculate_age(ds.PatientBirthDate, getattr(ds, 'StudyDate', None))
    if age:
        ds.PatientAge = age
        _refresh_tags(app)
        app.btn_calc_age.pack_forget()
        messagebox.showinfo("成功", f"年龄已计算: {age}")
    else:
        messagebox.showerror("错误", "无法计算年龄")


def _save(app):
    if not app.current_dataset:
        messagebox.showwarning("警告", "没有可保存的文件")
        return
    fp = filedialog.asksaveasfilename(
        title="保存DICOM文件", defaultextension=".dcm",
        filetypes=[("DICOM Files", "*.dcm")])
    if fp:
        try:
            DicomEditor.save_file(app.current_dataset, fp)
            messagebox.showinfo("成功", "文件已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


def _apply_tag_edits(app):
    """
    解析标签文本框中的内容，将修改应用回 dataset。
    格式：(gggg, eeee)  KeywordName  [VR]  value
    只处理有 keyword 且 VR 为常见字符串类型的标签。
    """
    if not app.current_dataset:
        messagebox.showwarning("警告", "请先打开文件")
        return

    import re
    STRING_VRS = {'LO', 'LT', 'PN', 'SH', 'ST', 'UC', 'UI', 'UR', 'UT',
                  'CS', 'DA', 'DS', 'DT', 'IS', 'TM', 'AE', 'AS'}

    text = app.tag_text.get('1.0', 'end')
    # 匹配格式：(gggg, eeee)  Keyword  [VR]  value
    pattern = re.compile(
        r'\(([0-9a-fA-F]{4}),\s*([0-9a-fA-F]{4})\)\s+(\w+)\s+\[(\w+)\]\s+(.*)')

    updated = 0
    errors = []
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        group, elem, keyword, vr, value = m.groups()
        value = value.strip()
        if vr not in STRING_VRS or not keyword or keyword == 'PixelData':
            continue
        try:
            tag = (int(group, 16), int(elem, 16))
            if tag in app.current_dataset:
                app.current_dataset[tag].value = value
                updated += 1
        except Exception as e:
            errors.append(f"{keyword}: {e}")

    _refresh_tags(app)
    msg = f"已更新 {updated} 个标签"
    if errors:
        msg += f"\n\n以下标签更新失败:\n" + "\n".join(errors[:5])
    messagebox.showinfo("应用完成", msg)

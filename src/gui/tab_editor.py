import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import ttkbootstrap as ttk_boot
import re

from dicom.editor import DicomEditor
from dicom.anonymizer import DicomAnonymizer
from dicom.image_viewer import DicomImageViewer
from utils.uid_generator import modify_uids
from utils.age_calculator import calculate_age

class EditorTab(ttk_boot.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.current_dataset = None
        self.current_filepath = None
        self.current_tk_image = None
        self._cached_pixel_array = None
        self.wc_var = tk.IntVar(value=0)
        self.ww_var = tk.IntVar(value=400)
        self.tag_search_var = tk.StringVar()
        
        self._build_ui()

    def _build_ui(self):
        # ── 工具栏 ──
        toolbar = ttk_boot.Frame(self)
        toolbar.pack(fill='x', padx=10, pady=8)

        ttk_boot.Button(toolbar, text="📂 打开", command=self._open).pack(side='left', padx=5)
        ttk_boot.Button(toolbar, text="🔒 匿名化", command=self._anonymize).pack(side='left', padx=5)
        ttk_boot.Button(toolbar, text="🔑 修改UID", command=self._modify_uid).pack(side='left', padx=5)

        self.btn_calc_age = ttk_boot.Button(toolbar, text="🎂 计算年龄", command=self._calc_age)
        self.btn_calc_age.pack(side='left', padx=5)
        self.btn_calc_age.pack_forget()

        ttk_boot.Button(toolbar, text="💾 保存", bootstyle="success", command=self._save).pack(side='right', padx=5)
        
        # ── 内容区（左图像 + 右标签） ──
        content = ttk_boot.Frame(self)
        content.pack(fill='both', expand=True, padx=10, pady=5)

        # 左：图像
        img_frame = ttk_boot.Labelframe(content, text="图像", padding=8)
        img_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

        self.image_canvas = tk.Canvas(img_frame, bg='black')
        self.image_canvas.pack(fill='both', expand=True)

        ww_bar = ttk_boot.Frame(img_frame)
        ww_bar.pack(fill='x', pady=4)

        ttk_boot.Label(ww_bar, text="窗位:").pack(side='left', padx=4)
        ttk_boot.Scale(ww_bar, from_=-2000, to=2000, variable=self.wc_var,
                       command=lambda _: self._update_window(), orient='horizontal').pack(side='left', fill='x', expand=True, padx=4)

        ttk_boot.Label(ww_bar, text="窗宽:").pack(side='left', padx=4)
        ttk_boot.Scale(ww_bar, from_=1, to=4000, variable=self.ww_var,
                       command=lambda _: self._update_window(), orient='horizontal').pack(side='left', fill='x', expand=True, padx=4)

        for label, preset in [("肺窗", 'lung'), ("纵隔", 'mediastinum'),
                               ("骨窗", 'bone'), ("软组织", 'soft_tissue')]:
            ttk_boot.Button(ww_bar, text=label, bootstyle="info-outline", width=5,
                            command=lambda p=preset: self._apply_preset(p)).pack(side='left', padx=2)

        # 右：标签
        tag_frame = ttk_boot.Labelframe(content, text="DICOM 标签", padding=8)
        tag_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

        tag_btn = ttk_boot.Frame(tag_frame)
        tag_btn.pack(fill='x', pady=(0, 4))
        ttk_boot.Label(tag_btn, text="直接编辑下方文本后点「应用修改」", bootstyle="secondary").pack(side='left', padx=4)
        ttk_boot.Button(tag_btn, text="应用标签修改", bootstyle="warning",
                        command=self._apply_tag_edits).pack(side='right', padx=4)

        search_bar = ttk_boot.Frame(tag_frame)
        search_bar.pack(fill='x', pady=(0, 4))
        ttk_boot.Label(search_bar, text="🔍").pack(side='left', padx=2)
        search_entry = ttk_boot.Entry(search_bar, textvariable=self.tag_search_var, width=25)
        search_entry.pack(side='left', fill='x', expand=True, padx=4)
        search_entry.bind('<Return>', lambda e: self._search_tag())
        self.tag_search_var.trace_add('write', lambda *_: self._search_tag())
        self.tag_search_count = ttk_boot.Label(search_bar, text="", bootstyle="secondary")
        self.tag_search_count.pack(side='left', padx=4)

        self.tag_text = scrolledtext.ScrolledText(tag_frame, font=('Consolas', 9))
        self.tag_text.pack(fill='both', expand=True)
        self.tag_text.tag_configure('search_highlight', background='#FFFF00', foreground='#000000')

    def _search_tag(self):
        keyword = self.tag_search_var.get().strip()
        self.tag_text.tag_remove('search_highlight', '1.0', 'end')

        if not keyword:
            self.tag_search_count.config(text="")
            return

        count = 0
        start = '1.0'
        first_pos = None

        while True:
            pos = self.tag_text.search(keyword, start, stopindex='end', nocase=True)
            if not pos:
                break
            end_pos = f"{pos}+{len(keyword)}c"
            self.tag_text.tag_add('search_highlight', pos, end_pos)
            if first_pos is None:
                first_pos = pos
            count += 1
            start = end_pos

        self.tag_search_count.config(text=f"{count} 个匹配" if count > 0 else "无匹配")
        if first_pos:
            self.tag_text.see(first_pos)

    def _open(self):
        fp = filedialog.askopenfilename(
            title="打开DICOM文件", filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")])
        if not fp: return
        try:
            self.current_dataset = DicomEditor.load_file(fp)
            self.current_filepath = fp
            self._refresh_tags()
            self._display_image()
            self._check_age_btn()
        except Exception as e:
            messagebox.showerror("错误", f"打开失败: {e}")

    def _refresh_tags(self):
        self.tag_text.delete('1.0', 'end')
        self.tag_text.insert('1.0', DicomEditor.dataset_to_text(self.current_dataset))

    def _display_image(self):
        if not self.current_dataset: return
        try:
            px = DicomImageViewer.load_image(self.current_dataset)
            if px is None:
                self._cached_pixel_array = None
                return
            self._cached_pixel_array = px
            ww = DicomImageViewer.get_window_from_dicom(self.current_dataset)
            center, width = ww if ww else DicomImageViewer.auto_window(px)
            self.wc_var.set(center)
            self.ww_var.set(width)
            self._render(px, center, width)
        except Exception as e:
            self.app.logger.exception(f"显示图像失败: {e}")

    def _render(self, px, center, width):
        try:
            pil = DicomImageViewer.to_pil_image(px, center, width)
            if pil is None: return
            cw = self.image_canvas.winfo_width()
            ch = self.image_canvas.winfo_height()
            if cw > 1 and ch > 1:
                pil = DicomImageViewer.resize_image(pil, cw, ch)
            self.current_tk_image = DicomImageViewer.to_tk_image(pil)
            if self.current_tk_image:
                self.image_canvas.delete('all')
                self.image_canvas.create_image(cw // 2, ch // 2, image=self.current_tk_image)
        except Exception as e:
            self.app.logger.exception(f"渲染图像失败: {e}")

    def _update_window(self):
        if not self.current_dataset: return
        px = self._cached_pixel_array
        if px is None:
            px = DicomImageViewer.load_image(self.current_dataset)
            self._cached_pixel_array = px
        if px is not None:
            self._render(px, self.wc_var.get(), self.ww_var.get())

    def _apply_preset(self, preset_name):
        presets = self.app.config.get('ui_settings.window_presets', {})
        if preset_name in presets:
            p = presets[preset_name]
            self.wc_var.set(p['center'])
            self.ww_var.set(p['width'])
            self._update_window()

    def _check_age_btn(self):
        ds = self.current_dataset
        if ds and (not getattr(ds, 'PatientAge', None)):
            self.btn_calc_age.pack(side='left', padx=5)
        else:
            self.btn_calc_age.pack_forget()

    def _anonymize(self):
        if not self.current_dataset:
            messagebox.showwarning("警告", "请先打开文件")
            return
        keep = self.app.config.get('anonymize.keep_last_digits', 4)
        prefix = self.app.config.get('anonymize.prefix', 'ANON')
        DicomAnonymizer.anonymize(self.current_dataset, prefix, keep)
        self._refresh_tags()
        messagebox.showinfo("成功", "匿名化完成")

    def _modify_uid(self):
        if not self.current_dataset:
            messagebox.showwarning("警告", "请先打开文件")
            return
        method = self.app.config.get('uid_strategy.method', 'regenerate')
        new_accession = self.app.config.get('uid_strategy.new_accession', True)
        modify_pid = self.app.config.get('uid_strategy.modify_patient_id', True)

        self.current_dataset = modify_uids(self.current_dataset, method, modify_patient_id=modify_pid)
        if new_accession:
            import random
            from datetime import datetime
            self.current_dataset.AccessionNumber = f"{datetime.now().strftime('%Y%m%d')}{random.randint(1000,9999)}"

        self._refresh_tags()
        changed = ["SOPInstanceUID", "SeriesInstanceUID", "StudyInstanceUID", "AccessionNumber"]
        if modify_pid: changed.append("PatientID")
        messagebox.showinfo("成功", "已重新生成:\n" + "\n".join(f"  • {f}" for f in changed))

    def _calc_age(self):
        ds = self.current_dataset
        if not ds or not getattr(ds, 'PatientBirthDate', None):
            messagebox.showwarning("警告", "文件中没有出生日期")
            return
        age = calculate_age(ds.PatientBirthDate, getattr(ds, 'StudyDate', None))
        if age:
            ds.PatientAge = age
            self._refresh_tags()
            self.btn_calc_age.pack_forget()
            messagebox.showinfo("成功", f"年龄已计算: {age}")
        else:
            messagebox.showerror("错误", "无法计算年龄")

    def _save(self):
        if not self.current_dataset:
            messagebox.showwarning("警告", "没有可保存的文件")
            return
        fp = filedialog.asksaveasfilename(
            title="保存DICOM文件", defaultextension=".dcm",
            filetypes=[("DICOM Files", "*.dcm")])
        if fp:
            try:
                DicomEditor.save_file(self.current_dataset, fp)
                messagebox.showinfo("成功", "文件已保存")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}")

    def _apply_tag_edits(self):
        if not self.current_dataset:
            messagebox.showwarning("警告", "请先打开文件")
            return

        from pydicom.values import convert_value

        STRING_VRS = {'LO', 'LT', 'PN', 'SH', 'ST', 'UC', 'UI', 'UR', 'UT',
                      'CS', 'DA', 'DS', 'DT', 'IS', 'TM', 'AE', 'AS'}
        INT_VRS = {'US', 'SS', 'UL', 'SL', 'AT'}
        FLOAT_VRS = {'FL', 'FD'}

        text = self.tag_text.get('1.0', 'end')
        pattern = re.compile(r'\(([0-9a-fA-F]{4}),\s*([0-9a-fA-F]{4})\)\s+(\S+)\s+\[([A-Z]{2})\]\s+(.*)')

        updated = 0
        errors = []
        for line in text.splitlines():
            m = pattern.match(line.strip())
            if not m: continue
            group, elem, keyword, vr, value = m.groups()
            value = value.strip()
            if not keyword or keyword == 'PixelData': continue
            try:
                tag = (int(group, 16), int(elem, 16))
                if tag not in self.current_dataset: continue
                if vr in STRING_VRS:
                    self.current_dataset[tag].value = value
                    updated += 1
                elif vr in INT_VRS:
                    self.current_dataset[tag].value = int(value)
                    updated += 1
                elif vr in FLOAT_VRS:
                    self.current_dataset[tag].value = float(value)
                    updated += 1
            except Exception as e:
                errors.append(f"{keyword}: {e}")

        self._refresh_tags()
        msg = f"已更新 {updated} 个标签"
        if errors:
            msg += f"\n\n以下标签更新失败:\n" + "\n".join(errors[:5])
        messagebox.showinfo("应用完成", msg)

def build(app) -> ttk_boot.Frame:
    return EditorTab(app.notebook, app)

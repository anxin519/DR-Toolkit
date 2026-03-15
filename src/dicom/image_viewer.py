# -*- coding: utf-8 -*-
"""DICOM图像查看器"""
import numpy as np
from PIL import Image, ImageTk


class DicomImageViewer:
    """DICOM图像处理和显示"""

    @staticmethod
    def load_image(dataset):
        """
        加载DICOM图像数据，多帧取第一帧。
        返回: 2D numpy array 或 None
        """
        if not hasattr(dataset, 'pixel_array'):
            return None
        try:
            pixel_array = dataset.pixel_array
            # 多帧取第一帧
            if pixel_array.ndim == 3:
                pixel_array = pixel_array[0]
            return pixel_array
        except Exception as e:
            print(f"加载图像失败: {e}")
            return None

    @staticmethod
    def apply_window(pixel_array, center, width):
        """应用窗宽窗位，返回 uint8 数组"""
        if pixel_array is None:
            return None
        width = max(width, 1)  # 防止除零
        img = pixel_array.astype(float)
        min_val = center - width / 2
        max_val = center + width / 2
        img = np.clip(img, min_val, max_val)
        img = (img - min_val) / (max_val - min_val) * 255.0
        return img.astype(np.uint8)

    @staticmethod
    def auto_window(pixel_array):
        """
        自动计算最佳窗宽窗位（2%~98%分位数）
        返回: (center, width)
        """
        if pixel_array is None:
            return (0, 400)
        min_val = float(np.percentile(pixel_array, 2))
        max_val = float(np.percentile(pixel_array, 98))
        width = max(int(max_val - min_val), 1)
        center = int((min_val + max_val) / 2)
        return (center, width)

    @staticmethod
    def get_window_from_dicom(dataset):
        """
        从DICOM标签获取窗宽窗位。
        返回: (center, width) 或 None
        """
        try:
            if hasattr(dataset, 'WindowCenter') and hasattr(dataset, 'WindowWidth'):
                center = dataset.WindowCenter
                width = dataset.WindowWidth
                # 处理多值（DSfloat序列）
                if hasattr(center, '__iter__') and not isinstance(center, str):
                    center = list(center)[0]
                if hasattr(width, '__iter__') and not isinstance(width, str):
                    width = list(width)[0]
                return (int(float(center)), int(float(width)))
        except Exception:
            pass
        return None

    @staticmethod
    def to_pil_image(pixel_array, center, width):
        """转换为 PIL Image"""
        img_array = DicomImageViewer.apply_window(pixel_array, center, width)
        if img_array is None:
            return None
        if img_array.ndim == 2:
            return Image.fromarray(img_array, mode='L')
        return Image.fromarray(img_array)

    @staticmethod
    def resize_image(pil_img, max_width, max_height):
        """等比缩放以适应显示区域"""
        if pil_img is None or max_width < 1 or max_height < 1:
            return pil_img
        w, h = pil_img.size
        ratio = min(max_width / w, max_height / h)
        if ratio < 1:
            pil_img = pil_img.resize(
                (int(w * ratio), int(h * ratio)),
                Image.Resampling.LANCZOS
            )
        return pil_img

    @staticmethod
    def to_tk_image(pil_img):
        """转换为 Tkinter PhotoImage"""
        if pil_img is None:
            return None
        return ImageTk.PhotoImage(pil_img)

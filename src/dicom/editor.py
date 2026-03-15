# -*- coding: utf-8 -*-
"""DICOM标签编辑器"""
import pydicom
from pydicom.tag import Tag

try:
    from utils.charset_helper import fix_dataset_encoding, safe_str
except ImportError:
    from src.utils.charset_helper import fix_dataset_encoding, safe_str


class DicomEditor:
    """DICOM标签编辑"""

    @staticmethod
    def load_file(filepath):
        """加载DICOM文件，自动修复中文乱码"""
        ds = pydicom.dcmread(filepath)
        fix_dataset_encoding(ds)
        return ds

    @staticmethod
    def save_file(dataset, filepath):
        """保存DICOM文件"""
        try:
            dataset.save_as(filepath, write_like_original=False)
        except TypeError:
            dataset.save_as(filepath)

    @staticmethod
    def get_tag_value(dataset, tag):
        """获取标签值（返回可读字符串）"""
        try:
            if isinstance(tag, str):
                val = getattr(dataset, tag, None)
            else:
                val = dataset[tag].value
            return safe_str(val, dataset) if val is not None else None
        except Exception:
            return None

    @staticmethod
    def set_tag_value(dataset, tag, value):
        """设置标签值"""
        try:
            if isinstance(tag, str):
                setattr(dataset, tag, value)
            else:
                dataset[tag].value = value
            return True
        except Exception:
            return False

    @staticmethod
    def dataset_to_text(dataset) -> str:
        """
        将 dataset 转为可读文本，中文字段自动修复乱码。
        """
        lines = []
        for elem in dataset:
            try:
                tag_str = str(elem.tag)
                name = elem.keyword or elem.name
                vr = elem.VR
                # 跳过像素数据
                if elem.tag == (0x7FE0, 0x0010):
                    lines.append(f"{tag_str}  {name}  [{vr}]  <像素数据>")
                    continue
                val = safe_str(elem.value, dataset)
                lines.append(f"{tag_str}  {name}  [{vr}]  {val}")
            except Exception as e:
                lines.append(f"{elem.tag}  <读取错误: {e}>")
        return "\n".join(lines)

# -*- coding: utf-8 -*-
"""UID生成和修改工具"""
from pydicom.uid import generate_uid
from datetime import datetime

# DICOM UID最大长度限制
_MAX_UID_LEN = 64


def _safe_append(original_uid: str, suffix: str) -> str:
    """
    安全追加后缀，确保不超过64字符。
    若追加后超长，则截断原UID前缀以腾出空间。
    """
    separator = "."
    full = f"{original_uid}{separator}{suffix}"
    if len(full) <= _MAX_UID_LEN:
        return full
    # 截断原UID，保留后缀
    max_prefix = _MAX_UID_LEN - len(separator) - len(suffix)
    if max_prefix <= 0:
        # 后缀本身就超长，直接生成新UID
        return generate_uid()
    return f"{original_uid[:max_prefix]}{separator}{suffix}"


def generate_new_uid() -> str:
    """生成新的DICOM UID"""
    return generate_uid()


def modify_uids(dataset, method="append_timestamp", custom_suffix=""):
    """
    修改数据集中的关键UID
    method: append_timestamp | regenerate | custom_suffix
    """
    if method == "append_timestamp":
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]  # 精确到毫秒
        for attr in ('SOPInstanceUID', 'SeriesInstanceUID', 'StudyInstanceUID'):
            if hasattr(dataset, attr):
                setattr(dataset, attr, _safe_append(str(getattr(dataset, attr)), timestamp))

    elif method == "regenerate":
        dataset.SOPInstanceUID = generate_uid()
        if hasattr(dataset, 'SeriesInstanceUID'):
            dataset.SeriesInstanceUID = generate_uid()
        if hasattr(dataset, 'StudyInstanceUID'):
            dataset.StudyInstanceUID = generate_uid()

    elif method == "custom_suffix" and custom_suffix:
        for attr in ('SOPInstanceUID', 'SeriesInstanceUID', 'StudyInstanceUID'):
            if hasattr(dataset, attr):
                setattr(dataset, attr, _safe_append(str(getattr(dataset, attr)), custom_suffix))

    return dataset


def batch_modify_uids(datasets, method="append_timestamp"):
    """
    批量修改UID，保持Study和Series的一致性。
    datasets: [(filepath, dataset), ...]
    """
    study_uid_map = {}
    series_uid_map = {}
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]

    for filepath, ds in datasets:
        # StudyInstanceUID - 同Study保持一致
        old_study = str(getattr(ds, 'StudyInstanceUID', ''))
        if old_study:
            if old_study not in study_uid_map:
                if method == "append_timestamp":
                    study_uid_map[old_study] = _safe_append(old_study, timestamp)
                else:
                    study_uid_map[old_study] = generate_uid()
            ds.StudyInstanceUID = study_uid_map[old_study]

        # SeriesInstanceUID - 同Series保持一致
        old_series = str(getattr(ds, 'SeriesInstanceUID', ''))
        if old_series:
            if old_series not in series_uid_map:
                if method == "append_timestamp":
                    series_uid_map[old_series] = _safe_append(old_series, timestamp)
                else:
                    series_uid_map[old_series] = generate_uid()
            ds.SeriesInstanceUID = series_uid_map[old_series]

        # SOPInstanceUID - 每个文件唯一
        old_sop = str(getattr(ds, 'SOPInstanceUID', ''))
        if old_sop:
            if method == "append_timestamp":
                # 用文件路径hash保证唯一性
                file_hash = f"{abs(hash(filepath)) % 99999:05d}"
                ds.SOPInstanceUID = _safe_append(old_sop, f"{timestamp}.{file_hash}")
            else:
                ds.SOPInstanceUID = generate_uid()

    return datasets

# -*- coding: utf-8 -*-
"""UID生成和修改工具"""
from pydicom.uid import generate_uid
from datetime import datetime
import random

_MAX_UID_LEN = 64


def _safe_append(original_uid: str, suffix: str) -> str:
    """安全追加后缀，确保不超过64字符且不含连续点。"""
    original_uid = original_uid.rstrip('.')
    full = f"{original_uid}.{suffix}"
    if len(full) <= _MAX_UID_LEN:
        return full
    max_prefix = _MAX_UID_LEN - 1 - len(suffix)
    if max_prefix <= 0:
        return generate_uid()
    return f"{original_uid[:max_prefix].rstrip('.')}.{suffix}"


def generate_new_uid() -> str:
    return generate_uid()


def modify_uids(dataset, method="regenerate", custom_suffix="", modify_patient_id=True):
    """
    修改数据集中的关键UID。

    method:
      regenerate       - 完全重新生成（推荐）
      append_timestamp - SOPInstanceUID追加时间戳，Study/Series重新生成（避免截断问题）
      custom_suffix    - 追加自定义后缀
    """
    if method in ("regenerate", "append_timestamp"):
        # Study/Series 统一重新生成，避免原UID过长截断后失去区分度
        if hasattr(dataset, 'StudyInstanceUID'):
            dataset.StudyInstanceUID = generate_uid()
        if hasattr(dataset, 'SeriesInstanceUID'):
            dataset.SeriesInstanceUID = generate_uid()
        # SOP 每个实例唯一
        if method == "append_timestamp":
            ts = datetime.now().strftime('%m%d%H%M%S%f')[:-3]  # 短时间戳
            if hasattr(dataset, 'SOPInstanceUID'):
                dataset.SOPInstanceUID = _safe_append(str(dataset.SOPInstanceUID), ts)
        else:
            if hasattr(dataset, 'SOPInstanceUID'):
                dataset.SOPInstanceUID = generate_uid()

    elif method == "custom_suffix" and custom_suffix:
        for attr in ('SOPInstanceUID', 'SeriesInstanceUID', 'StudyInstanceUID'):
            if hasattr(dataset, attr):
                setattr(dataset, attr, _safe_append(str(getattr(dataset, attr)), custom_suffix))

    # 同步 file_meta.MediaStorageSOPInstanceUID
    if hasattr(dataset, 'file_meta') and hasattr(dataset, 'SOPInstanceUID'):
        dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID

    # PatientID：原ID后追加日期，保留可读性
    if modify_patient_id and hasattr(dataset, 'PatientID') and dataset.PatientID:
        original_id = str(dataset.PatientID).strip()
        suffix = datetime.now().strftime('%m%d%H%M')
        dataset.PatientID = f"{original_id}_{suffix}"[:64]

    return dataset


def batch_modify_uids(datasets, method="regenerate", new_accession=True,
                      modify_patient_id=True, force_unique_study=False):
    """
    批量修改UID，保持Study/Series一致性。

    datasets: [(filepath, dataset), ...]
    force_unique_study: True时每个文件都生成独立的StudyUID（用于原始文件StudyUID已损坏的情况）
    """
    study_uid_map: dict = {}
    series_uid_map: dict = {}
    accession_map: dict = {}
    patient_id_map: dict = {}

    date_str = datetime.now().strftime('%Y%m%d')
    pid_suffix = datetime.now().strftime('%m%d%H%M')

    for filepath, ds in datasets:
        old_study = str(getattr(ds, 'StudyInstanceUID', ''))
        if old_study:
            # force_unique_study：每个文件强制独立Study（原始UID已损坏时使用）
            map_key = f"{old_study}_{filepath}" if force_unique_study else old_study
            if map_key not in study_uid_map:
                study_uid_map[map_key] = generate_uid()
                if new_accession:
                    accession_map[map_key] = f"{date_str}{random.randint(1000, 9999)}"
            ds.StudyInstanceUID = study_uid_map[map_key]
            if new_accession and map_key in accession_map:
                ds.AccessionNumber = accession_map[map_key]

        old_series = str(getattr(ds, 'SeriesInstanceUID', ''))
        if old_series:
            series_key = f"{old_series}_{filepath}" if force_unique_study else old_series
            if series_key not in series_uid_map:
                series_uid_map[series_key] = generate_uid()
            ds.SeriesInstanceUID = series_uid_map[series_key]

        if hasattr(ds, 'SOPInstanceUID'):
            ds.SOPInstanceUID = generate_uid()

        if hasattr(ds, 'file_meta') and hasattr(ds, 'SOPInstanceUID'):
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID

        if modify_patient_id and hasattr(ds, 'PatientID') and ds.PatientID:
            original_pid = str(ds.PatientID).strip()
            if original_pid not in patient_id_map:
                patient_id_map[original_pid] = f"{original_pid}_{pid_suffix}"[:64]
            ds.PatientID = patient_id_map[original_pid]

    return datasets

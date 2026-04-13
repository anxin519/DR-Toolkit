# -*- coding: utf-8 -*-
"""DICOM SCP - 接收服务"""
import os
from pynetdicom import AE, evt, StoragePresentationContexts
from pynetdicom.sop_class import Verification

try:
    from core.logger import Logger
except ImportError:
    from src.core.logger import Logger


class DicomSCP:
    """DICOM接收服务"""

    def __init__(self, ae_title="DICOM_TOOL", port=11112, storage_path="./storage",
                 on_received=None):
        """
        on_received: 收到文件后的回调 fn(filepath, dataset)，用于自动转发
        """
        self.ae_title = ae_title
        self.port = port
        self.storage_path = storage_path
        self.on_received = on_received
        self.server = None
        self.logger = Logger.get_logger('scp')

        self.ae = AE(ae_title=ae_title)
        self.ae.supported_contexts = StoragePresentationContexts
        self.ae.add_supported_context(Verification)

        os.makedirs(storage_path, exist_ok=True)

    def handle_store(self, event):
        """处理C-STORE请求，按 PatientID/StudyDate 分目录存储"""
        try:
            ds = event.dataset
            ds.file_meta = event.file_meta

            # 目录：PatientID/StudyDate/
            patient_id   = str(getattr(ds, 'PatientID',   'UNKNOWN')).strip() or 'UNKNOWN'
            study_date   = str(getattr(ds, 'StudyDate',   'NoDate')).strip()  or 'NoDate'
            patient_name = str(getattr(ds, 'PatientName', '')).strip()
            patient_age  = str(getattr(ds, 'PatientAge',  '')).strip()

            def _safe(s):
                """去掉文件名中的非法字符"""
                return "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in s)

            safe_id = _safe(patient_id)
            sub_dir = os.path.join(self.storage_path, safe_id, study_date)
            os.makedirs(sub_dir, exist_ok=True)

            # 文件名：姓名_年龄_日期_SOPInstanceUID.dcm
            # 例：张三_062Y_20260203_1.2.826.xxx.dcm
            parts = [_safe(patient_name) if patient_name else safe_id]
            if patient_age:
                parts.append(_safe(patient_age))
            if study_date and study_date != 'NoDate':
                parts.append(study_date)
            parts.append(str(ds.SOPInstanceUID))

            filename = "_".join(parts) + ".dcm"
            # 文件名过长时截断姓名部分，保留 UID 完整性
            if len(filename) > 200:
                parts[0] = parts[0][:20]
                filename = "_".join(parts) + ".dcm"

            filepath = os.path.join(sub_dir, filename)
            ds.save_as(filepath, write_like_original=False)

            # 触发回调（自动转发等）
            if self.on_received:
                try:
                    self.on_received(filepath, ds)
                except Exception as cb_err:
                    self.logger.exception(f"接收回调错误: {cb_err}")

            return 0x0000  # Success
        except Exception as e:
            self.logger.exception(f"存储文件失败: {e}")
            return 0xA700  # Out of Resources

    def handle_echo(self, event):
        """处理C-ECHO请求"""
        return 0x0000

    def start(self):
        """启动SCP服务（非阻塞）"""
        handlers = [
            (evt.EVT_C_STORE, self.handle_store),
            (evt.EVT_C_ECHO, self.handle_echo),
        ]
        self.server = self.ae.start_server(
            ('', self.port), evt_handlers=handlers, block=False
        )
        self.logger.info(f"DICOM SCP 已启动，端口: {self.port}")

    def stop(self):
        """停止SCP服务"""
        if self.server:
            self.server.shutdown()
            self.server = None
        else:
            self.ae.shutdown()
        self.logger.info("DICOM SCP 已停止")

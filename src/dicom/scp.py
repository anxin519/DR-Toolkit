# -*- coding: utf-8 -*-
"""DICOM SCP - 接收服务"""
import os
from pynetdicom import AE, evt, StoragePresentationContexts
from pynetdicom.sop_class import Verification


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

        self.ae = AE(ae_title=ae_title)
        self.ae.supported_contexts = StoragePresentationContexts
        self.ae.add_supported_context(Verification)

        os.makedirs(storage_path, exist_ok=True)

    def handle_store(self, event):
        """处理C-STORE请求"""
        try:
            ds = event.dataset
            ds.file_meta = event.file_meta

            filename = f"{ds.SOPInstanceUID}.dcm"
            filepath = os.path.join(self.storage_path, filename)
            ds.save_as(filepath, write_like_original=False)

            # 触发回调（自动转发等）
            if self.on_received:
                try:
                    self.on_received(filepath, ds)
                except Exception as cb_err:
                    print(f"接收回调错误: {cb_err}")

            return 0x0000  # Success
        except Exception as e:
            print(f"存储文件失败: {e}")
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
        print(f"DICOM SCP 已启动，端口: {self.port}")

    def stop(self):
        """停止SCP服务"""
        if self.server:
            self.server.shutdown()
            self.server = None
        else:
            self.ae.shutdown()
        print("DICOM SCP 已停止")

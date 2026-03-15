# -*- coding: utf-8 -*-
"""DICOM SCU - 发送客户端"""
import os
from pynetdicom import AE, StoragePresentationContexts
from pydicom import dcmread


class DicomSCU:
    """DICOM发送客户端"""

    def __init__(self, ae_title="DICOM_TOOL"):
        self.ae_title = ae_title
        self.ae = AE(ae_title=ae_title)
        self.ae.requested_contexts = StoragePresentationContexts

    def send_file(self, filepath, remote_host, remote_port, remote_ae):
        """发送单个DICOM文件（独立连接）"""
        try:
            ds = dcmread(filepath)
            assoc = self.ae.associate(remote_host, int(remote_port), ae_title=remote_ae)
            if assoc.is_established:
                status = assoc.send_c_store(ds)
                assoc.release()
                return status is not None and status.Status == 0x0000
            return False
        except Exception as e:
            print(f"发送失败 {filepath}: {e}")
            return False

    def send_batch(self, file_list, remote_host, remote_port, remote_ae):
        """
        批量发送DICOM文件（复用同一连接，失败则重连）
        返回: [(filepath, success), ...]
        """
        results = []
        assoc = None

        try:
            assoc = self.ae.associate(remote_host, int(remote_port), ae_title=remote_ae)
            if not assoc.is_established:
                # 连接失败，所有文件标记失败
                return [(fp, False) for fp in file_list]

            for filepath in file_list:
                try:
                    ds = dcmread(filepath)
                    status = assoc.send_c_store(ds)
                    success = status is not None and status.Status == 0x0000
                    results.append((filepath, success))
                except Exception as e:
                    print(f"发送失败 {filepath}: {e}")
                    results.append((filepath, False))
                    # 连接可能已断开，尝试重连
                    if not assoc.is_established:
                        assoc = self.ae.associate(remote_host, int(remote_port), ae_title=remote_ae)
                        if not assoc.is_established:
                            # 剩余文件全部标记失败
                            remaining = file_list[len(results):]
                            results.extend([(fp, False) for fp in remaining])
                            return results
        finally:
            if assoc and assoc.is_established:
                assoc.release()

        return results

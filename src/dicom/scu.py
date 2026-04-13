# -*- coding: utf-8 -*-
"""DICOM SCU - 发送客户端"""
import os
from pynetdicom import AE, StoragePresentationContexts
from pydicom import dcmread

try:
    from core.logger import Logger
except ImportError:
    from src.core.logger import Logger


class DicomSCU:
    """DICOM发送客户端"""

    def __init__(self, ae_title="DICOM_TOOL"):
        self.ae_title = ae_title
        self.ae = AE(ae_title=ae_title)
        self.ae.requested_contexts = StoragePresentationContexts
        self.logger = Logger.get_logger('scu')

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
                except ValueError as ve:
                    # pynetdicom会在找不到支持的上下文时抛出此错误（比如发送了某型号特有的压缩格式）
                    if "context" in str(ve).lower() or "syntax" in str(ve).lower():
                        self.logger.warning(f"格式不被节点支持，尝试向下降级解压后重发: {filepath}")
                        try:
                            from pydicom.uid import ImplicitVRLittleEndian
                            ds.decompress()  # 尝试解压为原始阵列 (需底层库如 pylibjpeg/gdcm 支持)
                            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
                            ds.is_little_endian = True
                            ds.is_implicit_VR = True
                            d_status = assoc.send_c_store(ds)
                            d_success = d_status is not None and d_status.Status == 0x0000
                            results.append((filepath, d_success))
                        except Exception as de:
                            self.logger.exception(f"智能降级发送失败 {filepath}: {de}")
                            results.append((filepath, False))
                    else:
                        self.logger.exception(f"发送失败 (ValueError) {filepath}: {ve}")
                        results.append((filepath, False))
                except Exception as e:
                    self.logger.exception(f"发送失败 {filepath}: {e}")
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

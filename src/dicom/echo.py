# -*- coding: utf-8 -*-
"""DICOM Echo测试"""
from pynetdicom import AE
from pynetdicom.sop_class import Verification
import time

class DicomEcho:
    """DICOM Echo测试"""
    
    @staticmethod
    def test(host, port, ae_title, local_ae="DICOM_TOOL", timeout=10):
        """
        测试DICOM连接
        返回: (success, message, response_time)
        """
        ae = AE(ae_title=local_ae)
        ae.add_requested_context(Verification)
        
        start_time = time.time()
        
        try:
            assoc = ae.associate(host, port, ae_title=ae_title, 
                               evt_handlers=[], bind_address=('', 0))
            
            if assoc.is_established:
                # 发送C-ECHO
                status = assoc.send_c_echo()
                response_time = int((time.time() - start_time) * 1000)
                
                assoc.release()
                
                if status and status.Status == 0x0000:
                    return (True, f"连接成功！\n响应时间: {response_time}ms\n远程AE: {ae_title}", response_time)
                else:
                    return (False, f"Echo失败\n状态码: {status.Status if status else 'Unknown'}", 0)
            else:
                # 连接失败，分析原因
                error_msg = "连接失败！\n"
                
                # 检查是否是超时
                if time.time() - start_time >= timeout:
                    error_msg += "错误类型: 连接超时\n"
                    error_msg += f"详细信息: 无法连接到 {host}:{port}\n"
                    error_msg += "建议: 检查网络连接、防火墙设置和目标服务是否运行"
                else:
                    error_msg += "错误类型: 连接被拒绝\n"
                    error_msg += f"详细信息: 远程节点拒绝了连接请求\n"
                    error_msg += f"建议: 检查AE Title '{ae_title}' 是否正确，或远程节点是否允许此AE连接"
                
                return (False, error_msg, 0)
                
        except ConnectionRefusedError:
            return (False, f"连接失败！\n错误类型: 连接被拒绝\n详细信息: 目标主机 {host}:{port} 拒绝连接\n建议: 检查目标服务是否运行", 0)
        except TimeoutError:
            return (False, f"连接失败！\n错误类型: 连接超时\n详细信息: 连接 {host}:{port} 超时\n建议: 检查网络连接和防火墙设置", 0)
        except Exception as e:
            return (False, f"连接失败！\n错误类型: 未知错误\n详细信息: {str(e)}\n建议: 检查所有配置参数", 0)

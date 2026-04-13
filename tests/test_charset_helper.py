import sys
import os
import unittest

# 将 src 目录加入 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.charset_helper import _is_garbled, _chinese_score, _best_decode

class TestCharsetHelper(unittest.TestCase):
    
    def test_is_garbled(self):
        """测试乱码特征识别"""
        self.assertFalse(_is_garbled("王伟"))
        self.assertFalse(_is_garbled("Hello World"))
        # 替换符
        self.assertTrue(_is_garbled("王\ufffd伟"))
        # 包含不支持的控制字符 (非\n\r\t)
        self.assertTrue(_is_garbled("王\x01伟"))
        # 典型 GBK 被当 Latin 1 读取的特征
        self.assertTrue(_is_garbled("ÍõÎ°"))

    def test_chinese_score(self):
        """测试中文覆盖率评分"""
        self.assertAlmostEqual(_chinese_score("张三"), 1.0)
        self.assertAlmostEqual(_chinese_score("张三丰A"), 0.75)
        # 乱码直接返回 -1.0
        self.assertEqual(_chinese_score("王\ufffd伟"), -1.0)
        
    def test_best_decode(self):
        """测试不同编码字节序列的最优解码"""
        gbk_bytes = "张三丰".encode("gbk")
        utf8_bytes = "张三丰".encode("utf-8")
        
        # 将 GBK 当作 ISO_IR 100(latin-1) 声明，应该能自动回退到 GBK 或 GB18030
        self.assertEqual(_best_decode(gbk_bytes, "latin-1"), "张三丰")
        
        # 将 UTF-8 当作 GBK 声明，若能解码且评分更高，应该能修复
        self.assertEqual(_best_decode(utf8_bytes, "gbk"), "张三丰")
        
if __name__ == '__main__':
    unittest.main()

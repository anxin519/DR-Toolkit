import sys
import os
import unittest
from datetime import datetime

# 将 src 目录加入 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.age_calculator import calculate_age

class TestAgeCalculator(unittest.TestCase):
    
    def test_valid_ages(self):
        """测试正常的出生日期和检查日期"""
        # 刚好过生日
        self.assertEqual(calculate_age('19900101', '20260101'), '036Y')
        # 还没过生日
        self.assertEqual(calculate_age('19900501', '20260401'), '035Y')
        # 已经过完生日
        self.assertEqual(calculate_age('19900201', '20260401'), '036Y')

    def test_missing_study_date(self):
        """测试没有传入检查日期（默认使用当前系统时间）"""
        current_year = datetime.now().year
        # 用今年减去10年前的今天
        birth = datetime.now().replace(year=current_year - 10).strftime('%Y%m%d')
        self.assertEqual(calculate_age(birth), '010Y')

    def test_invalid_lengths(self):
        """测试日期长度不符合预期的处理"""
        self.assertIsNone(calculate_age('199001'))       # 太短
        self.assertIsNone(calculate_age('19900101000'))  # 太长
        # study_date 无效长度，则回退到当前日期
        current_year = datetime.now().year
        birth = datetime.now().replace(year=current_year - 5).strftime('%Y%m%d')
        self.assertEqual(calculate_age(birth, '2026'), '005Y')

    def test_invalid_format(self):
        """测试无法解析的日期字符串"""
        self.assertIsNone(calculate_age('1990-01-01', '20260101'))
        self.assertIsNone(calculate_age('abcdefgh', '20260101'))
        self.assertIsNone(calculate_age('', ''))
        self.assertIsNone(calculate_age(None, None))
        
    def test_type_errors(self):
        """测试异常类型输入"""
        # 现在已经支持安全的数字类型强转，此处应该返回正确结果
        self.assertEqual(calculate_age(19900101, 20260101), '036Y')
        self.assertIsNone(calculate_age(['19900101'], None))

if __name__ == '__main__':
    unittest.main()

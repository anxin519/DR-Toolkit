import sys
import os
import unittest
from collections import defaultdict

# 将 src 目录加入 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.uid_generator import generate_uid, modify_uids, batch_modify_uids

class DummyDataset:
    def __init__(self, study_uid, series_uid, sop_uid):
        self.StudyInstanceUID = study_uid
        self.SeriesInstanceUID = series_uid
        self.SOPInstanceUID = sop_uid

class TestUIDGenerator(unittest.TestCase):
    
    def test_generate_uid(self):
        """测试基础的 UID 生成"""
        uid1 = generate_uid()
        uid2 = generate_uid()
        # 验证符合 DICOM UID 的一般特征，全部是数字和点
        self.assertTrue(all(c.isdigit() or c == '.' for c in uid1))
        # 验证独立调用不重复
        self.assertNotEqual(uid1, uid2)

    def test_modify_uids_append(self):
        """测试前缀保留策略（append_timestamp）"""
        ds = DummyDataset("1.2.3.4", "1.2.3.5", "1.2.3.6")
        modify_uids(ds, method="append_timestamp", custom_suffix="", modify_patient_id=False)
        
        # 验证 SOP 追加了时间戳，并且 Study/Series 重新生成（这是原有的业务逻辑要求）
        self.assertTrue(ds.SOPInstanceUID.startswith("1.2.3.6."))
        self.assertNotEqual(ds.StudyInstanceUID, "1.2.3.4")
        self.assertNotEqual(ds.SeriesInstanceUID, "1.2.3.5")

    def test_batch_modify_uids_consistency(self):
        """测试批量生成时相同 Study / Series 的一致性"""
        ds1 = DummyDataset("1.1.1", "2.2.2", "3.3.1")
        ds2 = DummyDataset("1.1.1", "2.2.2", "3.3.2")
        ds3 = DummyDataset("1.1.1", "2.2.3", "3.3.3")

        datasets = [("f1", ds1), ("f2", ds2), ("f3", ds3)]
        batch_modify_uids(datasets, force_unique_study=False, new_accession=False, modify_patient_id=False)
        
        # ds1 和 ds2 应有相同的 StudyInstanceUID 和 SeriesInstanceUID
        self.assertEqual(ds1.StudyInstanceUID, ds2.StudyInstanceUID)
        self.assertEqual(ds1.SeriesInstanceUID, ds2.SeriesInstanceUID)
        
        # ds1 和 ds3 应有相同的 StudyInstanceUID，但不同的 SeriesInstanceUID
        self.assertEqual(ds1.StudyInstanceUID, ds3.StudyInstanceUID)
        self.assertNotEqual(ds1.SeriesInstanceUID, ds3.SeriesInstanceUID)
        
        # 所有的 SOPInstanceUID 都应该独立
        self.assertNotEqual(ds1.SOPInstanceUID, ds2.SOPInstanceUID)
        self.assertNotEqual(ds1.SOPInstanceUID, ds3.SOPInstanceUID)
        self.assertNotEqual(ds2.SOPInstanceUID, ds3.SOPInstanceUID)

if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""Worklist SCP服务"""
import json
import os
import random
from datetime import datetime

from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence


class WorklistSCP:
    """Worklist SCP服务"""

    def __init__(self, ae_title="WORKLIST_SCP", port=11113,
                 data_file="config/worklist_data.json"):
        self.ae_title = ae_title
        self.port = port
        self.data_file = data_file
        self.server = None
        self.ae = AE(ae_title=ae_title)
        self.ae.add_supported_context(ModalityWorklistInformationFind)
        self.worklist_data = self.load_data()

    # ── 数据持久化 ────────────────────────────────────────────────────

    def load_data(self):
        """加载worklist数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_data(self):
        """保存worklist数据"""
        os.makedirs(os.path.dirname(self.data_file) or '.', exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.worklist_data, f, indent=2, ensure_ascii=False)

    def add_worklist_item(self, item: dict):
        self.worklist_data.append(item)
        self.save_data()

    def delete_worklist_item(self, index: int):
        if 0 <= index < len(self.worklist_data):
            del self.worklist_data[index]
            self.save_data()

    def generate_test_data(self, count=10):
        """生成随机测试数据"""
        surnames = ["张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴"]
        given = ["伟", "芳", "娜", "秀英", "敏", "静", "丽", "强", "磊", "军"]
        modalities = ["CR", "DR", "CT", "MR", "US"]
        descs = ["胸部", "腹部", "头部", "四肢", "脊柱"]

        for _ in range(count):
            birth_year = random.randint(1940, 2005)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            study_year = datetime.now().year
            age = study_year - birth_year
            item = {
                "PatientID": f"P{random.randint(100000, 999999)}",
                "PatientName": f"{random.choice(surnames)}{random.choice(given)}",
                "PatientSex": random.choice(["M", "F"]),
                "PatientAge": f"{age:03d}Y",
                "PatientBirthDate": f"{birth_year}{birth_month:02d}{birth_day:02d}",
                "StudyDate": datetime.now().strftime('%Y%m%d'),
                "StudyTime": f"{random.randint(8, 17):02d}{random.randint(0, 59):02d}00",
                "Modality": random.choice(modalities),
                "StudyDescription": f"{random.choice(descs)}检查",
                "AccessionNumber": f"ACC{random.randint(100000, 999999)}",
            }
            self.worklist_data.append(item)
        self.save_data()

    # ── C-FIND 处理 ───────────────────────────────────────────────────

    def handle_find(self, event):
        """处理C-FIND请求，逐条yield匹配结果"""
        try:
            query_ds = event.identifier
        except Exception:
            yield 0xC000, None
            return

        for item in self.worklist_data:
            if self._match_item(query_ds, item):
                yield 0xFF00, self._create_response(item)

        yield 0x0000, None  # Success / no more results

    def _match_item(self, query_ds, item: dict) -> bool:
        """简单通配符匹配（空值=不过滤）"""
        def _check(query_val, item_val):
            if not query_val:
                return True
            q = str(query_val).replace('*', '').replace('?', '').strip()
            return q.lower() in str(item_val).lower()

        if not _check(getattr(query_ds, 'PatientID', ''), item.get('PatientID', '')):
            return False
        if not _check(getattr(query_ds, 'PatientName', ''), item.get('PatientName', '')):
            return False

        # 检查模态（在ScheduledProcedureStepSequence里）
        sps_seq = getattr(query_ds, 'ScheduledProcedureStepSequence', None)
        if sps_seq:
            sps = sps_seq[0] if len(sps_seq) > 0 else None
            if sps:
                modality = getattr(sps, 'Modality', '')
                if modality and modality != item.get('Modality', ''):
                    return False
        return True

    def _create_response(self, item: dict) -> Dataset:
        """构建C-FIND响应Dataset"""
        ds = Dataset()
        ds.PatientName = item.get('PatientName', '')
        ds.PatientID = item.get('PatientID', '')
        ds.PatientSex = item.get('PatientSex', '')
        ds.PatientAge = item.get('PatientAge', '')
        ds.PatientBirthDate = item.get('PatientBirthDate', '')
        ds.AccessionNumber = item.get('AccessionNumber', '')
        ds.StudyInstanceUID = ''

        sps = Dataset()
        sps.Modality = item.get('Modality', '')
        sps.ScheduledStationAETitle = self.ae_title
        sps.ScheduledProcedureStepStartDate = item.get('StudyDate', '')
        sps.ScheduledProcedureStepStartTime = item.get('StudyTime', '')
        sps.ScheduledProcedureStepDescription = item.get('StudyDescription', '')
        sps.ScheduledProcedureStepID = item.get('AccessionNumber', '')
        ds.ScheduledProcedureStepSequence = Sequence([sps])

        return ds

    # ── 服务启停 ──────────────────────────────────────────────────────

    def start(self):
        """启动服务（非阻塞）"""
        handlers = [(evt.EVT_C_FIND, self.handle_find)]
        self.server = self.ae.start_server(
            ('', self.port), evt_handlers=handlers, block=False
        )

    def stop(self):
        """停止服务"""
        if self.server:
            self.server.shutdown()
            self.server = None
        else:
            self.ae.shutdown()

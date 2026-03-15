# -*- coding: utf-8 -*-
"""DICOM Worklist功能"""
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind
from pydicom.dataset import Dataset

class WorklistSCU:
    """Worklist查询客户端"""
    
    def __init__(self, ae_title="DICOM_TOOL"):
        self.ae = AE(ae_title=ae_title)
        self.ae.add_requested_context(ModalityWorklistInformationFind)
    
    def query(self, remote_host, remote_port, remote_ae,
              patient_id=None, patient_name=None, modality=None):
        """查询Worklist"""
        ds = Dataset()
        ds.PatientName = patient_name or ''
        ds.PatientID = patient_id or ''
        ds.PatientSex = ''
        ds.PatientAge = ''
        ds.PatientBirthDate = ''
        ds.AccessionNumber = ''

        sps = Dataset()
        sps.Modality = modality or ''
        sps.ScheduledStationAETitle = ''
        sps.ScheduledProcedureStepStartDate = ''
        sps.ScheduledProcedureStepStartTime = ''
        sps.ScheduledProcedureStepDescription = ''
        ds.ScheduledProcedureStepSequence = [sps]

        results = []
        assoc = self.ae.associate(remote_host, remote_port, ae_title=remote_ae)

        if assoc.is_established:
            responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
            for (status, identifier) in responses:
                if status and status.Status in (0xFF00, 0xFF01) and identifier:
                    results.append(identifier)
            assoc.release()
        else:
            raise ConnectionError(f"无法连接到 {remote_ae}@{remote_host}:{remote_port}")

        return results

# -*- coding: utf-8 -*-
"""DICOM匿名化处理"""
import pydicom

class DicomAnonymizer:
    """DICOM数据匿名化"""
    
    # 需要匿名化的标签
    TAGS_TO_ANONYMIZE = [
        'PatientName', 'PatientID', 'PatientBirthDate',
        'PatientSex', 'PatientAge', 'PatientAddress',
        'InstitutionName', 'ReferringPhysicianName',
        'PerformingPhysicianName', 'OperatorsName',
        'PhysiciansOfRecord', 'RequestingPhysician',
        'InstitutionAddress', 'StationName'
    ]
    
    @staticmethod
    def anonymize(dataset, patient_prefix="ANON", keep_last_digits=4):
        """
        匿名化DICOM数据集
        patient_prefix: 匿名前缀
        keep_last_digits: 保留病历号后几位
        """
        for tag in DicomAnonymizer.TAGS_TO_ANONYMIZE:
            if hasattr(dataset, tag):
                if tag == 'PatientName':
                    dataset.PatientName = f"{patient_prefix}^Patient"
                elif tag == 'PatientID':
                    original_id = str(dataset.PatientID)
                    if len(original_id) >= keep_last_digits:
                        kept_digits = original_id[-keep_last_digits:]
                        dataset.PatientID = f"{patient_prefix}_{kept_digits}"
                    else:
                        dataset.PatientID = f"{patient_prefix}_{original_id}"
                elif tag == 'PatientBirthDate':
                    dataset.PatientBirthDate = "19000101"
                else:
                    setattr(dataset, tag, "")
        
        return dataset

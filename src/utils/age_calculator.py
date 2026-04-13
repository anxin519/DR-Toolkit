# -*- coding: utf-8 -*-
"""年龄计算工具"""
from datetime import datetime

def calculate_age(birth_date, study_date=None):
    """
    根据出生日期计算年龄
    birth_date: DICOM格式日期 YYYYMMDD
    study_date: 检查日期，默认为当前日期
    返回: 年龄字符串，如 "035Y"
    """
    try:
        birth_str = str(birth_date).strip()
        if not birth_str or len(birth_str) != 8:
            return None
        
        birth = datetime.strptime(birth_str, '%Y%m%d')
        if study_date:
            study_str = str(study_date).strip()
            if len(study_str) == 8:
                study = datetime.strptime(study_str, '%Y%m%d')
            else:
                study = datetime.now()
        else:
            study = datetime.now()
        
        age_years = study.year - birth.year
        if (study.month, study.day) < (birth.month, birth.day):
            age_years -= 1
        
        return f"{age_years:03d}Y"
    except (ValueError, TypeError):
        return None

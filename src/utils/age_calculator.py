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
    if not birth_date or len(birth_date) != 8:
        return None
    
    try:
        birth = datetime.strptime(birth_date, '%Y%m%d')
        if study_date and len(study_date) == 8:
            study = datetime.strptime(study_date, '%Y%m%d')
        else:
            study = datetime.now()
        
        age_years = study.year - birth.year
        if (study.month, study.day) < (birth.month, birth.day):
            age_years -= 1
        
        return f"{age_years:03d}Y"
    except:
        return None

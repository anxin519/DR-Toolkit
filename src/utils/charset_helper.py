# -*- coding: utf-8 -*-
"""
DICOM 中文乱码修复工具

背景：
  国内 DICOM 设备常用 GB2312/GBK/GB18030 编码存储中文，但 SpecificCharacterSet
  标签可能缺失、写错（如写成 ISO_IR 6 / ISO_IR 192）或与实际编码不符，导致
  pydicom 读取后出现乱码。

策略：
  1. 优先尊重 SpecificCharacterSet 标签声明的编码
  2. 若解码结果包含乱码特征，则按优先级逐一试探候选编码
  3. 用启发式评分判断哪种编码结果"最像中文"，只输出最优结果
  4. 修复后同步更新 dataset 的 SpecificCharacterSet 标签，避免二次乱码
"""

import re
import unicodedata
import pydicom
from pydicom.dataset import Dataset

# ── DICOM SpecificCharacterSet → Python codec 映射 ────────────────────────────
_DICOM_CHARSET_MAP = {
    "ISO_IR 6":    "latin-1",
    "ISO_IR 13":   "shift_jis",
    "ISO_IR 58":   "gb2312",       # 中文简体（大陆设备最常见声明）
    "ISO_IR 100":  "latin-1",
    "ISO_IR 101":  "iso8859-2",
    "ISO_IR 109":  "iso8859-3",
    "ISO_IR 110":  "iso8859-4",
    "ISO_IR 126":  "iso8859-7",
    "ISO_IR 127":  "iso8859-6",
    "ISO_IR 138":  "iso8859-8",
    "ISO_IR 144":  "iso8859-5",
    "ISO_IR 148":  "iso8859-9",
    "ISO_IR 166":  "tis-620",
    "ISO_IR 192":  "utf-8",
    "GB18030":     "gb18030",
    "GBK":         "gbk",
    "GB2312":      "gb2312",
    "ISO 2022 IR 58": "gb2312",
}

# 试探顺序：国内设备最常见的编码优先
_CANDIDATE_ENCODINGS = [
    "gb18030",   # 兼容 GBK/GB2312，覆盖最广
    "gbk",
    "gb2312",
    "utf-8",
    "big5",      # 台湾/香港繁体
    "shift_jis", # 日文设备偶尔混入
    "latin-1",   # 最后兜底（不会抛异常，但结果可能无意义）
]

# 需要检查/修复的字符串类标签
_STRING_TAGS = [
    "PatientName", "PatientID", "PatientAddress",
    "InstitutionName", "InstitutionAddress",
    "ReferringPhysicianName", "PerformingPhysicianName",
    "OperatorsName", "StudyDescription", "SeriesDescription",
    "RequestingPhysician", "RequestedProcedureDescription",
]


# ── 启发式评分 ────────────────────────────────────────────────────────────────

def _is_garbled(text: str) -> bool:
    """快速判断字符串是否包含乱码特征"""
    if not text:
        return False
    # 替换字符（解码失败的占位符）
    if "\ufffd" in text:
        return True
    # 控制字符（除常见空白外）
    for ch in text:
        cat = unicodedata.category(ch)
        if cat == "Cc" and ch not in ("\n", "\r", "\t"):
            return True
    # 连续出现大量非打印 Latin 扩展字符（典型 GBK 被当 Latin 解码的特征）
    latin_ext = sum(1 for ch in text if "\u0080" <= ch <= "\u00ff")
    if latin_ext > len(text) * 0.3 and len(text) > 2:
        return True
    return False


def _chinese_score(text: str) -> float:
    """
    评分：文本中有效中文字符的比例（越高越好）。
    同时惩罚乱码特征。
    """
    if not text:
        return 0.0
    if _is_garbled(text):
        return -1.0
    chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff"
                  or "\u3400" <= ch <= "\u4dbf"
                  or "\uf900" <= ch <= "\ufaff")
    return chinese / max(len(text), 1)


def _try_decode(raw_bytes: bytes, encoding: str):
    """尝试用指定编码解码，失败返回 None"""
    try:
        return raw_bytes.decode(encoding, errors="strict")
    except (UnicodeDecodeError, LookupError):
        return None


def _best_decode(raw_bytes: bytes, declared_encoding = None) -> str:
    """
    用最优编码解码字节串。
    优先使用声明的编码，若结果有乱码则逐一试探候选编码，
    返回评分最高的结果。
    """
    if not raw_bytes:
        return ""

    candidates = []

    # 1. 先试声明的编码
    if declared_encoding:
        result = _try_decode(raw_bytes, declared_encoding)
        if result is not None:
            score = _chinese_score(result)
            candidates.append((score, result, declared_encoding))
            if score >= 0 and not _is_garbled(result):
                return result  # 声明编码解码正常，直接返回

    # 2. 逐一试探候选编码
    for enc in _CANDIDATE_ENCODINGS:
        if enc == declared_encoding:
            continue
        result = _try_decode(raw_bytes, enc)
        if result is not None:
            score = _chinese_score(result)
            candidates.append((score, result, enc))

    if not candidates:
        # 最后兜底：latin-1 不会抛异常
        return raw_bytes.decode("latin-1", errors="replace")

    # 取评分最高的
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# ── 公开 API ──────────────────────────────────────────────────────────────────

def get_declared_encoding(dataset: Dataset)   # type: Optional[str]:
    """从 SpecificCharacterSet 标签获取 Python codec 名称"""
    charset_tag = getattr(dataset, "SpecificCharacterSet", None)
    if not charset_tag:
        return None
    # 可能是多值（列表）
    if isinstance(charset_tag, (list, tuple)):
        charset_tag = charset_tag[0] if charset_tag else ""
    charset_str = str(charset_tag).strip()
    return _DICOM_CHARSET_MAP.get(charset_str)


def fix_string_value(raw_value, declared_encoding = None) -> str:
    """
    修复单个字符串值的乱码。
    raw_value 可以是 str（已被 pydicom 错误解码）或 bytes（原始字节）。
    """
    if raw_value is None:
        return ""

    # 如果已经是 str，先尝试判断是否乱码
    if isinstance(raw_value, str):
        if not _is_garbled(raw_value):
            return raw_value  # 已经正常，不处理
        # 乱码 str：尝试用 latin-1 还原为 bytes 再重新解码
        # （pydicom 默认用 latin-1 读取未知编码的字节）
        try:
            raw_bytes = raw_value.encode("latin-1")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return raw_value  # 无法还原，保持原样
    else:
        raw_bytes = bytes(raw_value)

    return _best_decode(raw_bytes, declared_encoding)


def fix_dataset_encoding(dataset: Dataset) -> Dataset:
    """
    修复 dataset 中所有常见字符串标签的乱码。
    同时将 SpecificCharacterSet 更新为 'ISO_IR 192'（UTF-8），
    确保后续保存/传输不再乱码。
    返回修改后的 dataset（原地修改）。
    """
    declared_enc = get_declared_encoding(dataset)

    fixed_any = False
    for tag_name in _STRING_TAGS:
        raw = getattr(dataset, tag_name, None)
        if raw is None:
            continue
        # PersonName 对象需要特殊处理
        raw_str = str(raw)
        fixed = fix_string_value(raw_str, declared_enc)
        if fixed != raw_str:
            try:
                setattr(dataset, tag_name, fixed)
                fixed_any = True
            except Exception:
                pass

    if fixed_any:
        # 更新字符集声明为 UTF-8
        # 注意：SpecificCharacterSet 的 VR 是 CS（最长16字符），ISO_IR 192 符合规范
        dataset.SpecificCharacterSet = 'ISO_IR 192'

    return dataset


def safe_str(value, dataset=None) -> str:
    """
    安全地将 DICOM 标签值转为可读字符串。
    如果 dataset 提供，会参考其 SpecificCharacterSet。
    """
    if value is None:
        return ""
    declared_enc = get_declared_encoding(dataset) if dataset else None
    raw_str = str(value)
    return fix_string_value(raw_str, declared_enc)


def diagnose(raw_bytes: bytes) -> list[dict]:
    """
    诊断模式：对给定字节串尝试所有候选编码，
    返回每种编码的解码结果和评分，按评分降序排列。
    仅输出评分 >= 0（无明显乱码）的结果。
    """
    results = []
    for enc in _CANDIDATE_ENCODINGS:
        result = _try_decode(raw_bytes, enc)
        if result is not None:
            score = _chinese_score(result)
            if score >= 0:
                results.append({
                    "encoding": enc,
                    "score": round(score, 3),
                    "text": result,
                    "garbled": _is_garbled(result),
                })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


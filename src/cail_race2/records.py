# -*- coding: utf-8 -*-
"""提交记录数据类与校验。

不变量（对应赛道说明 + 提交示例）：
- location 是「升序、互不重叠」的闭区间列表 [[s,e], ...]，区间内编号必须真实存在；
- 定位记录：非空 location ⇒ error_type ∈ {typo,inconsistency,missing_element}；
  空 location ⇒ error_type 必须为 null（表示该合同无问题）；
- 修订记录：正常记录 location 只能是单点区间 [[p,p]]；original_text 必须与原文逐字一致；
  correct_answer 非空且不含段落标签；同一 PID 不得重复修订；空记录为无操作哨兵。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ERROR_TYPES = ("typo", "inconsistency", "missing_element", "stance")
ERROR_TYPE_SET = frozenset(ERROR_TYPES)


@dataclass
class LocalizationRecord:
    contract_id: str
    location: Optional[list]
    error_type: Optional[str]

    def to_dict(self) -> dict:
        return {"contract_id": self.contract_id,
                "location": self.location,
                "error_type": self.error_type}


@dataclass
class RevisionRecord:
    contract_id: str
    location: Optional[list]
    error_types: list
    original_text: Optional[str]
    correct_answer: Optional[str]

    def to_dict(self) -> dict:
        return {"contract_id": self.contract_id,
                "location": self.location,
                "error_types": self.error_types,
                "original_text": self.original_text,
                "correct_answer": self.correct_answer}


def check_intervals(location, paragraphs: dict[int, str]) -> list[str]:
    """校验区间列表的通用规则，返回问题字符串列表（空表示通过）。"""
    errs: list[str] = []
    if location is None:
        return errs
    if not isinstance(location, list):
        return ["location 必须是数组"]
    prev_end = None
    for iv in location:
        if not (isinstance(iv, list) and len(iv) == 2
                and all(isinstance(x, int) for x in iv)):
            errs.append(f"区间形状非法: {iv!r}")
            continue
        s, e = iv
        if s > e:
            errs.append(f"区间起点大于终点: {iv!r}")
        if prev_end is not None and s <= prev_end:
            errs.append(f"区间未严格升序或重叠: {iv!r}")
        prev_end = e
        for pid in (s, e):
            if pid not in paragraphs:
                errs.append(f"段落编号不存在: {pid}")
    return errs


def validate_localization(rec: LocalizationRecord, paragraphs: dict[int, str]) -> list[str]:
    errs = check_intervals(rec.location, paragraphs)
    if not rec.location:
        if rec.error_type is not None:
            errs.append("空 location 时 error_type 必须为 null")
    elif rec.error_type not in ERROR_TYPE_SET:
        errs.append(f"非法 error_type: {rec.error_type!r}")
    return errs


def validate_revision(rec: RevisionRecord, paragraphs: dict[int, str]) -> list[str]:
    errs: list[str] = []
    loc = rec.location or []
    if not loc:
        if rec.error_types:
            errs.append("空 location 时 error_types 必须为空")
        return errs

    if not (len(loc) == 1 and len(loc[0]) == 2
            and all(isinstance(x, int) for x in loc[0]) and loc[0][0] == loc[0][1]):
        errs.append("revision.location 必须是单个单点区间 [[p,p]]")
    errs += check_intervals(loc, paragraphs)

    if not rec.error_types:
        errs.append("error_types 不能为空")
    if len(rec.error_types) != len(set(rec.error_types)):
        errs.append("error_types 存在重复")
    for et in rec.error_types:
        if et not in ERROR_TYPE_SET:
            errs.append(f"非法 error_type: {et!r}")

    pid = loc[0][0] if (loc and len(loc[0]) == 2) else None
    if rec.original_text is None:
        errs.append("original_text 不能为空")
    elif pid is not None and pid in paragraphs and rec.original_text != paragraphs[pid]:
        errs.append(f"original_text 与原文不一致: {rec.contract_id} p{pid}")
    if not rec.correct_answer:
        errs.append("correct_answer 不能为空")
    elif "<p" in rec.correct_answer or "</p" in rec.correct_answer:
        errs.append("correct_answer 不得包含段落标签")
    return errs

# -*- coding: utf-8 -*-
"""提交格式硬约束校验（可测函数版；脚本 `validate_submission.py` 调用它）。

对应赛道说明的校验项：字段完整无多余、contract_id 存在、区间升序不重叠且编号存在、
original_text 逐字一致、非空段不得改空、不得含段落标签、同一 PID 不重复修订、
修订段 error_types == 该段定位类型并集；且 localization 覆盖全部输入合同。
"""
from __future__ import annotations

from .records import (LocalizationRecord, RevisionRecord,
                      validate_localization, validate_revision)

LOC_KEYS = {"contract_id", "location", "error_type"}
REV_KEYS = {"contract_id", "location", "error_types", "original_text", "correct_answer"}


def check(contracts, loc_rows: list, rev_rows: list) -> tuple[list, list]:
    """contracts: Contract[]；loc_rows/rev_rows: [(lineno, dict)]。返回 (errors, warns)。"""
    errors: list[str] = []
    warns: list[str] = []
    by_id = {c.contract_id: c for c in contracts}

    covered: set = set()
    loc_by_pid: dict[str, dict[int, set]] = {}
    for n, obj in loc_rows:
        if "__bad__" in obj:
            errors.append(f"localization 第{n}行 JSON 错误: {obj['__bad__']}")
            continue
        if set(obj) != LOC_KEYS:
            errors.append(f"localization 第{n}行字段应为 {sorted(LOC_KEYS)}，实际 {sorted(obj)}")
            continue
        cid = obj["contract_id"]
        if cid not in by_id:
            errors.append(f"localization 第{n}行未知 contract_id: {cid!r}")
            continue
        covered.add(cid)
        rec = LocalizationRecord(cid, obj["location"], obj["error_type"])
        for e in validate_localization(rec, by_id[cid].paragraphs):
            errors.append(f"localization {cid} 第{n}行: {e}")
        if obj["location"]:
            for s, e2 in obj["location"]:
                for pid in range(s, e2 + 1):
                    loc_by_pid.setdefault(cid, {}).setdefault(pid, set()).add(obj["error_type"])

    missing = set(by_id) - covered
    if missing:
        errors.append(f"localization 未覆盖 {len(missing)} 个合同: {sorted(missing)[:5]}…")

    seen_pids: dict[str, set] = {}
    for n, obj in rev_rows:
        if "__bad__" in obj:
            errors.append(f"revision 第{n}行 JSON 错误: {obj['__bad__']}")
            continue
        if set(obj) != REV_KEYS:
            errors.append(f"revision 第{n}行字段应为 {sorted(REV_KEYS)}，实际 {sorted(obj)}")
            continue
        cid = obj["contract_id"]
        if cid not in by_id:
            errors.append(f"revision 第{n}行未知 contract_id: {cid!r}")
            continue
        rec = RevisionRecord(cid, obj["location"], obj["error_types"],
                             obj["original_text"], obj["correct_answer"])
        for e in validate_revision(rec, by_id[cid].paragraphs):
            errors.append(f"revision {cid} 第{n}行: {e}")
        if obj["location"]:
            pid = obj["location"][0][0]
            if pid in seen_pids.setdefault(cid, set()):
                errors.append(f"revision {cid} 第{n}行: 段落 p{pid} 重复修订")
            seen_pids[cid].add(pid)
            expected = loc_by_pid.get(cid, {}).get(pid, set())
            if set(obj["error_types"]) != expected:
                errors.append(f"revision {cid} p{pid}: error_types={obj['error_types']} "
                              f"与定位类型并集 {sorted(expected)} 不一致")
    return errors, warns

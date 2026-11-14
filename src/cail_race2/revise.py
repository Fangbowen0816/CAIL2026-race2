# -*- coding: utf-8 -*-
"""LLM 修订阶段：合同 + 定位 + 预分析 → RevisionRecord[]，并回填最终段落。"""
from __future__ import annotations

import json
from collections import defaultdict

from .contracts import Contract
from .prompts import revise_messages
from .records import (ERROR_TYPE_SET, LocalizationRecord, RevisionRecord)


def revise(contract_id: str, context: str, paragraphs: dict[int, str],
           locs: list[LocalizationRecord], client,
           hints: str = "") -> list[RevisionRecord]:
    contract = Contract(contract_id, context, paragraphs)
    locs_json = json.dumps([r.to_dict() for r in locs], ensure_ascii=False)
    obj = client.complete_json(revise_messages(contract, locs_json, hints))
    from .predictor import parse_revisions
    return parse_revisions(contract, obj)


def reconcile(contract_id: str, locs: list[LocalizationRecord],
              revs: list[RevisionRecord]):
    """强制「修订段 error_types == 自身定位类型并集」：
    - 已定位的 PID：用定位类型并集覆写修订的 error_types；
    - 未定位却被修订的 PID：补对应定位记录，保持自洽。
    幂等。"""
    by_pid: dict[int, set] = defaultdict(set)
    for r in locs:
        if r.error_type:
            for s, e in (r.location or []):
                for pid in range(s, e + 1):
                    by_pid[pid].add(r.error_type)

    new_locs = [r for r in locs if r.location]
    new_revs: list[RevisionRecord] = []
    for r in revs:
        loc = r.location or []
        if not (len(loc) == 1 and len(loc[0]) == 2 and loc[0][0] == loc[0][1]):
            continue
        pid = loc[0][0]
        if pid not in by_pid:
            types = [t for t in dict.fromkeys(r.error_types or []) if t in ERROR_TYPE_SET]
            if not types:
                types = ["missing_element"]
            for t in types:
                new_locs.append(LocalizationRecord(contract_id, [[pid, pid]], t))
            by_pid[pid] = set(types)
        new_revs.append(RevisionRecord(contract_id, r.location,
                                       sorted(by_pid[pid]), r.original_text,
                                       r.correct_answer))
    if not new_revs:
        new_revs = [RevisionRecord(contract_id, [], [], None, None)]
    if not new_locs:
        new_locs = [LocalizationRecord(contract_id, [], None)]
    return new_locs, new_revs


def apply_revisions(paragraphs: dict[int, str],
                    revs: list[RevisionRecord]) -> dict[int, str]:
    """按修订记录回填最终段落（未修改的保留原文）。"""
    final = dict(paragraphs)
    for r in revs:
        loc = r.location or []
        if len(loc) == 1 and r.correct_answer:
            final[loc[0][0]] = r.correct_answer
    return final

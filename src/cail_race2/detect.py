# -*- coding: utf-8 -*-
"""LLM 定位阶段：合同 + 预分析线索 → LocalizationRecord[]。"""
from __future__ import annotations

from .contracts import Contract
from .prompts import locate_messages
from .records import LocalizationRecord


def detect(contract_id: str, context: str, paragraphs: dict[int, str], client,
           hints: str = "") -> list[LocalizationRecord]:
    contract = Contract(contract_id, context, paragraphs)
    obj = client.complete_json(locate_messages(contract, hints))
    from .predictor import parse_localization
    return parse_localization(contract, obj)


def merge_deterministic(locs: list[LocalizationRecord], contract_id: str,
                        paragraphs: dict[int, str]) -> list[LocalizationRecord]:
    """把强缺失候选并入定位结果（保 recall，缺失权重最高），并去掉空哨兵。"""
    from .verify import find_missing_candidates
    merged = [r for r in locs if r.location]
    covered: set[int] = set()
    for r in merged:
        if r.error_type == "missing_element":
            for s, e in r.location:
                covered.update(range(s, e + 1))
    for c in find_missing_candidates(paragraphs, strong=True):
        pid = c.pids[0]
        if pid not in covered:
            merged.append(LocalizationRecord(contract_id, [[pid, pid]], "missing_element"))
            covered.add(pid)
    return merged or [LocalizationRecord(contract_id, [], None)]

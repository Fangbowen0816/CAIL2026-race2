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
    """把确定性候选并入定位结果并去重：
    - 跨段不一致：补齐**全部冲突侧**（事实表同槽位冲突）；
    - 强缺失候选（保 recall，缺失权重最高）；
    去掉空哨兵。"""
    from .facts import extract_facts
    from .verify import find_conflicts, find_missing_candidates
    merged = [r for r in locs if r.location]
    covered: set = set()
    for r in merged:
        if r.error_type:
            for s, e in (r.location or []):
                for pid in range(s, e + 1):
                    covered.add((pid, r.error_type))
    for c in find_conflicts(extract_facts(paragraphs)):
        for pid in sorted(set(c.pids)):
            if (pid, "inconsistency") not in covered:
                merged.append(LocalizationRecord(contract_id, [[pid, pid]], "inconsistency"))
                covered.add((pid, "inconsistency"))
    for c in find_missing_candidates(paragraphs, strong=True):
        pid = c.pids[0]
        if (pid, "missing_element") not in covered:
            merged.append(LocalizationRecord(contract_id, [[pid, pid]], "missing_element"))
            covered.add((pid, "missing_element"))
    return merged or [LocalizationRecord(contract_id, [], None)]

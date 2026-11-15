# -*- coding: utf-8 -*-
"""LLM 修订阶段：合同 + 定位 + 预分析 → RevisionRecord[]，并回填最终段落。"""
from __future__ import annotations

import html
import json
from collections import defaultdict

from .contracts import Contract
from .evaluate import edit_similarity
from .prompts import revise_messages
from .records import (ERROR_TYPE_SET, LocalizationRecord, RevisionRecord)

# typo-only 修订的最小改动阈值：相似度低于此判为“大幅改写”，抑制为原文（避免字级 FP）
_TYPO_MIN_SIM = 0.6


def guard_typo_edit(error_types, orig: str, ans: str) -> str:
    """#5/#14：typo-only 的修订若“大幅改写/添加实质内容”，则回退为原文。
    理由：字级 F0.5（beta=0.5）对**误改（FP）**惩罚重于漏改（FN）；
    错字纠正通常不增加长度，而过度补全会明显变长。"""
    if list(error_types or []) != ["typo"]:
        return ans
    if not orig or not ans:
        return ans
    if len(ans) > len(orig) + max(3, int(0.2 * len(orig))):
        return orig                                  # 添加了实质内容
    return orig if edit_similarity(ans, orig) < _TYPO_MIN_SIM else ans


def guard_revisions(contract_id: str, paragraphs: dict[int, str],
                    revs: list[RevisionRecord]) -> list[RevisionRecord]:
    out: list[RevisionRecord] = []
    for r in revs:
        loc = r.location or []
        if len(loc) == 1 and loc[0][0] == loc[0][1] and r.correct_answer is not None:
            orig = r.original_text or paragraphs.get(loc[0][0], "")
            out.append(RevisionRecord(contract_id, r.location, r.error_types, orig,
                                      guard_typo_edit(r.error_types, orig, r.correct_answer)))
        else:
            out.append(r)
    return out


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


def normalize_revisions(contract_id: str, paragraphs: dict[int, str],
                        revs: list[RevisionRecord]) -> list[RevisionRecord]:
    """把 original_text 重新回填为平台口径的段落正文（已 HTML 反转义），
    并反转义 correct_answer。幂等，用于修正缓存/模型输出。"""
    out: list[RevisionRecord] = []
    for r in revs:
        loc = r.location or []
        if len(loc) == 1 and len(loc[0]) == 2 and loc[0][0] == loc[0][1]:
            pid = loc[0][0]
            orig = paragraphs.get(pid, r.original_text)
            ans = html.unescape(r.correct_answer) if isinstance(r.correct_answer, str) \
                else r.correct_answer
            out.append(RevisionRecord(contract_id, r.location, r.error_types, orig, ans))
        else:
            out.append(r)
    return out

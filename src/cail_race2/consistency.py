# -*- coding: utf-8 -*-
"""#3 不一致的整组取值统一。

原则：同一槽位（当事人名/编号等）出现多个取值时，**整套选定一个值并同步所有位置**，
优先采用**当事人定义段**（`甲方：X；乙方：Y`）里的取值（与 gold 示例一致），
否则取出现次数最多者（并列取最早段落）。保证「整套采用、全文协调」。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .facts import Fact, PARTY_DEF_RE
from .records import LocalizationRecord, RevisionRecord


def _definition_values(paragraphs: dict[int, str]) -> dict[str, str]:
    """当事人定义段（含 `甲方：/乙方：`）给出的取值，按首次出现。"""
    out: dict[str, str] = {}
    for pid in sorted(paragraphs):
        for m in PARTY_DEF_RE.finditer(paragraphs[pid]):
            slot = m.group("paren") or m.group("label")
            out.setdefault(slot, m.group("name"))
    return out


def canonical_party(facts: list[Fact], paragraphs: dict[int, str]) -> dict[str, str]:
    groups: dict[str, list[Fact]] = defaultdict(list)
    for f in facts:
        if f.kind == "party" and f.slot:
            groups[f.slot].append(f)
    defv = _definition_values(paragraphs)
    out: dict[str, str] = {}
    for slot, fs in groups.items():
        values = {f.value for f in fs}
        if len(values) < 2:
            continue
        if slot in defv and defv[slot] in values:
            out[slot] = defv[slot]
            continue
        cnt: Counter = Counter()
        first: dict[str, int] = {}
        for f in fs:
            cnt[f.value] += 1
            first.setdefault(f.value, f.pid)
        out[slot] = sorted(cnt, key=lambda v: (-cnt[v], first[v]))[0]
    return out


def unify_party_conflicts(paragraphs: dict[int, str], facts: list[Fact]) -> dict[int, str]:
    """返回需重写的 {pid: 统一后的文本}（仅包含确实发生替换的段落）。"""
    canon = canonical_party(facts, paragraphs)
    if not canon:
        return {}
    repairs: dict[int, str] = {}
    for f in facts:
        if f.kind != "party" or f.slot not in canon or f.value == canon[f.slot]:
            continue
        text = repairs.get(f.pid, paragraphs.get(f.pid, ""))
        if f.value in text:
            repairs[f.pid] = text.replace(f.value, canon[f.slot])
    return repairs


def apply_party_unification(contract_id: str, paragraphs: dict[int, str], facts: list[Fact],
                            locs: list[LocalizationRecord], revs: list[RevisionRecord]):
    canon = canonical_party(facts, paragraphs)
    if not canon:
        return locs, revs
    wrong_by_pid: dict[int, set] = defaultdict(set)
    for f in facts:
        if f.kind == "party" and f.slot in canon and f.value != canon[f.slot]:
            wrong_by_pid[f.pid].add((f.value, canon[f.slot]))
    if not wrong_by_pid:
        return locs, revs
    # 以「已有修订文本」为基（保同段其他修复如错别字），无则用原文
    existing = {r.location[0][0]: r.correct_answer for r in revs
                if len(r.location or []) == 1 and r.location[0][0] == r.location[0][1]
                and r.correct_answer}
    loc_pids: dict[int, set] = defaultdict(set)
    for r in locs:
        if r.error_type:
            for s, e in (r.location or []):
                for pid in range(s, e + 1):
                    loc_pids[pid].add(r.error_type)
    new_locs = [r for r in locs if r.location]
    new_revs = [r for r in revs if r.location]
    for pid, pairs in wrong_by_pid.items():
        base = existing.get(pid) or paragraphs.get(pid, "")
        text = base
        for wrong, right in pairs:
            if wrong in text:
                text = text.replace(wrong, right)
        if text == base:
            continue
        if "inconsistency" not in loc_pids.get(pid, set()):
            new_locs.append(LocalizationRecord(contract_id, [[pid, pid]], "inconsistency"))
            loc_pids[pid].add("inconsistency")
        types = sorted(loc_pids[pid]) or ["inconsistency"]
        new_revs = [r for r in new_revs if not (r.location and r.location[0][0] == pid)]
        new_revs.append(RevisionRecord(contract_id, [[pid, pid]], types,
                                       paragraphs.get(pid, ""), text))
    return new_locs, new_revs

# -*- coding: utf-8 -*-
"""确定性算术修复：单价×数量≠总价、比例×总价≠金额 → 直接重写数值。"""
from __future__ import annotations

from collections import defaultdict

from .facts import Fact
from .records import LocalizationRecord, RevisionRecord


def _fmt(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return ("%g" % x)


def arithmetic_repairs(paragraphs: dict[int, str], facts: list[Fact]) -> dict[int, str]:
    per: dict[int, list[Fact]] = defaultdict(list)
    for f in facts:
        per[f.pid].append(f)

    repairs: dict[int, str] = {}
    corrected_total = None

    # 1) 单价 × 数量 = 总价
    for pid, fs in per.items():
        unit = [f for f in fs if f.kind == "money" and f.slot == "单价"]
        qty = [f for f in fs if f.kind == "quantity" and f.slot == "数量"]
        total = [f for f in fs if f.kind == "money" and f.slot == "总价"]
        if len(unit) == 1 and len(qty) == 1 and len(total) == 1:
            expected = unit[0].number * qty[0].number
            if abs(expected - total[0].number) > 0.01:
                t = total[0]
                text = paragraphs[pid]
                if t.start >= 0:
                    repairs[pid] = text[:t.start] + _fmt(expected) + text[t.end:]
                corrected_total = expected

    if corrected_total is None:
        totals = {f.number for f in facts if f.kind == "money" and f.slot == "总价"}
        if len(totals) == 1:
            corrected_total = totals.pop()

    # 2) 比例 × 总价 = 金额
    if corrected_total is not None:
        for pid, fs in per.items():
            ratios = [f for f in fs if f.kind == "ratio"]
            moneys = [f for f in fs if f.kind == "money" and f.slot not in ("单价", "总价")]
            if len(ratios) == 1 and len(moneys) == 1:
                expected = ratios[0].number / 100.0 * corrected_total
                m = moneys[0]
                if abs(expected - m.number) > 0.01 and m.start >= 0:
                    text = repairs.get(pid, paragraphs[pid])
                    repairs[pid] = text[:m.start] + _fmt(expected) + text[m.end:]
    return repairs


def apply_arithmetic_repairs(contract_id: str, paragraphs: dict[int, str],
                             facts: list[Fact], locs: list[LocalizationRecord],
                             revs: list[RevisionRecord]):
    """把确定性算术修复并入定位/修订，保持 error_types 自洽。"""
    repairs = arithmetic_repairs(paragraphs, facts)
    if not repairs:
        return locs, revs

    loc_pids: dict[int, set] = defaultdict(set)
    for r in locs:
        if r.error_type:
            for s, e in (r.location or []):
                for pid in range(s, e + 1):
                    loc_pids[pid].add(r.error_type)

    new_locs = [r for r in locs if r.location]
    new_revs = [r for r in revs if r.location]
    for pid, text in repairs.items():
        orig = paragraphs.get(pid, "")
        if not text or text == orig:
            continue
        if "inconsistency" not in loc_pids.get(pid, set()):
            new_locs.append(LocalizationRecord(contract_id, [[pid, pid]], "inconsistency"))
            loc_pids[pid].add("inconsistency")
        types = sorted(loc_pids[pid]) or ["inconsistency"]
        new_revs = [r for r in new_revs
                    if not (r.location and r.location[0][0] == pid)]
        new_revs.append(RevisionRecord(contract_id, [[pid, pid]], types, orig, text))
    if not new_revs:
        new_revs = [RevisionRecord(contract_id, [], [], None, None)]
    return new_locs, new_revs

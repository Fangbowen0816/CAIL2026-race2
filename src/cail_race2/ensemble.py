# -*- coding: utf-8 -*-
"""#8 多轮并集：把多次运行的定位/修订按 (contract, pid, type) 原子合并，抵消非确定性。

策略：定位取**并集**（提召回）；修订按 pid 取**首个非空**答案（避免逐字冲突）。
适用于同一合同多轮取样的场景，需自行权衡 FP。
"""
from __future__ import annotations


def union_localizations(record_lists: list[list[dict]]) -> list[dict]:
    groups: dict[str, dict[str, set]] = {}
    for recs in record_lists:
        for r in recs:
            cid = r.get("contract_id")
            et = r.get("error_type")
            if not et:
                continue
            for s, e in (r.get("location") or []):
                for p in range(s, e + 1):
                    groups.setdefault(cid, {}).setdefault(et, set()).add(p)
    out: list[dict] = []
    for cid, by_type in groups.items():
        for et, pids in by_type.items():
            out.append({"contract_id": cid, "location": [[p, p] for p in sorted(pids)],
                        "error_type": et})
    return out


def union_revisions(record_lists: list[list[dict]]) -> list[dict]:
    out: dict[tuple, dict] = {}
    for recs in record_lists:
        for r in recs:
            loc = r.get("location") or []
            if not (len(loc) == 1 and loc[0][0] == loc[0][1]):
                continue
            key = (r.get("contract_id"), loc[0][0])
            if key not in out:
                out[key] = r
    return list(out.values())

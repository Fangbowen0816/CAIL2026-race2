# -*- coding: utf-8 -*-
"""#17 确定性自检/评审：对「定位 ↔ 修订」结果做不变量核查。

检查项：
- 修订段必须有对应定位（否则平台可能判不合法）；
- 修订段 error_types 必须 == 该段定位类型并集；
- original_text 必须与原文逐字一致；
- 纯干净合同（无定位）不应有修订。
返回 Issue 列表（空=通过）。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Issue:
    kind: str
    pid: int | None
    detail: str


def _loc_types(locs) -> dict[int, set]:
    out: dict[int, set] = defaultdict(set)
    for r in locs:
        if r.error_type:
            for s, e in (r.location or []):
                for pid in range(s, e + 1):
                    out[pid].add(r.error_type)
    return out


def critique(contract_id: str, paragraphs: dict[int, str], locs, revs) -> list[Issue]:
    issues: list[Issue] = []
    loc_types = _loc_types(locs)
    has_loc = bool(loc_types)
    for r in revs:
        loc = r.location or []
        if not loc:
            continue
        pid = loc[0][0] if (len(loc) == 1 and len(loc[0]) == 2) else None
        if pid is None:
            issues.append(Issue("bad_location", None, f"修订 location 非单点区间: {loc}"))
            continue
        if pid not in loc_types:
            issues.append(Issue("unlocalized_revision", pid, "修订段未定位"))
        if set(r.error_types or []) != loc_types.get(pid, set()):
            issues.append(Issue("type_mismatch", pid,
                                f"error_types={r.error_types} != 定位并集 {sorted(loc_types.get(pid, set()))}"))
        if r.original_text is not None and r.original_text != paragraphs.get(pid):
            issues.append(Issue("original_mismatch", pid, "original_text 与原文不一致"))
    if not has_loc and any(r.location for r in revs):
        issues.append(Issue("revision_on_clean_contract", None, "干净合同却产生修订"))
    return issues

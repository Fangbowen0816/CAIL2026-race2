# -*- coding: utf-8 -*-
"""审查结果评分（MCP Server 端）。

两种口径：
1. 有 gold（提交示例）时：按 CAIL 官方口径给 Localization / Revision / Total。
2. 无 gold 时：给「自检分」——结构合法性 + 修订后残余冲突/缺失。
均返回 {score, mode, breakdown, feedback}。
"""
from __future__ import annotations

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import Contract, parse_paragraphs          # noqa: E402
from cail_race2.evaluate import (localization_score, revision_score,  # noqa: E402
                                 total_score)
from cail_race2.records import (LocalizationRecord, RevisionRecord,   # noqa: E402
                                validate_localization, validate_revision)
from cail_race2.revise import apply_revisions                          # noqa: E402
from cail_race2.verify import verify                                   # noqa: E402


def _records(contract_id, localization, revision):
    locs = [LocalizationRecord(contract_id, d.get("location"), d.get("error_type"))
            for d in localization]
    revs = [RevisionRecord(contract_id, d.get("location"), d.get("error_types") or [],
                           d.get("original_text"), d.get("correct_answer")) for d in revision]
    return locs, revs


def score_review(contract_id: str, context: str, localization: list, revision: list,
                 gold: dict | None = None) -> dict:
    paragraphs = parse_paragraphs(context)
    contract = Contract(contract_id, context, paragraphs)
    locs, revs = _records(contract_id, localization, revision)

    schema_errors: list[str] = []
    for r in locs:
        schema_errors += [f"loc: {e}" for e in validate_localization(r, paragraphs)]
    for r in revs:
        schema_errors += [f"rev: {e}" for e in validate_revision(r, paragraphs)]
    schema_ok = not schema_errors

    final = apply_revisions(paragraphs, revs)
    residual = [c for c in verify(final) if c.kind in ("conflict", "arithmetic", "missing")]
    issue_count = max(1, len([r for r in locs if r.location]))

    if gold:
        loc = localization_score(gold.get("localization", []), localization)
        rev = revision_score({contract_id: contract}, gold.get("revision", []), revision)
        total = total_score(loc["L"], rev["R"])
        return {
            "score": round(total, 4),
            "mode": "cail_gold",
            "breakdown": {"Localization": round(loc["L"], 4),
                          "Revision": round(rev["R"], 4),
                          "Loc_typo": round(loc["typo"]["f1"] * 100, 4),
                          "Loc_inconsistency": round(loc["inconsistency"]["f1"] * 100, 4),
                          "Loc_missing": round(loc["missing_element"]["f1"] * 100, 4),
                          "Rev_typo": round(rev["T"], 4),
                          "Rev_inconsistency": round(rev["C"], 4),
                          "Rev_missing": round(rev["M"], 4)},
            "feedback": "按 CAIL 口径（1:3:6 定位 + 10:30:60 修订）评分。"
                        + (" 结构校验通过。" if schema_ok else f" 结构问题：{schema_errors[:5]}"),
        }

    # 无 gold：自检分
    consistency = max(0.0, 1 - len(residual) / issue_count)
    score = 100 * (0.5 * (1.0 if schema_ok else 0.0) + 0.5 * consistency)
    return {
        "score": round(score, 4),
        "mode": "self_check",
        "breakdown": {"schema_ok": schema_ok, "issues": issue_count,
                      "residual_problems": len(residual), "consistency": round(consistency, 4)},
        "feedback": ("结构合法，修订后无明显残余冲突。" if schema_ok and not residual
                     else f"结构问题 {len(schema_errors)} 项；修订后残余问题 {len(residual)} 处。"),
    }

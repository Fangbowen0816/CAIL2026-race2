# -*- coding: utf-8 -*-
"""审查结果评分（MCP Server 端）。

两种口径：
1. 有 gold（提交示例）时：按**官方口径**返回与平台排行榜同名的字段
   （Total / Localization / Revision / Loc_* / Rev_* / Typo_TP/FP/FN）。
   公式与反推校准见 `cail_race2.evaluate` 模块 docstring。
2. 无 gold 时：给「自检分」——结构合法性 + 修订后残余冲突/缺失。
均返回 {score, mode, breakdown, feedback}。
"""
from __future__ import annotations

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import Contract, parse_paragraphs          # noqa: E402
from cail_race2.evaluate import official_report                       # noqa: E402
from cail_race2.records import (LocalizationRecord, RevisionRecord,   # noqa: E402
                                validate_localization, validate_revision)
from cail_race2.revise import apply_revisions                          # noqa: E402
from cail_race2.verify import verify                                   # noqa: E402

PLATFORM_FIELDS = ("Total", "Localization", "Revision",
                   "Loc_typo", "Loc_inconsistency", "Loc_missing", "Loc_stance",
                   "Rev_typo", "Rev_inconsistency", "Rev_missing", "Rev_stance",
                   "Typo_TP", "Typo_FP", "Typo_FN")


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

    if gold:
        rep = official_report({contract_id: contract}, gold,
                              {"localization": localization, "revision": revision})
        breakdown = {k: round(rep[k], 4) for k in PLATFORM_FIELDS}
        return {
            "score": breakdown["Total"],
            "mode": "cail_gold",
            "breakdown": breakdown,
            "feedback": "官方口径评分（定位 1:3:6，修订 10:30:60）；字段与平台排行榜一致。"
                        + (" 结构校验通过。" if schema_ok else f" 结构问题：{schema_errors[:5]}"),
        }

    # 无 gold：自检分
    final = apply_revisions(paragraphs, revs)
    residual = [c for c in verify(final) if c.kind in ("conflict", "arithmetic", "missing")]
    issue_count = max(1, len([r for r in locs if r.location]))
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

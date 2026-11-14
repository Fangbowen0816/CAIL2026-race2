# -*- coding: utf-8 -*-
"""#8 多轮并集工具：TDD 测点。"""
from cail_race2.ensemble import union_localizations, union_revisions


def _atoms(recs):
    return {(r["error_type"], p) for r in recs for s, e in r["location"] for p in range(s, e + 1)}


def test_union_localizations_merges_atoms():
    a = [{"contract_id": "C1", "location": [[1, 1]], "error_type": "typo"}]
    b = [{"contract_id": "C1", "location": [[2, 2]], "error_type": "typo"}]
    assert _atoms(union_localizations([a, b])) == {("typo", 1), ("typo", 2)}


def test_union_localizations_dedups_same_atom():
    a = [{"contract_id": "C1", "location": [[1, 1]], "error_type": "typo"}]
    assert len(union_localizations([a, a])) == 1


def test_union_revisions_keeps_first_by_pid():
    a = [{"contract_id": "C1", "location": [[1, 1]], "error_types": ["typo"],
          "original_text": "x", "correct_answer": "y"}]
    b = [{"contract_id": "C1", "location": [[1, 1]], "error_types": ["typo"],
          "original_text": "x", "correct_answer": "z"}]
    out = union_revisions([a, b])
    assert len(out) == 1 and out[0]["correct_answer"] == "y"

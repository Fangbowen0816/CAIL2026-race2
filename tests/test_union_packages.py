# -*- coding: utf-8 -*-
"""#15 多包并集：集成后必须自洽（error_types == 定位并集）。"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from union_packages import union_packages  # noqa: E402


def _write(pkg, loc, rev):
    os.makedirs(pkg, exist_ok=True)
    with open(os.path.join(pkg, "localization_predictions.jsonl"), "w", encoding="utf-8") as f:
        for r in loc:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(pkg, "revision_predictions.jsonl"), "w", encoding="utf-8") as f:
        for r in rev:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_union_merges_and_reconciles(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    _write(a, [{"contract_id": "C1", "location": [[1, 1]], "error_type": "typo"}],
           [{"contract_id": "C1", "location": [[1, 1]], "error_types": ["typo"],
             "original_text": "x", "correct_answer": "y"}])
    # b 多了 p2 的修订但没有定位 → reconcile 应补出定位
    _write(b, [{"contract_id": "C1", "location": [], "error_type": None}],
           [{"contract_id": "C1", "location": [[2, 2]], "error_types": ["inconsistency"],
             "original_text": "a", "correct_answer": "b"}])
    loc, rev = union_packages([a, b])
    atoms = {(d["error_type"], p) for d in loc for s, e in (d["location"] or []) for p in range(s, e + 1)}
    assert ("typo", 1) in atoms and ("inconsistency", 2) in atoms
    # 每个修订段的 error_types 必须等于定位并集
    locmap = {}
    for d in loc:
        for s, e in (d["location"] or []):
            for p in range(s, e + 1):
                locmap.setdefault(p, set()).add(d["error_type"])
    for r in rev:
        if r["location"]:
            p = r["location"][0][0]
            assert set(r["error_types"]) == locmap.get(p, set())

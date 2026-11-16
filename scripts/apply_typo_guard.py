# -*- coding: utf-8 -*-
"""离线应用 typo 后置校验到已生成的提交包（不调用 LLM）。

用法：
  python scripts/apply_typo_guard.py --in outputs/semi_kdeep --out outputs/semi_kdeep_g
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.records import RevisionRecord  # noqa: E402
from cail_race2.submission import make_zip, write_jsonl  # noqa: E402
from cail_race2.typo_guard import guard_records  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    a = ap.parse_args()
    loc = _read(os.path.join(a.src, "localization_predictions.jsonl"))
    rev = _read(os.path.join(a.src, "revision_predictions.jsonl"))
    by_contract = {}
    for d in rev:
        rec = RevisionRecord(d["contract_id"], d.get("location"), d.get("error_types") or [],
                             d.get("original_text"), d.get("correct_answer"))
        by_contract.setdefault(d["contract_id"], []).append(rec)
    rows = []
    for cid, recs in by_contract.items():
        for r in guard_records(cid, {}, recs):
            rows.append({"contract_id": r.contract_id, "location": r.location,
                         "error_types": r.error_types, "original_text": r.original_text,
                         "correct_answer": r.correct_answer})
    loc_out = loc
    # 统计变化
    orig = {(d["contract_id"], tuple(tuple(x) for x in (d.get("location") or []))):
            (d.get("correct_answer") or "") for d in rev}
    changed = 0
    for d in rows:
        k = (d["contract_id"], tuple(tuple(x) for x in (d.get("location") or [])))
        if orig.get(k, "") != (d["correct_answer"] or ""):
            changed += 1
    os.makedirs(a.dst, exist_ok=True)
    write_jsonl(os.path.join(a.dst, "localization_predictions.jsonl"), loc_out)
    write_jsonl(os.path.join(a.dst, "revision_predictions.jsonl"), rows)
    zip_path = make_zip(os.path.join(a.dst, "cail2026_race2_submission.zip"),
                        [os.path.join(a.dst, "localization_predictions.jsonl"),
                         os.path.join(a.dst, "revision_predictions.jsonl")])
    print("修订 %d 条，其中被校验改动 %d 条" % (len(rows), changed))
    print("提交包:", zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

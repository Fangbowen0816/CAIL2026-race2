# -*- coding: utf-8 -*-
"""离线应用 typo 后置校验到已生成的提交包（不调用 LLM）。

用法：
  python scripts/apply_typo_guard.py --in outputs/semi_kdeep --out outputs/semi_kdeep_g
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.records import LocalizationRecord, RevisionRecord  # noqa: E402
from cail_race2.submission import make_zip, write_jsonl  # noqa: E402
from cail_race2.typo_dict import apply_typo_dict  # noqa: E402
from cail_race2.typo_guard import guard_records  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--dict", action="store_true", help="同时应用错别字词典补漏")
    ap.add_argument("--contracts", default=None, help="--dict 时需要：原始合同 jsonl")
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
    if a.dict:
        if not a.contracts:
            raise SystemExit("--dict 需同时给 --contracts（用原文扫描词典）")
        from cail_race2.contracts import load_contracts
        paras = {c.contract_id: c.paragraphs for c in load_contracts(a.contracts)}
        by_c = collections.defaultdict(list)
        for d in loc:
            by_c[d["contract_id"]].append(LocalizationRecord(
                d["contract_id"], d.get("location"), d.get("error_type")))
        l2, r2 = [], []
        for cid, recs in by_contract.items():
            ls = by_c.get(cid, [])
            rlist = [RevisionRecord(cid, r["location"], r["error_types"],
                                    r["original_text"], r["correct_answer"]) for r in rows
                     if r["contract_id"] == cid]
            ls, rlist = apply_typo_dict(cid, paras.get(cid, {}), ls, rlist)
            l2 += ls
            r2 += rlist
        loc_out = [{"contract_id": x.contract_id, "location": x.location,
                    "error_type": x.error_type} for x in l2]
        rows = [{"contract_id": x.contract_id, "location": x.location,
                 "error_types": x.error_types, "original_text": x.original_text,
                 "correct_answer": x.correct_answer} for x in r2]
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

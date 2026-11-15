# -*- coding: utf-8 -*-
"""把多个提交包并集成一份（定位取并集；修订按段落取首个非空），并做自洽 reconcile。

用法：
  python scripts/union_packages.py --packages outputs/run_a outputs/run_b --out outputs/union
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.ensemble import union_localizations, union_revisions  # noqa: E402
from cail_race2.records import LocalizationRecord, RevisionRecord      # noqa: E402
from cail_race2.revise import reconcile                               # noqa: E402
from cail_race2.submission import make_zip, write_jsonl               # noqa: E402


def _load(pkg):
    loc = [json.loads(l) for l in open(os.path.join(pkg, "localization_predictions.jsonl"),
                                       encoding="utf-8") if l.strip()]
    rev = [json.loads(l) for l in open(os.path.join(pkg, "revision_predictions.jsonl"),
                                       encoding="utf-8") if l.strip()]
    return loc, rev


def union_packages(packages: list[str]):
    loc_lists, rev_lists = [], []
    for pkg in packages:
        l, r = _load(pkg)
        loc_lists.append(l)
        rev_lists.append(r)
    loc_u, rev_u = union_localizations(loc_lists), union_revisions(rev_lists)

    by_cid_loc: dict[str, list] = defaultdict(list)
    for d in loc_u:
        by_cid_loc[d["contract_id"]].append(LocalizationRecord(d["contract_id"], d["location"], d["error_type"]))
    by_cid_rev: dict[str, list] = defaultdict(list)
    for d in rev_u:
        by_cid_rev[d["contract_id"]].append(
            RevisionRecord(d["contract_id"], d["location"], d.get("error_types") or [],
                           d.get("original_text"), d.get("correct_answer")))

    out_loc, out_rev = [], []
    for cid in sorted(set(by_cid_loc) | set(by_cid_rev)):
        locs, revs = reconcile(cid, by_cid_loc.get(cid, []), by_cid_rev.get(cid, []))
        out_loc += [r.to_dict() for r in locs]
        out_rev += [r.to_dict() for r in revs]
    return out_loc, out_rev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packages", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    loc, rev = union_packages(a.packages)
    os.makedirs(a.out, exist_ok=True)
    write_jsonl(os.path.join(a.out, "localization_predictions.jsonl"), loc)
    write_jsonl(os.path.join(a.out, "revision_predictions.jsonl"), rev)
    zip_path = make_zip(os.path.join(a.out, "cail2026_race2_submission.zip"),
                        [os.path.join(a.out, "localization_predictions.jsonl"),
                         os.path.join(a.out, "revision_predictions.jsonl")])
    print(f"并集：定位 {len(loc)} | 修订 {len(rev)} | 包 {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""召回检测机制：把我们的定位结果与「模型穷举标注集」比对，量出逐类型召回/精确。

标注集由 scripts/annotate_errors.py 生成（missing/stance/inconsistency），仅用于评估。

用法：
  python scripts/recall_check.py --kind missing --annot resources/recall/annot_missing \
      --localization outputs/semi_kdeep/localization_predictions.jsonl
  python scripts/recall_check.py --all --contracts <f> --localization <f>
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import load_contracts  # noqa: E402

KINDS = {"missing": "missing_element", "stance": "stance", "inconsistency": "inconsistency"}
ANN_DIR = {"missing": "annot_missing", "stance": "annot_stance",
           "inconsistency": "annot_inconsistency"}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def ours_segments(localization, etype):
    out = collections.defaultdict(set)
    for d in _read(localization):
        if d["error_type"] != etype:
            continue
        for a, b in (d["location"] or []):
            for p in range(a, b + 1):
                out[d["contract_id"]].add(p)
    return out


def ann_segments(annot_dir):
    out = collections.defaultdict(set)
    reasons = collections.defaultdict(dict)
    if not os.path.isdir(annot_dir):
        return out, reasons
    for f in sorted(os.listdir(annot_dir)):
        cid = f[:-5]
        for it in json.load(open(os.path.join(annot_dir, f), encoding="utf-8")):
            for p in it["pids"]:
                out[cid].add(p)
                reasons[cid][p] = it.get("reason", "")
    return out, reasons


def measure(kind, annot_root, localization):
    ann, reasons = ann_segments(os.path.join(annot_root, ANN_DIR[kind]))
    ours = ours_segments(localization, KINDS[kind])
    tot = sum(len(v) for v in ann.values())
    hit = sum(len(ann[c] & ours.get(c, set())) for c in ann)
    otot = sum(len(v) for v in ours.values())
    ohit = sum(len(ours[c] & ann.get(c, set())) for c in ours)
    r = hit / tot if tot else 0.0
    p = ohit / otot if otot else 0.0
    miss = [(c, p2, reasons[c].get(p2, "")) for c in sorted(ann)
            for p2 in sorted(ann[c] - ours.get(c, set()))]
    return {"kind": kind, "标注": tot, "我们": otot, "命中": hit, "召回": round(r, 4),
            "精确": round(p, 4), "F1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
            "漏检": miss}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=list(KINDS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--annot-root", default=os.path.join(ROOT, "resources", "recall"))
    ap.add_argument("--localization", required=True)
    ap.add_argument("--show-miss", type=int, default=0)
    a = ap.parse_args()
    kinds = list(KINDS) if a.all else [a.kind]
    for k in kinds:
        m = measure(k, a.annot_root, a.localization)
        print("%-14s 标注 %4d | 我们 %4d | 命中 %3d | 召回 %.1f%% | 精确 %.1f%% | F1 %.3f"
              % (k, m["标注"], m["我们"], m["命中"], 100 * m["召回"], 100 * m["精确"], m["F1"]))
        for c, p, why in m["漏检"][:a.show_miss]:
            print("    漏 %s p%s: %s" % (c, p, why[:70]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

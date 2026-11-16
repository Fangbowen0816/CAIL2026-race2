# -*- coding: utf-8 -*-
"""把模型标注的「错别字集」精炼为检测用词典（区分真错别字与跨段一致性）。

用法：
  python scripts/build_typo_lexicon.py --annot resources/typo/typo_set.jsonl \
      --out resources/typo/lexicon.jsonl --report
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.typo_dict import build_lexicon, classify_pair  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annot", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.annot, encoding="utf-8") if l.strip()]
    kinds = collections.Counter(classify_pair(d["wrong"], d["right"]) for d in rows)
    lex = build_lexicon(rows)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for (w, r), e in sorted(lex.items(), key=lambda kv: -kv[1]["count"]):
            f.write(json.dumps({"wrong": w, "right": r, "count": e["count"],
                                "contracts": sorted(e["contracts"])}, ensure_ascii=False) + "\n")
    if a.report:
        print("标注 %d → 词典 %d 条（去重、剔双向歧义后）" % (len(rows), len(lex)))
        print("分类:", dict(kinds.most_common()))
        print("\n高频词条 TOP20:")
        for (w, r), e in sorted(lex.items(), key=lambda kv: -kv[1]["count"])[:20]:
            print("  %-16s → %-14s x%d" % (w, r, e["count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

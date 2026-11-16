# -*- coding: utf-8 -*-
"""用「合同错别字集」验证错别字模块效果（该集仅作标注真值，agent 不查询）。

用法：
  python scripts/typo_validate.py \
      --annot resources/typo/contract/typo_set.jsonl \
      --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
      --localization outputs/semi_kdeep/localization_predictions.jsonl \
      --revision outputs/semi_kdeep/revision_predictions.jsonl

指标：
  段级召回 = 标注所在段被标为 typo 的比例（定位能力）
  纠正召回 = 标注的错字在最终文本中已被改正的比例（修订能力）
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


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annot", required=True)
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--localization", default=None)
    ap.add_argument("--revision", default=None)
    a = ap.parse_args()
    anns = _read(a.annot)
    cs = {c.contract_id: c for c in load_contracts(a.contracts)}
    orig = {cid: c.paragraphs for cid, c in cs.items()}
    loc = collections.defaultdict(set)
    if a.localization:
        for x in _read(a.localization):
            if x["error_type"] == "typo":
                for s, e in (x["location"] or []):
                    loc[x["contract_id"]].update(range(s, e + 1))
    final = collections.defaultdict(lambda: collections.defaultdict(str))
    if a.revision:
        for x in _read(a.revision):
            if not x.get("location"):
                continue
            pid = x["location"][0][0]
            final[x["contract_id"]][pid] = x.get("correct_answer") or ""
    tot = loc_ok = fixed_ok = 0
    for x in anns:
        cid = x["contract_id"]
        src = orig[cid].get(x["pid"], "") or ""
        if x["wrong"] not in src:
            continue                                   # 无法定位到原文，跳过
        tot += 1
        loc_ok += x["pid"] in loc[cid]
        f = final[cid].get(x["pid"]) or src
        fixed_ok += (x["wrong"] not in f) and (x["right"] in f)
    if not tot:
        print("无可评估的标注")
        return 0
    print("合同错别字集：%d 处可定位" % tot)
    if a.localization:
        print("  段级召回（定位为 typo）：%.1f%%" % (100 * loc_ok / tot))
    if a.revision:
        print("  纠正召回（最终文本已改正）：%.1f%%" % (100 * fixed_ok / tot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

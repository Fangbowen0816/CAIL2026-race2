# -*- coding: utf-8 -*-
"""验证错别字纠错算法：用**合同错别字集**（agent 不查询，仅作标注真值）评估效果。

用法：
  python scripts/typo_validate.py \
      --annot resources/typo/contract/typo_set.jsonl \
      --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
      [--localization outputs/semi_kdeep/localization_predictions.jsonl]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import load_contracts      # noqa: E402
from cail_race2.typo_dict import TypoDict            # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def spans(text, w, used):
    i, out = 0, []
    while True:
        j = text.find(w, i)
        if j < 0:
            break
        if not any(j < e and j + len(w) > s for s, e in used):
            out.append((j, j + len(w)))
            used.add((j, j + len(w)))
            break
        i = j + 1
    return out


def evaluate(pred, gt, paras):
    tp = fp = fn = 0
    for cid, anns in gt.items():
        p = paras[cid]
        used = set()
        gspans = collections.defaultdict(list)
        for a in anns:
            gspans[a["pid"]] += spans(p.get(a["pid"], "") or "", a["wrong"], set())
        for h in pred.get(cid, []):
            hit = any(h["start"] < e and h["end"] > s for s, e in gspans[h["pid"]])
            tp += hit
            fp += not hit
        fn += sum(len(v) for v in gspans.values()) - sum(
            1 for h in pred.get(cid, []) for s, e in gspans[h["pid"]]
            if h["start"] < e and h["end"] > s)
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "P": round(P, 4), "R": round(R, 4),
            "F1": round(2 * P * R / (P + R), 4) if P + R else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annot", required=True)
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--lexicon", default=None, help="通用词典（默认 resources/typo/general.jsonl）")
    ap.add_argument("--localization", default=None)
    a = ap.parse_args()
    anns = _read(a.annot)
    cs = {c.contract_id: c for c in load_contracts(a.contracts)}
    paras = {cid: c.paragraphs for cid, c in cs.items()}
    d = TypoDict.load(a.lexicon) if a.lexicon else TypoDict.load()
    gt = collections.defaultdict(list)
    for x in anns:
        gt[x["contract_id"]].append(x)
    pred = {}
    for cid in paras:
        hits = []
        for pid in sorted(paras[cid]):
            for h in d.find(paras[cid][pid] or ""):
                hits.append({**h, "pid": pid})
        pred[cid] = hits
    print("通用词典 %d 条" % len(d.entries))
    print("【算法单独】", evaluate(pred, gt, paras))
    if a.localization:
        loc = collections.defaultdict(set)
        for x in _read(a.localization):
            if x["error_type"] == "typo":
                for s, e in (x["location"] or []):
                    for p in range(s, e + 1):
                        loc[x["contract_id"]].add(p)
        tot = llm = dic = both = 0
        for cid, anns2 in gt.items():
            hits = pred.get(cid, [])
            for x in anns2:
                tot += 1
                in_llm = x["pid"] in loc[cid]
                in_dic = any(h["pid"] == x["pid"] for h in hits)
                llm += in_llm
                dic += in_dic
                both += in_llm or in_dic
        print("【召回（对错别字集 %d 处）】LLM %.0f%% | 词典 %.0f%% | 合并 %.0f%%"
              % (tot, 100 * llm / tot, 100 * dic / tot, 100 * both / tot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

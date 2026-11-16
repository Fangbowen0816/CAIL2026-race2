# -*- coding: utf-8 -*-
"""检查「词典错别字检测器」的效果：覆盖率 / 补漏 / 留出泛化 / 安全性。

用法：
  python scripts/typo_dict_check.py \
      --annot resources/typo/typo_set.jsonl \
      --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
      --holdout 5
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import load_contracts               # noqa: E402
from cail_race2.typo_dict import TypoDict, build_lexicon      # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _spans(text, anns):
    """把标注定位到字符区间（同一 pid 内按出现顺序）。"""
    out, used = [], set()
    for a in anns:
        w = a["wrong"]
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            if not any(i < e and i + len(w) > s for s, e in used):
                out.append((i, i + len(w)))
                used.add((i, i + len(w)))
                break
            start = i + 1
    return out


def evaluate(pred_by_contract, gt_by_contract, paragraphs_by_contract):
    tp = fp = fn = 0
    for cid, gts in gt_by_contract.items():
        paras = paragraphs_by_contract[cid]
        gt_spans = collections.defaultdict(list)
        for a in gts:
            gt_spans[a["pid"]] += _spans(paras.get(a["pid"], "") or "", [a])
        pred_spans = [h for h in pred_by_contract.get(cid, [])]
        used_gt = set()
        for h in pred_spans:
            ps, pe = h["start"], h["end"]
            hit = False
            for (s, e) in gt_spans[h["pid"]]:
                if (h["pid"], s, e) in used_gt:
                    continue
                if ps < e and pe > s:
                    used_gt.add((h["pid"], s, e))
                    hit = True
                    break
            tp += 1 if hit else 0
            fp += 0 if hit else 1
        fn += sum(len(v) for v in gt_spans.values()) - len(used_gt)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "P": round(p, 4), "R": round(r, 4), "F1": round(f1, 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annot", required=True)
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--holdout", type=int, default=5)
    ap.add_argument("--localization", default=None, help="LLM 定位结果（算补漏）")
    a = ap.parse_args()
    annots = _read(a.annot)
    contracts = {c.contract_id: c for c in load_contracts(a.contracts)}
    paras = {cid: c.paragraphs for cid, c in contracts.items()}

    # 1) 全量覆盖率 + 补漏
    full = TypoDict.load()
    all_pred = {cid: _spans_paras(full, paras[cid]) for cid in paras}
    total_hits = sum(len(v) for v in all_pred.values())
    print("【全量】词典 %d 条；在 45 合同共命中 %d 处" % (len(full.entries), total_hits))
    if a.localization:
        loc = collections.defaultdict(set)
        for d in _read(a.localization):
            if d["error_type"] == "typo":
                for s, e in (d["location"] or []):
                    for p in range(s, e + 1):
                        loc[d["contract_id"]].add(p)
        extra = sum(1 for cid, hs in all_pred.items() for h in hs if h["pid"] not in loc[cid])
        print("       其中 LLM 未标 typo 的段：%d 处 → 词典可补漏" % extra)

    # 2) 留出泛化：训练集建词典，测试集评估
    ids = sorted(paras)
    test_ids = ids[-a.holdout:] if a.holdout else []
    train_ids = [c for c in ids if c not in test_ids]
    lex = build_lexicon([d for d in annots if d["contract_id"] in set(train_ids)])
    d = TypoDict([(w, r) for (w, r) in lex])
    gt = collections.defaultdict(list)
    for x in annots:
        if x["contract_id"] in set(test_ids):
            gt[x["contract_id"]].append(x)
    pred = {cid: _spans_paras(d, paras[cid]) for cid in test_ids}
    print("\n【留出】训练 %d 合同（词典 %d 条）→ 测试 %s"
          % (len(train_ids), len(d.entries), ",".join(test_ids)))
    print("  ", evaluate(pred, gt, paras))

    # 3) 安全性：词典对干净文本的改动量
    changed = sum(1 for hs in all_pred.values() for h in hs if h["wrong"] == h["right"])
    print("\n【安全】词典命中中 wrong==right 的条目：%d（应为 0）" % changed)

    # 4) 对「错别字集」的召回：LLM / 词典 / 合并（实例级）
    if a.localization:
        loc = collections.defaultdict(set)
        for d0 in _read(a.localization):
            if d0["error_type"] == "typo":
                for s, e in (d0["location"] or []):
                    for p in range(s, e + 1):
                        loc[d0["contract_id"]].add(p)
        for scope, ids_ in (("全量 45", ids), ("留出 %d" % a.holdout, test_ids)):
            tot = llm_ok = dict_ok = both = 0
            dd = full if scope.startswith("全量") else d
            for x in annots:
                cid = x["contract_id"]
                if cid not in set(ids_):
                    continue
                tot += 1
                in_llm = x["pid"] in loc[cid]
                in_dict = any(h["pid"] == x["pid"] for h in _spans_paras(dd, {x["pid"]: paras[cid].get(x["pid"], "")}))
                llm_ok += in_llm
                dict_ok += in_dict
                both += (in_llm or in_dict)
            print("\n【召回 %s】标注 %d 处：LLM %.0f%% | 词典 %.0f%% | 合并 %.0f%%"
                  % (scope, tot, 100 * llm_ok / tot, 100 * dict_ok / tot, 100 * both / tot))
    return 0


def _spans_paras(d, paragraphs):
    out = []
    for pid in sorted(paragraphs):
        for h in d.find(paragraphs[pid] or ""):
            out.append({**h, "pid": pid})
    return out


if __name__ == "__main__":
    raise SystemExit(main())

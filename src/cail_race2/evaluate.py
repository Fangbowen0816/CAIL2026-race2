# -*- coding: utf-8 -*-
"""本地评测（对齐赛道公式，但为近似实现；官方评分脚本不公开）。

定位分（可精确复现口径）：
  匹配单位 = (contract_id, 段落号, error_type)；跨段按命中 id 逐个计。
  L = 10·F_typo + 30·F_inconsistency + 60·F_missing   （百分制）

修改分（近似）：
  按预测回填各段最终文本：
  T（错别字）     = gold 标注段内，预测文本与标准答案的**字级 F0.5**均值
  C（不一致）     = 预测最终文本与标准答案**完全一致**的比例
  M（要素缺失）   = 预测与标准答案的 **1 - 编辑距离/最大长度** 均值
  R = 10·T + 30·C + 60·M

总分 S = 0.5·L + 0.5·R
"""
from __future__ import annotations

from collections import Counter

from .records import ERROR_TYPES


def _atoms(records) -> set:
    atoms = set()
    for r in records:
        et = r.get("error_type")
        for iv in (r.get("location") or []):
            for pid in range(iv[0], iv[1] + 1):
                atoms.add((r["contract_id"], pid, et))
    return atoms


def _prf(gold: set, pred: set):
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def localization_score(gold_records, pred_records) -> dict:
    out, f1s = {}, {}
    for t in ERROR_TYPES:
        g = {a for a in _atoms(gold_records) if a[2] == t}
        p = {a for a in _atoms(pred_records) if a[2] == t}
        pr, rc, f1 = _prf(g, p)
        out[t] = {"precision": pr, "recall": rc, "f1": f1,
                  "n_gold": len(g), "n_pred": len(p)}
        f1s[t] = f1
    out["L"] = 10 * f1s["typo"] + 30 * f1s["inconsistency"] + 60 * f1s["missing_element"]
    return out


def char_f_beta(pred: str, gold: str, beta: float = 0.5) -> float:
    """字级 F-beta（字符袋近似）。"""
    if not pred and not gold:
        return 1.0
    cp, cg = Counter(pred or ""), Counter(gold or "")
    overlap = sum((cp & cg).values())
    p = overlap / len(pred) if pred else 0.0
    r = overlap / len(gold) if gold else 0.0
    b2 = beta * beta
    return (1 + b2) * p * r / (b2 * p + r) if (p + r) else 0.0


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def edit_similarity(pred: str, gold: str) -> float:
    m = max(len(pred or ""), len(gold or ""))
    return 1.0 if m == 0 else 1 - levenshtein(pred or "", gold or "") / m


def _mean(xs) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def revision_score(contracts: dict, gold_records, pred_records) -> dict:
    """contracts: {contract_id: Contract}，用于回填未修改段落。"""

    def final_map(records):
        m: dict[str, dict[int, str]] = {}
        for r in records:
            loc = r.get("location") or []
            if len(loc) == 1 and loc[0][0] == loc[0][1] and r.get("correct_answer"):
                m.setdefault(r["contract_id"], {})[loc[0][0]] = r["correct_answer"]
        return m

    pfinal = final_map(pred_records)
    buckets = {t: [] for t in ERROR_TYPES}
    for r in gold_records:
        loc = r.get("location") or []
        if not (len(loc) == 1 and loc[0][0] == loc[0][1]):
            continue
        cid, pid = r["contract_id"], loc[0][0]
        orig = contracts[cid].paragraphs.get(pid, "") if cid in contracts else ""
        goldtext = r.get("correct_answer") or ""
        predtext = pfinal.get(cid, {}).get(pid, orig)
        for t in (r.get("error_types") or []):
            if t == "typo":
                buckets[t].append(char_f_beta(predtext, goldtext))
            elif t == "inconsistency":
                buckets[t].append(1.0 if predtext == goldtext else 0.0)
            elif t == "missing_element":
                buckets[t].append(edit_similarity(predtext, goldtext))
    T, C, M = (100 * _mean(buckets[t]) for t in
               ("typo", "inconsistency", "missing_element"))
    return {"T": T, "C": C, "M": M, "R": 0.10 * T + 0.30 * C + 0.60 * M,
            "n": {t: len(buckets[t]) for t in ERROR_TYPES}}


def total_score(L: float, R: float) -> float:
    return 0.5 * L + 0.5 * R

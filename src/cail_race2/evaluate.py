# -*- coding: utf-8 -*-
"""官方口径评分（依据赛道说明 + 两次平台实测反推校准）。

平台返回的评分字段与公式（已用两次提交实测值反推校验）：

  定位（段落级，匹配单位 = (contract_id, 段落号, error_type)）：
      Loc_typo / Loc_inconsistency / Loc_missing 分别为三类 F1（百分制）
      Localization = 0.1·Loc_typo + 0.3·Loc_inconsistency + 0.6·Loc_missing
  修订：
      Rev_typo         = 字级 F0.5（ChERRANT：相对原文抽取编辑，隔离不一致编辑；用 TP/FP/FN 计）
      Rev_inconsistency= 已修复的不一致问题数 / 全部不一致问题数（接受多参考）
      Rev_missing      = 相对“原文→标准答案”的编辑距离完成度（pred==gold 记 1，pred==orig 记 0）
      Revision = 0.1·Rev_typo + 0.3·Rev_inconsistency + 0.6·Rev_missing
  总分：Total = 0.5·Localization + 0.5·Revision

反推校准（两次平台实测，逐位吻合）：
  提交A: Loc 47.531 / Rev 8.4198 / Total 27.9754
  提交B: Loc 45.0615 / Rev 5.6434 / Total 25.3524
  Typo(字级) TP135/FP160/FN11 → F0.5=50.91；TP100/FP139/FN46 → F0.5=45.3721
"""
from __future__ import annotations

import difflib
from collections import Counter

from .records import ERROR_TYPES

LOC_WEIGHT = {"typo": 10.0, "inconsistency": 30.0, "missing_element": 60.0}
REV_WEIGHT = {"typo": 10.0, "inconsistency": 30.0, "missing_element": 60.0}


# --------------------------------------------------------------------------- 定位
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
    out["L"] = sum(LOC_WEIGHT[t] * f1s[t] for t in ERROR_TYPES)
    return out


# --------------------------------------------------------------------------- 修订工具
def f_beta(p: float, r: float, beta: float = 0.5) -> float:
    b2 = beta * beta
    return (1 + b2) * p * r / (b2 * p + r) if (p + r) else 0.0


def char_f_beta(pred: str, gold: str, beta: float = 0.5) -> float:
    """字级 F-beta（字符袋近似，保留兼容）。"""
    if not pred and not gold:
        return 1.0
    cp, cg = Counter(pred or ""), Counter(gold or "")
    overlap = sum((cp & cg).values())
    p = overlap / len(pred) if pred else 0.0
    r = overlap / len(gold) if gold else 0.0
    return f_beta(p, r, beta)


def _edit_counter(orig: str, new: str) -> Counter:
    """把 orig→new 的字符编辑表示为「(源串, 目标串) → 字符数」的多重集。"""
    c: Counter = Counter()
    sm = difflib.SequenceMatcher(a=orig or "", b=new or "", autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        c[(orig[i1:i2], new[j1:j2])] += max(i2 - i1, j2 - j1)
    return c


def char_edit_f_beta(orig: str, gold: str, pred: str, beta: float = 0.5) -> dict:
    """ChERRANT 口径字级 F0.5：相对原文抽编辑，与标准答案的编辑求 TP/FP/FN。"""
    g = _edit_counter(orig or "", gold or "")
    p = _edit_counter(orig or "", pred or "")
    tp = sum((g & p).values())
    fp = sum(p.values()) - tp
    fn = sum(g.values()) - tp
    pp = tp / (tp + fp) if (tp + fp) else 0.0
    rr = tp / (tp + fn) if (tp + fn) else 0.0
    return {"f": f_beta(pp, rr, beta), "tp": tp, "fp": fp, "fn": fn}


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


def _progress(orig: str, pred: str, gold: str) -> float:
    """要素缺失完成度：pred==gold→1，pred==orig→0，中间为沿编辑距离的线性插值。"""
    if pred == gold:
        return 1.0
    denom = levenshtein(orig or "", gold or "")
    if denom == 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - levenshtein(pred or "", gold or "") / denom))


def _accepted(record) -> list:
    """标准答案可有多参考：correct_answers / references，回退 correct_answer。"""
    vals = record.get("correct_answers") or record.get("references")
    if isinstance(vals, list) and vals:
        return [v for v in vals if v is not None]
    return [record.get("correct_answer")]


def _mean(xs) -> float:
    return sum(xs) / len(xs) if xs else 0.0


# --------------------------------------------------------------------------- 修订
def revision_score(contracts: dict, gold_records, pred_records) -> dict:
    """contracts: {contract_id: Contract}，用于回填未修改段落。"""
    def final_map(records):
        m: dict[str, dict[int, str]] = {}
        for r in records:
            loc = r.get("location") or []
            if len(loc) == 1 and loc[0][0] == loc[0][1] and r.get("correct_answer") is not None:
                m.setdefault(r["contract_id"], {})[loc[0][0]] = r["correct_answer"]
        return m

    pfinal = final_map(pred_records)
    typo_agg = Counter()
    inc, miss = [], []
    n_typo = 0
    for r in gold_records:
        loc = r.get("location") or []
        if not (len(loc) == 1 and loc[0][0] == loc[0][1]):
            continue
        cid, pid = r["contract_id"], loc[0][0]
        orig = r.get("original_text")
        if orig is None:
            orig = contracts[cid].paragraphs.get(pid, "") if cid in contracts else ""
        predtext = pfinal.get(cid, {}).get(pid, orig)
        goldtext = r.get("correct_answer") or ""
        for t in (r.get("error_types") or []):
            if t == "typo":
                n_typo += 1
                e = char_edit_f_beta(orig, goldtext, predtext)
                typo_agg["tp"] += e["tp"]; typo_agg["fp"] += e["fp"]; typo_agg["fn"] += e["fn"]
            elif t == "inconsistency":
                inc.append(1.0 if predtext in _accepted(r) else 0.0)
            elif t == "missing_element":
                miss.append(_progress(orig, predtext, goldtext))
    tp, fp, fn = typo_agg["tp"], typo_agg["fp"], typo_agg["fn"]
    pp = tp / (tp + fp) if (tp + fp) else 0.0
    rr = tp / (tp + fn) if (tp + fn) else 0.0
    T = 100 * f_beta(pp, rr, 0.5)
    C = 100 * _mean(inc)
    M = 100 * _mean(miss)
    return {"T": T, "C": C, "M": M, "R": 0.10 * T + 0.30 * C + 0.60 * M,
            "typo_tp": tp, "typo_fp": fp, "typo_fn": fn,
            "n": {"typo": n_typo, "inconsistency": len(inc), "missing_element": len(miss)}}


def total_score(L: float, R: float) -> float:
    return 0.5 * L + 0.5 * R


# --------------------------------------------------------------------------- 整合
def official_report(contracts: dict, gold: dict, pred: dict) -> dict:
    """返回与平台排行榜同名的完整字段（含各分项与总分）。"""
    loc = localization_score(gold.get("localization", []), pred.get("localization", []))
    rev = revision_score(contracts, gold.get("revision", []), pred.get("revision", []))
    L, R = loc["L"], rev["R"]
    return {
        "Total": total_score(L, R),
        "Localization": L, "Revision": R,
        "Loc_typo": loc["typo"]["f1"] * 100,
        "Loc_inconsistency": loc["inconsistency"]["f1"] * 100,
        "Loc_missing": loc["missing_element"]["f1"] * 100,
        "Rev_typo": rev["T"], "Rev_inconsistency": rev["C"], "Rev_missing": rev["M"],
        "Typo_TP": rev["typo_tp"], "Typo_FP": rev["typo_fp"], "Typo_FN": rev["typo_fn"],
        "loc_detail": loc, "rev_detail": rev,
    }

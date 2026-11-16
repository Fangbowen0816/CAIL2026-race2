# -*- coding: utf-8 -*-
"""typo 修订质量检测（无 gold 的代理指标 + 混淆集审计）。

用法：
  python scripts/typo_check.py --localization <f> --revision <f>
  python scripts/typo_check.py ... --guard        # 给出后置校验后的指标
  python scripts/typo_check.py ... --json

指标口径（45 合同无真值，用规则代理）：
  合法纠错 legit = 混淆集内替换 + 重复字/标点删除 + 补全未闭合括号
  违规编辑 viol  = 空白差异 + 当事人/数字变动 + 集外替换 + 非法插入/删除 + 长度不等改写
  precision 代理 = legit / (legit + viol)
说明：后置校验只作用于**纯 typo 段**（混段含不一致/缺失的合法改写，不动）。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.typo_guard import audit_text, guard_text, preserve_whitespace  # noqa: E402

LEGIT = {"subst-ok", "dup-del", "bracket", "add-char", "swap"}
CATS = ["subst-ok", "add-char", "dup-del", "bracket", "subst-out", "whitespace",
        "protected", "del", "insert", "structural", "swap"]


def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def measure(records, scope, use_guard=False):
    cat = collections.Counter()
    n = 0
    for r in records:
        if not r.get("location") or "typo" not in set(r.get("error_types") or []):
            continue
        types = set(r["error_types"])
        if (scope == "pure") != (types == {"typo"}):
            continue
        n += 1
        o, nw = r.get("original_text") or "", r.get("correct_answer") or ""
        if use_guard:
            nw = guard_text(o, nw) if types == {"typo"} else preserve_whitespace(o, nw)
        for e in audit_text(o, nw):
            cat[e["reason"]] += 1
    legit = sum(cat[k] for k in LEGIT)
    viol = sum(cat.values()) - legit
    return {"段数": n, "编辑总数": legit + viol, "合法纠错": legit, "违规编辑": viol,
            "precision代理": round(legit / (legit + viol), 4) if legit + viol else 1.0,
            "_cat": {k: cat[k] for k in CATS if cat[k]}}


def _row(name, b, a=None):
    if a is None:
        print("%-14s %9s %10s" % (name, b, ""))
    else:
        print("%-14s %9s %10s %8s" % (name, b, a, ("+" if a - b > 0 else "") + str(round(a - b, 4))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", default=None)
    ap.add_argument("--localization", required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    records = _read_jsonl(a.revision)
    out = {}
    for scope in ("pure", "mixed"):
        before = measure(records, scope, use_guard=False)
        after = measure(records, scope, use_guard=True) if a.guard else None
        out[scope] = {"before": before, "after": after}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    for scope, label in (("pure", "纯 typo 段"), ("mixed", "typo 混段")):
        b = out[scope]["before"]
        a_ = out[scope]["after"]
        print("=== %s（%d 段）===" % (label, b["段数"]))
        if not a_:
            for k in ("编辑总数", "合法纠错", "违规编辑", "precision代理"):
                _row(k, b[k])
            continue
        print("指标                校验前      校验后      Δ")
        for k in ("编辑总数", "合法纠错", "违规编辑", "precision代理"):
            _row(k, b[k], a_[k])
        cats = set(b["_cat"]) | set(a_["_cat"])
        for k in CATS:
            if k in cats:
                print("  %-12s %5d → %-5d" % (k, b["_cat"].get(k, 0), a_["_cat"].get(k, 0)))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

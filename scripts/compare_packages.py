# -*- coding: utf-8 -*-
"""对照两个提交包（15 合同，无 gold）：类型计数 / 原子重叠 / 自检残余。

用法：python scripts/compare_packages.py <包A目录> <包B目录>
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import parse_paragraphs          # noqa: E402
from cail_race2.records import RevisionRecord              # noqa: E402
from cail_race2.revise import apply_revisions               # noqa: E402
from cail_race2.verify import verify                        # noqa: E402


def _load(pkg, name):
    p = os.path.join(pkg, f"{name}_predictions.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def _atoms(loc):
    s = set()
    for r in loc:
        for iv in (r.get("location") or []):
            for p in range(iv[0], iv[1] + 1):
                s.add((r["contract_id"], p, r.get("error_type")))
    return s


def analyze(pkg, contracts):
    loc, rev = _load(pkg, "localization"), _load(pkg, "revision")
    by = collections.Counter(r.get("error_type") for r in loc)
    residual = 0
    for cid, ctx in contracts.items():
        paras = parse_paragraphs(ctx)
        rv = [RevisionRecord(cid, r.get("location"), r.get("error_types") or [],
                             r.get("original_text"), r.get("correct_answer"))
              for r in rev if r["contract_id"] == cid]
        final = apply_revisions(paras, rv)
        residual += len([c for c in verify(final)
                         if c.kind in ("conflict", "arithmetic", "missing")])
    return {"loc": len(loc), "rev": len(rev), "by": by, "residual": residual,
            "atoms": _atoms(loc)}


def main():
    a_dir, b_dir = sys.argv[1], sys.argv[2]
    contracts = {json.loads(l)["contract_id"]: json.loads(l)["context"]
                 for l in open(os.path.join(ROOT, "resources", "datasets",
                                            "race2_contract_review", "contracts.jsonl"),
                               encoding="utf-8")}
    A, B = analyze(a_dir, contracts), analyze(b_dir, contracts)
    for nm, d in (("A", A), ("B", B)):
        print(f"[{nm}] {d['loc']} loc / {d['rev']} rev | 残余问题 {d['residual']} | "
              f"类型 {dict(d['by'])}")
    inter, only_a, only_b = A["atoms"] & B["atoms"], A["atoms"] - B["atoms"], B["atoms"] - A["atoms"]
    print(f"定位原子重叠: 交集 {len(inter)} | 仅A {len(only_a)} | 仅B {len(only_b)} | "
          f"并集 {len(A['atoms'] | B['atoms'])}")
    print(f"Jaccard(定位): {len(inter)/len(A['atoms']|B['atoms']):.3f}")


if __name__ == "__main__":
    main()

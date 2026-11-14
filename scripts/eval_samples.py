# -*- coding: utf-8 -*-
"""用官方口径 scorer 在「提交示例」gold 上做回归评测（本地代理，无线上额度消耗）。

用法：
  python scripts/eval_samples.py                      # 自检：gold vs gold，应得 Total=100
  python scripts/eval_samples.py --pred-dir <目录>     # 对某次输出的定位/修订打分
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import load_contracts           # noqa: E402
from cail_race2.evaluate import official_report            # noqa: E402

SAMPLE = os.path.join(ROOT, "resources", "datasets", "race2_contract_review", "提交示例")


def _read_jsonl(path):
    if not path or not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def evaluate(pred_dir: str | None = None, sample_dir: str = SAMPLE) -> dict:
    contracts = {c.contract_id: c for c in
                 load_contracts(os.path.join(sample_dir, "contracts.jsonl"))}
    gold = {"localization": _read_jsonl(os.path.join(sample_dir, "localization_predictions.jsonl")),
            "revision": _read_jsonl(os.path.join(sample_dir, "revision_predictions.jsonl"))}
    if pred_dir:
        pred = {"localization": _read_jsonl(os.path.join(pred_dir, "localization_predictions.jsonl")),
                "revision": _read_jsonl(os.path.join(pred_dir, "revision_predictions.jsonl"))}
    else:
        pred = gold  # 自检
    return official_report(contracts, gold, pred)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred-dir", default=None)
    a = ap.parse_args()
    rep = evaluate(a.pred_dir)
    keys = ("Total", "Localization", "Revision", "Loc_typo", "Loc_inconsistency", "Loc_missing",
            "Rev_typo", "Rev_inconsistency", "Rev_missing", "Typo_TP", "Typo_FP", "Typo_FN")
    print(json.dumps({k: round(rep[k], 4) for k in keys}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

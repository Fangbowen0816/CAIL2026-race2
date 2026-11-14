# -*- coding: utf-8 -*-
"""在「提交示例」的 gold 上本地打分（2 份合同 mini dev set）。

用法：
  python scripts/eval_examples.py --mock
  python scripts/eval_examples.py                     # 用 LLM 预测再打分
  python scripts/eval_examples.py --pred-dir outputs/prelim   # 对已有提交打分
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import load_contracts  # noqa: E402
from cail_race2.env import load_dotenv  # noqa: E402
from cail_race2.evaluate import (localization_score, revision_score,  # noqa: E402
                                total_score)
from cail_race2.llm import LLMClient  # noqa: E402
from cail_race2.predictor import LLMPredictor, NullPredictor  # noqa: E402

DEFAULT_DIR = os.path.join(ROOT, "resources", "datasets", "race2_contract_review", "提交示例")


def _read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", default=DEFAULT_DIR)
    ap.add_argument("--pred-dir", default=None, help="已有提交目录（含两份 jsonl）")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    a = ap.parse_args()

    load_dotenv(os.path.join(ROOT, ".env"))
    contracts = {c.contract_id: c for c in load_contracts(
        os.path.join(a.examples, "contracts.jsonl"))}
    gold_loc = _read_jsonl(os.path.join(a.examples, "localization_predictions.jsonl"))
    gold_rev = _read_jsonl(os.path.join(a.examples, "revision_predictions.jsonl"))

    if a.pred_dir:
        pred_loc = _read_jsonl(os.path.join(a.pred_dir, "localization_predictions.jsonl"))
        pred_rev = _read_jsonl(os.path.join(a.pred_dir, "revision_predictions.jsonl"))
    else:
        predictor = NullPredictor() if a.mock else LLMPredictor(
            LLMClient(base_url=a.base_url, model=a.model))
        pred_loc, pred_rev = [], []
        for c in contracts.values():
            locs, revs = predictor.predict(c)
            pred_loc += [r.to_dict() for r in locs]
            pred_rev += [r.to_dict() for r in revs]

    loc = localization_score(gold_loc, pred_loc)
    rev = revision_score(contracts, gold_rev, pred_rev)
    total = total_score(loc["L"], rev["R"])

    print("== 定位 ==")
    for t in ("typo", "inconsistency", "missing_element"):
        m = loc[t]
        print(f"  {t:16s} P={m['precision']:.3f} R={m['recall']:.3f} "
              f"F1={m['f1']:.3f} (gold {m['n_gold']} / pred {m['n_pred']})")
    print(f"  L = {loc['L']:.2f}")
    print("== 修改 ==")
    print(f"  T={rev['T']:.2f} C={rev['C']:.2f} M={rev['M']:.2f}  (n={rev['n']})")
    print(f"  R = {rev['R']:.2f}")
    print(f"== 总分 S = 0.5L+0.5R = {total:.2f} ==")
    print("注：修改分为近似口径，官方评分脚本未公开。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""提交前门禁（preflight）：格式硬约束 + 示例口径回归，全过才放行。

用法：
  python scripts/preflight_submit.py \
      --contracts resources/datasets/race2_contract_review/contracts.jsonl \
      --localization outputs/agent_bench/localization_predictions.jsonl \
      --revision outputs/agent_bench/revision_predictions.jsonl
  # 额外在 gold 示例上跑官方口径（针对示例输出目录）：
  #   --sample-pred-dir outputs/agent_accept
退出码非 0 表示不允许提交。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from cail_race2.contracts import load_contracts            # noqa: E402
from cail_race2.submission_check import check               # noqa: E402
from eval_samples import evaluate                            # noqa: E402


def _read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append((n, json.loads(line)))
        except json.JSONDecodeError as e:
            rows.append((n, {"__bad__": str(e)}))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--localization", required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--sample-pred-dir", default=None)
    a = ap.parse_args()

    ok = True
    errors, warns = check(load_contracts(a.contracts),
                          _read_jsonl(a.localization), _read_jsonl(a.revision))
    for w in warns:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"[1/2] 格式硬约束：{len(errors)} ERROR, {len(warns)} WARN")
    ok = ok and not errors

    if a.sample_pred_dir:
        rep = evaluate(a.sample_pred_dir)
        print(f"[2/2] 示例口径：Total={rep['Total']:.4f} Loc={rep['Localization']:.4f} "
              f"Rev={rep['Revision']:.4f}")
    else:
        print("[2/2] 示例口径：跳过（未给 --sample-pred-dir）")

    print("\n结论：" + ("✅ 允许提交" if ok else "❌ 禁止提交（先修 ERROR）"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

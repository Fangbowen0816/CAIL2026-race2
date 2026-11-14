# -*- coding: utf-8 -*-
"""提交自检（调用 `cail_race2.submission_check`；官方未提供评分脚本）。

用法：
  python scripts/validate_submission.py \
      --contracts resources/datasets/race2_contract_review/contracts.jsonl \
      --localization outputs/prelim/localization_predictions.jsonl \
      --revision outputs/prelim/revision_predictions.jsonl
存在 ERROR 时退出码为 1。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import load_contracts          # noqa: E402
from cail_race2.submission_check import check             # noqa: E402


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append((n, json.loads(line)))
            except json.JSONDecodeError as e:
                rows.append((n, {"__bad__": str(e)}))
    return rows


def _report(errors, warns):
    for w in warns:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"\n结果：{len(errors)} ERROR, {len(warns)} WARN")
    if not errors:
        print("格式自检通过 ✔")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--localization", required=True)
    ap.add_argument("--revision", required=True)
    a = ap.parse_args()

    errors = [f"缺失文件: {p}" for p in (a.localization, a.revision) if not os.path.exists(p)]
    warns: list = []
    if not errors:
        errors, warns = check(load_contracts(a.contracts),
                              _read_jsonl(a.localization), _read_jsonl(a.revision))
    _report(errors, warns)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

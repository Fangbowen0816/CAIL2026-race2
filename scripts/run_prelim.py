# -*- coding: utf-8 -*-
"""初赛跑通入口：读合同 → 预测 → 写两份 JSONL → 打包 zip。

用法：
  python scripts/run_prelim.py --mock                 # 离线跑通（不调模型）
  python scripts/run_prelim.py                        # 用 .env / 环境变量里的 DeepSeek 配置
  python scripts/run_prelim.py --limit 3 --force      # 只跑前 3 份并覆盖缓存
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.env import load_dotenv  # noqa: E402
from cail_race2.llm import LLMClient  # noqa: E402
from cail_race2.pipeline import run, run_staged  # noqa: E402
from cail_race2.predictor import LLMPredictor, NullPredictor  # noqa: E402
from cail_race2.submission import make_zip  # noqa: E402

DEFAULT_CONTRACTS = os.path.join(
    ROOT, "resources", "datasets", "race2_contract_review", "contracts.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", default=DEFAULT_CONTRACTS)
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "prelim"))
    ap.add_argument("--mock", action="store_true", help="离线跑通，不调用模型")
    ap.add_argument("--legacy", action="store_true",
                    help="用旧的单步 predictor（非 Stage 流）")
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--no-json-mode", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="忽略逐合同缓存")
    a = ap.parse_args()

    load_dotenv(os.path.join(ROOT, ".env"))

    if a.mock:
        stats = run(a.contracts, a.out, NullPredictor(), force=a.force,
                    limit=a.limit, progress=print)
    else:
        client = LLMClient(base_url=a.base_url, model=a.model,
                           json_mode=not a.no_json_mode)
        print("使用模型:", client.model, "| base_url:", client.base_url)
        if a.legacy:
            stats = run(a.contracts, a.out, LLMPredictor(client), force=a.force,
                        limit=a.limit, progress=print)
        else:
            stats = run_staged(a.contracts, a.out, client, force=a.force,
                               limit=a.limit, progress=print)
    print(f"完成：合同 {stats.contracts}，定位记录 {stats.localizations}，"
          f"修订记录 {stats.revisions}")

    zip_path = make_zip(os.path.join(a.out, "cail2026_race2_submission.zip"),
                        [os.path.join(a.out, "localization_predictions.jsonl"),
                         os.path.join(a.out, "revision_predictions.jsonl")])
    print("提交包:", zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

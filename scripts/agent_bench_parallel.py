# -*- coding: utf-8 -*-
"""并行跑 CAIL 基准：逐合同审查（ksxc），从缓存汇总两份 JSONL 并打 zip。

用法：python scripts/agent_bench_parallel.py --out outputs/agent_bench --workers 4 [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from agent.config import load_ksxc_provider            # noqa: E402
from agent.review import review_contract               # noqa: E402
from cail_race2.contracts import load_contracts        # noqa: E402
from cail_race2.llm import LLMClient                   # noqa: E402
from cail_race2.submission import make_zip, write_jsonl  # noqa: E402

DEFAULT_CONTRACTS = os.path.join(
    ROOT, "resources", "datasets", "race2_contract_review", "contracts.jsonl")


def main() -> int:
    from cail_race2.env import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", default=DEFAULT_CONTRACTS)
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "agent_bench"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    contracts = load_contracts(a.contracts)
    prov = load_ksxc_provider()
    print("provider:", prov.redacted(), "| workers:", a.workers, flush=True)

    def work(c):
        try:
            client = LLMClient(base_url=prov.base_url, model=a.model or prov.model,
                               headers=prov.headers, api_key=prov.api_key, json_mode=False)
            review_contract(c, a.out, client, use_cache=not a.force)
            return c.contract_id, None
        except Exception as e:
            return c.contract_id, f"{type(e).__name__}: {e}"

    failures = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, c) for c in contracts]
        for f in as_completed(futs):
            cid, err = f.result()
            print("done", cid, ("FAIL " + err) if err else "", flush=True)
            if err:
                failures.append((cid, err))

    loc_rows, rev_rows = [], []
    for c in contracts:
        p = os.path.join(a.out, "predictions", f"{c.contract_id}.json")
        if not os.path.exists(p):
            loc_rows.append({"contract_id": c.contract_id, "location": [], "error_type": None})
            rev_rows.append({"contract_id": c.contract_id, "location": [], "error_types": [],
                             "original_text": None, "correct_answer": None})
            continue
        o = json.load(open(p, encoding="utf-8"))
        loc_rows += o.get("localization", [])
        rev_rows += o.get("revision", [])
    write_jsonl(os.path.join(a.out, "localization_predictions.jsonl"), loc_rows)
    write_jsonl(os.path.join(a.out, "revision_predictions.jsonl"), rev_rows)
    zip_path = make_zip(os.path.join(a.out, "cail2026_race2_submission.zip"),
                        [os.path.join(a.out, "localization_predictions.jsonl"),
                         os.path.join(a.out, "revision_predictions.jsonl")])
    print(f"合同 {len(contracts)} | 定位 {len(loc_rows)} | 修订 {len(rev_rows)}")
    if failures:
        print("失败", len(failures), failures)
    print("提交包:", zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

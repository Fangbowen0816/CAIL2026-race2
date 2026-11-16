# -*- coding: utf-8 -*-
"""对合同批量跑 stance 审查，输出仅含 stance 的定位 JSONL（供 recall_check 评估）。

用法：
  python scripts/stance_scan.py --contracts <f> --out outputs/stance_scan \
      --provider ksxc --model deepseek-v4.1-flash --workers 12 [--force]
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

from agent.config import load_provider            # noqa: E402
from cail_race2.contracts import Contract, load_contracts  # noqa: E402
from cail_race2.llm import LLMClient              # noqa: E402
from cail_race2.stance_review import review_stance, review_stance_cross  # noqa: E402


def main() -> int:
    from cail_race2.env import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", default="ksxc")
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--mode", default="std", choices=["std", "cross"])
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    p = load_provider(a.provider)
    client = LLMClient(api_key=p.api_key, base_url=p.base_url,
                       model=a.model or p.model, headers=p.headers, timeout=200)
    contracts = load_contracts(a.contracts)

    def work(c):
        path = os.path.join(a.out, f"{c.contract_id}{a.tag}.json")
        if os.path.exists(path) and not a.force and not a.tag:
            return c.contract_id, json.load(open(path, encoding="utf-8")), True
        try:
            fn = review_stance_cross if a.mode == "cross" else review_stance
            recs = fn(Contract(c.contract_id, c.context, c.paragraphs), client)
            data = [{"pid": r.location[0][0], "type": r.error_type} for r in recs if r.location]
            return c.contract_id, data, False
        except Exception as e:
            print("ERR", c.contract_id, type(e).__name__)
            return c.contract_id, [], False

    loc = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed({ex.submit(work, c): c.contract_id for c in contracts}):
            cid, data, cached = f.result()
            if not cached:
                json.dump(data, open(os.path.join(a.out, f"{cid}{a.tag}.json"), "w", encoding="utf-8"),
                          ensure_ascii=False)
            for d in data:
                loc.append({"contract_id": cid, "location": [[d["pid"], d["pid"]]],
                            "error_type": d["type"]})
            print("%-10s %s %d" % (cid, "缓存" if cached else "完成", len(data)))
    with open(os.path.join(a.out, "localization_predictions.jsonl"), "w", encoding="utf-8") as f:
        for r in loc:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("stance 定位 %d 条" % len(loc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

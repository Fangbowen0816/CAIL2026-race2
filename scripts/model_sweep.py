# -*- coding: utf-8 -*-
"""多模型并行 sweep：对 gold 示例跑完整审查链，用本地官方口径评测服务排序。

用法：
  python scripts/model_sweep.py                      # 默认模型集
  python scripts/model_sweep.py --specs ksxc:deepseek-v4.1-flash starstream:qwen3.8-max
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

from agent.config import load_provider                    # noqa: E402
from agent.review import review_contract                  # noqa: E402
from cail_race2.contracts import load_contracts            # noqa: E402
from cail_race2.evaluate import official_report            # noqa: E402
from cail_race2.llm import LLMClient                       # noqa: E402

SAMPLE = os.path.join(ROOT, "resources", "datasets", "race2_contract_review", "提交示例")
DEFAULT_SPECS = [
    "ksxc:deepseek-v4.1-flash", "ksxc:glm-5.3", "ksxc:kimi-k3", "ksxc:mimo-v2.5-pro",
    "starstream:deepseek-v4.1-flash", "starstream:qwen3.8-max", "starstream:glm-5.3",
    "starstream:kimi-k3.1-pro", "starstream:minimax-m3", "starstream:gpt-oss-120b",
]
KEYS = ("Total", "Localization", "Revision", "Loc_typo", "Loc_inconsistency", "Loc_missing",
        "Rev_typo", "Rev_inconsistency", "Rev_missing")


def _gold():
    return {"localization": [json.loads(l) for l in
            open(os.path.join(SAMPLE, "localization_predictions.jsonl"), encoding="utf-8") if l.strip()],
            "revision": [json.loads(l) for l in
            open(os.path.join(SAMPLE, "revision_predictions.jsonl"), encoding="utf-8") if l.strip()]}


def run_one(spec: str, out_root: str, contracts, repeat: int = 1) -> dict:
    prov_name, model_id = spec.split(":", 1)
    prov = load_provider(prov_name)
    cmap = {c.contract_id: c for c in contracts}
    gold = _gold()
    reps = []
    for i in range(max(1, repeat)):
        client = LLMClient(base_url=prov.base_url, model=model_id, headers=prov.headers,
                           api_key=prov.api_key, json_mode=False)
        loc_rows, rev_rows = [], []
        for c in contracts:
            d = os.path.join(out_root, f"{prov_name}__{model_id}", f"r{i}", c.contract_id)
            res = review_contract(c, d, client, use_cache=False)
            loc_rows += res["localization"]
            rev_rows += res["revision"]
        reps.append(official_report(cmap, gold, {"localization": loc_rows, "revision": rev_rows}))
    mean = {k: sum(r[k] for r in reps) / len(reps) for k in
            ("Total", "Localization", "Revision", "Loc_typo", "Loc_inconsistency", "Loc_missing",
             "Rev_typo", "Rev_inconsistency", "Rev_missing")}
    return {"spec": spec, "rep": mean, "runs": [round(r["Total"], 2) for r in reps]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", nargs="*", default=DEFAULT_SPECS)
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "sweep"))
    ap.add_argument("--repeat", type=int, default=1, help="每个模型重复次数，取均值（抗方差）")
    a = ap.parse_args()

    from cail_race2.env import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    contracts = load_contracts(os.path.join(SAMPLE, "contracts.jsonl"))

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=len(a.specs)) as ex:
        futs = {ex.submit(run_one, s, a.out, contracts, a.repeat): s for s in a.specs}
        for f in as_completed(futs):
            s = futs[f]
            try:
                r = f.result()
                results.append(r)
                print(f"done {s}: 均值Total={r['rep']['Total']:.4f} runs={r['runs']}", flush=True)
            except Exception as e:
                failures.append((s, f"{type(e).__name__}: {e}"))
                print(f"FAIL {s}: {type(e).__name__}: {e}", flush=True)

    results.sort(key=lambda r: r["rep"]["Total"], reverse=True)
    print("\n%-32s %7s %7s %7s %6s %6s %6s %6s %6s %6s" %
          ("model", "Total", "Loc", "Rev", "L_typo", "L_inc", "L_miss", "R_typo", "R_inc", "R_miss"))
    for r in results:
        d = r["rep"]
        print("%-32s %7.4f %7.2f %7.2f %6.2f %6.2f %6.2f %6.2f %6.2f %6.2f" % (
            r["spec"], d["Total"], d["Localization"], d["Revision"],
            d["Loc_typo"], d["Loc_inconsistency"], d["Loc_missing"],
            d["Rev_typo"], d["Rev_inconsistency"], d["Rev_missing"]))
    if failures:
        print("\n失败：", failures)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

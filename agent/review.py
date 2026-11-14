# -*- coding: utf-8 -*-
"""合同审查能力：复用 cail_race2 内核，产出批注合同 / 审查报告 / 两份 JSONL。

可作 CLI 调用（供 Agent 通过 run_shell 执行）：
  python -m agent.review --contract <文件> --out <目录> [--dry]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.contracts import Contract, load_contracts, parse_paragraphs  # noqa: E402
from cail_race2.pipeline import _cache_path, _load_cache, _save_cache  # noqa: E402
from cail_race2.stage import run_stages  # noqa: E402
from cail_race2.stages import (FactsStage, LLMDetectStage, LLMReviseStage,  # noqa: E402
                               VerifyStage)
from cail_race2.state import ContractState  # noqa: E402
from cail_race2.submission import write_jsonl  # noqa: E402


def review_contract(contract: Contract, out_dir: str, client=None,
                    dry: bool = False, use_cache: bool = False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    cache = _cache_path(out_dir, contract.contract_id)
    locs = revs = None
    if use_cache and not dry:
        cached = _load_cache(cache)
        if cached:
            locs, revs = cached

    state = ContractState(contract.contract_id, contract.paragraphs, contract.context)
    if dry or client is None:
        state = run_stages(state, [FactsStage(), VerifyStage()])
        locs, revs = [], []
    elif locs is None:
        state = run_stages(state, [FactsStage(), VerifyStage(),
                                   LLMDetectStage(client), LLMReviseStage(client)])
        locs, revs = state.localizations, state.revisions
        _save_cache(cache, locs, revs)

    locs = locs or []
    revs = revs or []
    final = state.final_paragraphs or contract.paragraphs

    write_jsonl(os.path.join(out_dir, "localization_predictions.jsonl"),
                [r.to_dict() for r in locs])
    write_jsonl(os.path.join(out_dir, "revision_predictions.jsonl"),
                [r.to_dict() for r in revs])
    annotated = _annotated_md(contract, final, locs, revs)
    open(os.path.join(out_dir, "annotated.md"), "w", encoding="utf-8").write(annotated)
    report = _report_md(contract, state, locs, revs)
    open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8").write(report)

    return {"contract_id": contract.contract_id,
            "annotated": os.path.join(out_dir, "annotated.md"),
            "report": os.path.join(out_dir, "report.md"),
            "localization": [r.to_dict() for r in locs],
            "revision": [r.to_dict() for r in revs]}


def _annotated_md(contract: Contract, final: dict, locs, revs) -> str:
    by_pid: dict[int, set] = {}
    for r in locs:
        for s, e in (r.location or []):
            for pid in range(s, e + 1):
                by_pid.setdefault(pid, set()).add(r.error_type)
    rev_by_pid = {}
    for r in revs:
        loc = r.location or []
        if len(loc) == 1:
            rev_by_pid[loc[0][0]] = r
    out = [f"# 批注合同 · {contract.contract_id}", ""]
    for pid in sorted(contract.paragraphs):
        text = contract.paragraphs[pid]
        tags = by_pid.get(pid)
        if not tags:
            out.append(f"`p{pid}` {text}")
            continue
        out.append(f"`p{pid}` **[{ '/'.join(sorted(tags)) }]** {text}")
        r = rev_by_pid.get(pid)
        if r and r.correct_answer and r.correct_answer != text:
            out.append(f"  - ↳ 修订：{r.correct_answer}")
    return "\n".join(out) + "\n"


def _report_md(contract: Contract, state, locs, revs) -> str:
    out = [f"# 审查报告 · {contract.contract_id}", "",
           f"- 段落数：{len(contract.paragraphs)}",
           f"- 定位问题：{len([r for r in locs if r.location])} 处",
           f"- 修订段落：{len([r for r in revs if r.location])} 段",
           f"- 确定性预分析冲突：{len(getattr(state, 'conflicts', []))} 处", ""]
    if getattr(state, "conflicts", None):
        out.append("## 预分析线索（待人工复核）")
        for c in state.conflicts:
            out.append(f"- [{c.kind}] p{c.pids}: {c.detail}")
        out.append("")
    out.append("## 问题清单")
    for r in locs:
        if r.location:
            out.append(f"- {r.error_type} @ p{r.location}")
    return "\n".join(out) + "\n"


def _load_one(path: str) -> Contract:
    if path.endswith(".jsonl"):
        contracts = load_contracts(path)
        return contracts[0]
    o = json.load(open(path, encoding="utf-8"))
    return Contract(o["contract_id"], o["context"], parse_paragraphs(o["context"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    from cail_race2.env import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    client = None
    if not a.dry:
        from agent.config import load_ksxc_provider
        from cail_race2.llm import LLMClient
        p = load_ksxc_provider()
        client = LLMClient(base_url=p.base_url, model=a.model or p.model,
                           headers=p.headers, api_key=p.api_key, json_mode=False)
    res = review_contract(_load_one(a.contract), a.out, client, dry=a.dry)
    print(json.dumps({k: res[k] for k in ("contract_id", "annotated", "report")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

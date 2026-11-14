# -*- coding: utf-8 -*-
"""端到端编排：逐合同预测（带缓存），汇总写出两份提交 JSONL。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .contracts import Contract, load_contracts
from .predictor import Predictor
from .records import LocalizationRecord, RevisionRecord
from .submission import write_jsonl


@dataclass
class RunStats:
    contracts: int = 0
    localizations: int = 0
    revisions: int = 0


def _cache_path(out_dir: str, contract_id: str) -> str:
    return os.path.join(out_dir, "predictions", f"{contract_id}.json")


def _load_cache(path: str) -> tuple[list[LocalizationRecord], list[RevisionRecord]] | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    locs = [LocalizationRecord(d["contract_id"], d["location"], d["error_type"])
            for d in obj.get("localization", [])]
    revs = [RevisionRecord(d["contract_id"], d["location"], d["error_types"],
                           d["original_text"], d["correct_answer"])
            for d in obj.get("revision", [])]
    return locs, revs


def _save_cache(path: str, locs: list[LocalizationRecord],
                revs: list[RevisionRecord]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"localization": [r.to_dict() for r in locs],
               "revision": [r.to_dict() for r in revs]}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def run(contracts_path: str, out_dir: str, predictor: Predictor,
        force: bool = False, limit: int | None = None,
        progress=lambda msg: None) -> RunStats:
    contracts: list[Contract] = load_contracts(contracts_path)
    if limit is not None:
        contracts = contracts[:limit]

    all_locs: list[LocalizationRecord] = []
    all_revs: list[RevisionRecord] = []
    stats = RunStats()

    for i, c in enumerate(contracts, 1):
        path = _cache_path(out_dir, c.contract_id)
        cached = None if force else _load_cache(path)
        if cached is not None:
            locs, revs = cached
            progress(f"[{i}/{len(contracts)}] {c.contract_id} (cache)")
        else:
            locs, revs = predictor.predict(c)
            _save_cache(path, locs, revs)
            progress(f"[{i}/{len(contracts)}] {c.contract_id} "
                     f"loc={len(locs)} rev={len(revs)}")
        all_locs.extend(locs)
        all_revs.extend(revs)
        stats.contracts += 1

    write_jsonl(os.path.join(out_dir, "localization_predictions.jsonl"),
                [r.to_dict() for r in all_locs])
    write_jsonl(os.path.join(out_dir, "revision_predictions.jsonl"),
                [r.to_dict() for r in all_revs])
    stats.localizations = len(all_locs)
    stats.revisions = len(all_revs)
    return stats

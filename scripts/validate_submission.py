# -*- coding: utf-8 -*-
"""提交自检（对齐赛道说明的校验口径；官方未提供评分脚本）。

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

from cail_race2.contracts import load_contracts  # noqa: E402
from cail_race2.records import (LocalizationRecord, RevisionRecord,  # noqa: E402
                                validate_localization, validate_revision)

LOC_KEYS = {"contract_id", "location", "error_type"}
REV_KEYS = {"contract_id", "location", "error_types", "original_text", "correct_answer"}


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--localization", required=True)
    ap.add_argument("--revision", required=True)
    a = ap.parse_args()

    errors, warns = [], []

    def err(msg):
        errors.append(msg)

    def warn(msg):
        warns.append(msg)

    contracts = load_contracts(a.contracts)
    by_id = {c.contract_id: c for c in contracts}

    if not os.path.exists(a.localization):
        err(f"缺失文件: {a.localization}")
    if not os.path.exists(a.revision):
        err(f"缺失文件: {a.revision}")
    if errors:
        _report(errors, warns)
        return 1

    covered = set()
    loc_by_pid: dict[str, dict[int, set]] = {}
    for n, obj in _read_jsonl(a.localization):
        if "__bad__" in obj:
            err(f"localization 第{n}行 JSON 错误: {obj['__bad__']}")
            continue
        if set(obj) != LOC_KEYS:
            err(f"localization 第{n}行字段应为 {sorted(LOC_KEYS)}，实际 {sorted(obj)}")
            continue
        cid = obj["contract_id"]
        if cid not in by_id:
            err(f"localization 第{n}行未知 contract_id: {cid!r}")
            continue
        covered.add(cid)
        rec = LocalizationRecord(cid, obj["location"], obj["error_type"])
        for e in validate_localization(rec, by_id[cid].paragraphs):
            err(f"localization {cid} 第{n}行: {e}")
        if obj["location"]:
            for s, e2 in obj["location"]:
                for pid in range(s, e2 + 1):
                    loc_by_pid.setdefault(cid, {}).setdefault(pid, set()).add(obj["error_type"])

    missing = set(by_id) - covered
    if missing:
        err(f"localization 未覆盖 {len(missing)} 个合同: {sorted(missing)[:5]}…")

    seen_pids: dict[str, set] = {}
    for n, obj in _read_jsonl(a.revision):
        if "__bad__" in obj:
            err(f"revision 第{n}行 JSON 错误: {obj['__bad__']}")
            continue
        if set(obj) != REV_KEYS:
            err(f"revision 第{n}行字段应为 {sorted(REV_KEYS)}，实际 {sorted(obj)}")
            continue
        cid = obj["contract_id"]
        if cid not in by_id:
            err(f"revision 第{n}行未知 contract_id: {cid!r}")
            continue
        rec = RevisionRecord(cid, obj["location"], obj["error_types"],
                             obj["original_text"], obj["correct_answer"])
        for e in validate_revision(rec, by_id[cid].paragraphs):
            err(f"revision {cid} 第{n}行: {e}")
        if obj["location"]:
            pid = obj["location"][0][0]
            if pid in seen_pids.setdefault(cid, set()):
                err(f"revision {cid} 第{n}行: 段落 p{pid} 重复修订")
            seen_pids[cid].add(pid)
            expected = loc_by_pid.get(cid, {}).get(pid, set())
            if expected and set(obj["error_types"]) != expected:
                warn(f"revision {cid} p{pid}: error_types={obj['error_types']} "
                     f"与定位类型并集 {sorted(expected)} 不一致")

    _report(errors, warns)
    return 1 if errors else 0


def _report(errors, warns):
    for w in warns:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"\n结果：{len(errors)} ERROR, {len(warns)} WARN")
    if not errors:
        print("格式自检通过 ✔")


if __name__ == "__main__":
    raise SystemExit(main())

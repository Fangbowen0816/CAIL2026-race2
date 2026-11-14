# -*- coding: utf-8 -*-
"""预测器接口 + 响应归一化 + 实现。

- NullPredictor：不调用模型，输出「无问题」哨兵，用于离线跑通流程/端到端测试。
- LLMPredictor：两阶段（定位 → 修订）调用 DeepSeek。
归一化函数把模型输出映射为合法 records，并丢弃非法项（映射关系单独测试）。
"""
from __future__ import annotations

import json
from typing import Protocol

from .contracts import Contract
from .llm import LLMClient
from .prompts import locate_messages, revise_messages
from .records import (ERROR_TYPE_SET, LocalizationRecord, RevisionRecord,
                      validate_localization, validate_revision)


class Predictor(Protocol):
    def predict(self, contract: Contract) -> tuple[list[LocalizationRecord],
                                                    list[RevisionRecord]]:
        ...


def _as_list(obj, *keys) -> list:
    """从 dict/list 响应里取列表：支持 {"issues": [...]}、{"revisions": [...]} 或裸列表。"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, list):
                return v
    return []


def parse_localization(contract: Contract, obj) -> list[LocalizationRecord]:
    """归一化定位响应；非法项丢弃，全空则给一条无问题哨兵。"""
    records: list[LocalizationRecord] = []
    for item in _as_list(obj, "issues", "locations", "localization", "results"):
        if not isinstance(item, dict):
            continue
        rec = LocalizationRecord(contract.contract_id,
                                 item.get("location"), item.get("error_type"))
        if rec.error_type not in ERROR_TYPE_SET and rec.location:
            continue
        if not validate_localization(rec, contract.paragraphs):
            records.append(rec)
    if not records:
        records.append(LocalizationRecord(contract.contract_id, [], None))
    return records


def parse_revisions(contract: Contract, obj) -> list[RevisionRecord]:
    """归一化修订响应：original_text 按定位强制回填原文；同 PID 去重；非法项丢弃。"""
    records: list[RevisionRecord] = []
    seen: set[int] = set()
    for item in _as_list(obj, "revisions", "results", "changes"):
        if not isinstance(item, dict):
            continue
        loc = item.get("location") or []
        if not (len(loc) == 1 and len(loc[0]) == 2 and loc[0][0] == loc[0][1]):
            continue
        pid = loc[0][0]
        if pid in seen or pid not in contract.paragraphs:
            continue
        seen.add(pid)
        types = [t for t in dict.fromkeys(item.get("error_types") or []) if t in ERROR_TYPE_SET]
        rec = RevisionRecord(contract.contract_id, [[pid, pid]], types,
                             contract.paragraphs[pid], item.get("correct_answer"))
        if not validate_revision(rec, contract.paragraphs):
            records.append(rec)
    if not records:
        records.append(RevisionRecord(contract.contract_id, [], [], None, None))
    return records


class NullPredictor:
    """离线哨兵：不调用模型，输出无问题。（用于先跑通流程）"""
    def predict(self, contract: Contract):
        return ([LocalizationRecord(contract.contract_id, [], None)],
                [RevisionRecord(contract.contract_id, [], [], None, None)])


class LLMPredictor:
    def __init__(self, client: LLMClient):
        self.client = client

    def predict(self, contract: Contract):
        issues_obj = self.client.complete_json(locate_messages(contract))
        locs = parse_localization(contract, issues_obj)
        locs_for_prompt = json.dumps([r.to_dict() for r in locs], ensure_ascii=False)
        revs = parse_revisions(contract, self.client.complete_json(
            revise_messages(contract, locs_for_prompt)))
        return locs, revs

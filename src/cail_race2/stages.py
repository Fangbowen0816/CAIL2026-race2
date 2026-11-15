# -*- coding: utf-8 -*-
"""Stage 实现：确定性阶段（facts/verify）与 LLM 阶段（detect/revise）。"""
from __future__ import annotations

from .consistency import apply_party_unification
from .detect import detect, merge_deterministic
from .facts import extract_facts
from .fill import apply_missing_fills
from .hints import build_hints
from .records import LocalizationRecord
from .repair import apply_arithmetic_repairs
from .revise import (apply_revisions, build_base, guard_revisions, normalize_revisions,
                     reconcile, revise)
from .state import ContractState
from .verify import verify


class FactsStage:
    name = "facts"

    def run(self, state: ContractState) -> ContractState:
        return state.clone(facts=extract_facts(state.paragraphs))


class VerifyStage:
    name = "verify"

    def run(self, state: ContractState) -> ContractState:
        return state.clone(conflicts=verify(state.paragraphs, state.facts))


class LLMDetectStage:
    name = "detect"

    def __init__(self, client):
        self.client = client

    def run(self, state: ContractState) -> ContractState:
        hints = build_hints(state.paragraphs, state.facts, state.conflicts)
        try:
            locs = detect(state.contract_id, state.context, state.paragraphs, self.client, hints)
        except Exception:
            locs = [LocalizationRecord(state.contract_id, [], None)]  # 降级：仅用确定性结果
        locs = merge_deterministic(locs, state.contract_id, state.paragraphs)
        return state.clone(localizations=locs)


class LLMReviseStage:
    name = "revise"

    def __init__(self, client):
        self.client = client

    def run(self, state: ContractState) -> ContractState:
        hints = build_hints(state.paragraphs, state.facts, state.conflicts)
        try:
            revs = revise(state.contract_id, state.context, state.paragraphs,
                          state.localizations, self.client, hints)
        except Exception:
            revs = []  # 降级：保留确定性算术修复
        locs, revs = reconcile(state.contract_id, state.localizations, revs)
        # #29 归一化底稿：以「原文 + 已产出修订」为基，后续确定性处理均在其上进行
        #     （避免以带错字原文为基 → 覆盖同段其他修复；original_text 最后回填原文）
        base = build_base(state.paragraphs, revs)
        base_facts = extract_facts(base)
        locs, revs = apply_arithmetic_repairs(state.contract_id, base, base_facts, locs, revs)
        locs, revs = reconcile(state.contract_id, locs, revs)
        locs, revs = apply_missing_fills(state.contract_id, base, locs, revs)
        locs, revs = apply_party_unification(state.contract_id, base, base_facts, locs, revs)
        locs, revs = reconcile(state.contract_id, locs, revs)
        # original_text 一律回填**输入原文逐字**（平台要求）
        revs = normalize_revisions(state.contract_id, state.paragraphs, revs)
        revs = guard_revisions(state.contract_id, state.paragraphs, revs)
        return state.clone(localizations=locs, revisions=revs,
                           final_paragraphs=apply_revisions(state.paragraphs, revs))

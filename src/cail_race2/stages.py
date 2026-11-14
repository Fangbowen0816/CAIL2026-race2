# -*- coding: utf-8 -*-
"""Stage 实现：确定性阶段（facts/verify）与 LLM 阶段（detect/revise）。"""
from __future__ import annotations

from .detect import detect, merge_deterministic
from .facts import extract_facts
from .hints import build_hints
from .revise import apply_revisions, normalize_revisions, reconcile, revise
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
        locs = detect(state.contract_id, state.context, state.paragraphs, self.client, hints)
        locs = merge_deterministic(locs, state.contract_id, state.paragraphs)
        return state.clone(localizations=locs)


class LLMReviseStage:
    name = "revise"

    def __init__(self, client):
        self.client = client

    def run(self, state: ContractState) -> ContractState:
        hints = build_hints(state.paragraphs, state.facts, state.conflicts)
        revs = revise(state.contract_id, state.context, state.paragraphs,
                      state.localizations, self.client, hints)
        locs, revs = reconcile(state.contract_id, state.localizations, revs)
        revs = normalize_revisions(state.contract_id, state.paragraphs, revs)
        return state.clone(localizations=locs, revisions=revs,
                           final_paragraphs=apply_revisions(state.paragraphs, revs))

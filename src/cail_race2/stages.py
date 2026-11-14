# -*- coding: utf-8 -*-
"""确定性 Stage 实现（包装 facts / verify 纯函数）。"""
from __future__ import annotations

from .facts import extract_facts
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

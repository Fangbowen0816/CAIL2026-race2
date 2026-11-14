# -*- coding: utf-8 -*-
"""Stage 接口与确定性编排。

- 阶段是纯函数：run(view-state) -> 新 state，不改全局。
- 编排器按固定顺序调用并推进 version（控制流固定，不做 LLM 编排）。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .state import ContractState


@runtime_checkable
class Stage(Protocol):
    name: str

    def run(self, state: ContractState) -> ContractState:
        ...


def run_stages(state: ContractState, stages, progress=lambda msg: None) -> ContractState:
    """顺序执行阶段；每阶段返回新 state，orchestrator 推进 version。"""
    for st in stages:
        before = state.version
        state = st.run(state)
        state.version = before + 1
        progress(f"stage {getattr(st, 'name', type(st).__name__)} -> v{state.version}")
    return state

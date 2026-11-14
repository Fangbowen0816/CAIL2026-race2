# -*- coding: utf-8 -*-
"""合同处理状态的唯一真相源。

约定：阶段（Stage）只读 state，返回新 state（增量合并）；orchestrator 负责推进 version。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass
class ContractState:
    contract_id: str
    paragraphs: dict[int, str]                      # 原始段落，不可变
    facts: list = field(default_factory=list)       # list[Fact]
    conflicts: list = field(default_factory=list)   # list[Conflict]
    localizations: list = field(default_factory=list)  # list[LocalizationRecord]
    revisions: list = field(default_factory=list)      # list[RevisionRecord]
    final_paragraphs: dict[int, str] = field(default_factory=dict)
    version: int = 0

    def clone(self, **changes) -> "ContractState":
        return replace(self, **changes)

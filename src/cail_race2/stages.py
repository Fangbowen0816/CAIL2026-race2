# -*- coding: utf-8 -*-
"""Stage 实现：确定性阶段（facts/verify）与 LLM 阶段（detect/revise）。"""
from __future__ import annotations

from .consistency import apply_party_unification
from .contracts import Contract
from .detect import detect, merge_deterministic
from .facts import extract_facts
from .fill import apply_missing_fills
from .hints import build_hints
from .records import LocalizationRecord
from .repair import apply_arithmetic_repairs
from .revise import (apply_revisions, build_base, ensure_revisions_for_localized,  # noqa: E402
                     guard_revisions, normalize_revisions, reconcile, revise)
from .stance_review import review_stance, review_stance_cross, filter_stance_overreport  # noqa: E402
from .typo_guard import guard_records  # noqa: E402


def _merge_stance(state: ContractState, locs: list, client) -> list:
    """#43：专用 stance 审查（逐条款穷举）结果并入定位（去重）。"""
    contract = Contract(state.contract_id, state.context, state.paragraphs)
    extra = review_stance(contract, client)
    covered = {(pid, "stance") for r in locs if r.error_type == "stance"
               for s, e in (r.location or []) for pid in range(s, e + 1)}
    for r in extra:
        pid = r.location[0][0]
        if (pid, "stance") in covered:
            continue
        locs.append(r)
        covered.add((pid, "stance"))
    return locs
from .state import ContractState
from .verify import verify, find_stance_symmetry


def _merge_stance_symmetry(state: ContractState, locs: list) -> list:
    """#45 P1：跨条款对等性（甲方↔乙方互换后结构配对）→ 补 stance 定位。"""
    covered = {(pid, "stance") for r in locs if r.error_type == "stance"
               for s, e in (r.location or []) for pid in range(s, e + 1)}
    for c in find_stance_symmetry(state.paragraphs):
        pid = c.pids[0]
        if (pid, "stance") not in covered:
            locs.append(LocalizationRecord(state.contract_id, [[pid, pid]], "stance"))
            covered.add((pid, "stance"))
    return locs


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

    def __init__(self, client, reviewer_client=None, reviewer_penalty_only: bool = True,
                 stance_filter: bool = False, stance_symmetry: bool = False):
        """reviewer_client：S7.5 跨模型审稿的独立第二模型。

        stance_filter / stance_symmetry / S7.5 **默认关闭**：R3 线上实证表明
        它们使 Loc_stance 20.93→17.85（−3.08），而离线标注代理指标却“变好”
        → 代理失效，暂不启用（见 docs/召回分析.md 阶段六）。
        """
        self.client = client
        self.reviewer_client = reviewer_client
        self.reviewer_penalty_only = reviewer_penalty_only
        self.stance_filter = stance_filter
        self.stance_symmetry = stance_symmetry

    def run(self, state: ContractState) -> ContractState:
        hints = build_hints(state.paragraphs, state.facts, state.conflicts)
        try:
            locs = detect(state.contract_id, state.context, state.paragraphs, self.client, hints)
        except Exception:
            locs = [LocalizationRecord(state.contract_id, [], None)]  # 降级：仅用确定性结果
        locs = merge_deterministic(locs, state.contract_id, state.paragraphs)
        locs = _merge_stance(state, locs, self.client)
        locs = filter_stance_overreport(state.contract_id, state.paragraphs, locs) \
            if self.stance_filter else locs
        locs = _merge_stance_symmetry(state, locs) if self.stance_symmetry else locs
        locs = self._merge_cross_review(state, locs)
        return state.clone(localizations=locs)

    def _merge_cross_review(self, state: ContractState, locs: list) -> list:
        """S7.5：跨模型审稿的**罚则类**候选并入（只补漏，不覆盖）。"""
        if self.reviewer_client is None:
            return locs
        try:
            extra = review_stance_cross(
                Contract(state.contract_id, state.context, state.paragraphs),
                self.reviewer_client, penalty_only=self.reviewer_penalty_only)
        except Exception:
            return locs
        covered = {(pid, "stance") for r in locs if r.error_type == "stance"
                   for s, e in (r.location or []) for pid in range(s, e + 1)}
        for r in extra:
            pid = r.location[0][0]
            if (pid, "stance") not in covered:
                locs.append(r)
                covered.add((pid, "stance"))
        return locs


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
        revs = guard_records(state.contract_id, state.paragraphs, revs)
        revs = ensure_revisions_for_localized(state.contract_id, state.paragraphs, locs, revs)
        return state.clone(localizations=locs, revisions=revs,
                           final_paragraphs=apply_revisions(state.paragraphs, revs))

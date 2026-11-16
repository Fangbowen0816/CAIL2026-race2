# -*- coding: utf-8 -*-
"""把确定性预分析（事实表 + 冲突 + 缺失）压成紧凑提示块，供 LLM 阶段作线索。"""
from __future__ import annotations

from .facts import Fact
from .verify import Conflict, find_slot_gap_candidates, find_stance_candidates


def build_hints(paragraphs: dict[int, str], facts: list[Fact],
                conflicts: list[Conflict], max_lines: int = 40) -> str:
    lines: list[str] = []

    parties: dict[str, list[str]] = {}
    for f in facts:
        if f.kind == "party":
            parties.setdefault(f.slot, [])
            tag = f"{f.value}(p{f.pid})"
            if tag not in parties[f.slot]:
                parties[f.slot].append(tag)
    if parties:
        lines.append("当事人：")
        for slot, items in parties.items():
            lines.append(f"- {slot}: " + "；".join(items))

    nums = [f for f in facts if f.kind in ("money", "quantity", "ratio") and f.slot]
    if nums:
        lines.append("关键数值（带槽位）：")
        for f in nums[:20]:
            lines.append(f"- {f.kind}/{f.slot}: {f.value}(p{f.pid})")

    if conflicts:
        lines.append("疑似问题（重点核对，勿盲从）：")
        for c in conflicts[:20]:
            lines.append(f"- [{c.kind}] p{c.pids}: {c.detail}")

    gaps = find_slot_gap_candidates(paragraphs, facts)
    if gaps:
        lines.append("疑似要素缺失（交付/付款类条款段内未见时间，重点核对）：")
        for c in gaps[:10]:
            lines.append(f"- p{c.pids}: {c.detail}")

    stance = find_stance_candidates(paragraphs)
    if stance:
        lines.append("疑似立场失衡（仅提示，需判断是否确实显失公平）：")
        for c in stance[:10]:
            lines.append(f"- p{c.pids[0]}: {c.detail}")

    from .verify import ESSENTIALS, contract_type
    if lines:   # 仅当已有其它发现时追加（避免干净合同被诱导误报）
        ctype = contract_type(paragraphs)
        lines.append(f"本合同类型（推断）：{ctype}；请核查必备要素是否缺失："
                     + "、".join(ESSENTIALS.get(ctype, ESSENTIALS["通用"])))

    # 注：通用错别字词典（resources/typo/general.jsonl）实测精度仅 ~0.12（多为函数字碎片），
    #     故**不注入提示**；见 docs/typo优化.md。

    if not lines:
        return ""
    return "\n".join(["【预分析（正则/规则抽取，供交叉核对，非最终结论）】"] + lines)[:4000]

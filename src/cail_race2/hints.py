# -*- coding: utf-8 -*-
"""把确定性预分析（事实表 + 冲突 + 缺失）压成紧凑提示块，供 LLM 阶段作线索。"""
from __future__ import annotations

from .facts import Fact
from .verify import Conflict


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

    if not lines:
        return ""
    return "\n".join(["【预分析（正则/规则抽取，供交叉核对，非最终结论）】"] + lines)[:4000]

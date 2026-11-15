# -*- coding: utf-8 -*-
"""#30 evidence 组装：按「段 + 槽位」检索，喂给句级改写模型。

选择顺序（由小到大）：
1. **局部**：`f.pid == 目标段` 的事实；
2. **同槽位全局**：目标段出现的槽位 → 全合同同槽位取值（一致性）；
3. **相关冲突**：`conflicts` 中 pids 含目标段的条目；
4. **同句式**：全合同同类型义务句（供措辞同构）。
"""
from __future__ import annotations


def build_evidence(pid: int, paragraphs: dict[int, str], facts: list,
                   conflicts: list, loc_types: list) -> dict:
    local = [f for f in facts if f.pid == pid]
    slots = {f.slot for f in local if getattr(f, "slot", "")}
    same_slot: dict[str, list] = {}
    for f in facts:
        if getattr(f, "slot", "") in slots and f.slot:
            same_slot.setdefault(f.slot, [])
            item = (f.pid, str(f.value))
            if item not in same_slot[f.slot]:
                same_slot[f.slot].append(item)
    rel_conflicts = [c for c in conflicts if pid in (getattr(c, "pids", None) or [])]
    return {
        "pid": pid,
        "text": paragraphs.get(pid, ""),
        "types": list(loc_types),
        "local_facts": [(f.kind, str(f.value)) for f in local],
        "same_slot": same_slot,
        "conflicts": [getattr(c, "detail", "") for c in rel_conflicts],
    }


def evidence_text(ev: dict) -> str:
    """把 evidence 压成紧凑文本（供 prompt）。"""
    lines = [f"待改句所在段（p{ev['pid']}）：{ev['text']}",
             f"问题类型：{ev['types'] or '（待定）'}"]
    if ev["local_facts"]:
        lines.append("本段事实：" + "；".join(f"{k}={v}" for k, v in ev["local_facts"]))
    if ev["same_slot"]:
        parts = [f"{s}: " + ", ".join(f"p{p}({v})" for p, v in vs) for s, vs in ev["same_slot"].items()]
        lines.append("同槽位（全文一致性约束）：" + "；".join(parts))
    if ev["conflicts"]:
        lines.append("相关冲突：" + "；".join(ev["conflicts"]))
    return "\n".join(lines)

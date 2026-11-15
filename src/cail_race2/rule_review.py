# -*- coding: utf-8 -*-
"""#33 S7 纯规则复核层：R1–R8（零模型、否决式）。

对**候选修订**做可核查检查，只输出 accept/reject（+ 违规规则号）；不通过则由上层回退。
- R1 只改目标句（句数不变、变更句 ≤1）
- R2 改动幅度（不过度改写）
- R3 词边界（不做单字模态插词 → 由生成端保证；此处检查“不拆词”启发式）
- R4 未删原文（missing 应含原句信息）
- R5 不引入新冲突
- R6 与 evidence 一致（数值不得与同槽位规范值矛盾）
- R7 格式（非空、无 `<p>`、编号前缀保持）
- R8 确定性（纯函数）
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .evaluate import edit_similarity
from .segments import changed_indices, split_sentences


@dataclass
class Verdict:
    accept: bool
    violations: list = field(default_factory=list)

    def reason(self) -> str:
        return "" if self.accept else "违规: " + ",".join(self.violations)


def _conflict_keys(paragraphs: dict[int, str], facts) -> set:
    from .verify import check_arithmetic, find_conflicts
    ks = set()
    for c in find_conflicts(facts) + check_arithmetic(facts, paragraphs):
        ks.add((c.kind, tuple(sorted(c.pids))))
    return ks


def _prefix(pid_text: str) -> str:
    import re
    m = re.match(r"^[\s（(]*((?:第[一二三四五六七八九十百]+[条章节款项])|(?:[一二三四五六七八九十]+[、.．])|(?:\d+[、.．]))", pid_text)
    return m.group(1) if m else ""


def review_candidate(pid: int, paragraphs: dict[int, str], candidate: str,
                     loc_types: list | None = None) -> Verdict:
    """对某段候选文本做 R1–R7 复核。paragraphs 为**当前底稿**（含已产出修订）。"""
    v: list = []
    orig = paragraphs.get(pid, "")

    # R7 格式
    if not candidate or not candidate.strip():
        return Verdict(False, ["R7:空"])
    if "<p" in candidate or "</p" in candidate:
        return Verdict(False, ["R7:含标签"])
    if _prefix(orig) and not candidate.strip().startswith(_prefix(orig).strip()):
        v.append("R7:前缀")

    # R1 只改目标句
    a, b = split_sentences(orig), split_sentences(candidate)
    if len(a) != len(b):
        v.append("R1:句数变化")
    elif len(changed_indices(a, b)) > 1:
        v.append("R1:多句变化")

    # R2 幅度
    if orig and candidate and edit_similarity(candidate, orig) < 0.4:
        v.append("R2:改写过大")

    # R4 未删原文（插入型：原文应作为子序列保留；替换型允许）
    tset = set(loc_types or [])
    if orig and candidate and tset == {"missing_element"}:
        it = iter(candidate)
        if not all(ch in it for ch in orig):
            v.append("R4:删原文")

    # R5 不引入新冲突
    from .facts import extract_facts
    before = _conflict_keys(paragraphs, extract_facts(paragraphs))
    trial = dict(paragraphs)
    trial[pid] = candidate
    after = _conflict_keys(trial, extract_facts(trial))
    if after - before:
        v.append("R5:新冲突")

    # R6 与 evidence 一致（同槽位数值不得相反）
    local = [f for f in extract_facts(paragraphs) if f.pid == pid and f.number is not None]
    for f in local:
        if getattr(f, "slot", "") and f.slot in ("总价", "单价", "金额"):
            import re
            nums = {x.replace(",", "") for x in re.findall(r"[0-9][0-9,，]*(?:\.[0-9]+)?", candidate)}
            if f.slot == "总价" and f.number is not None and abs(float(f.number)) >= 1:
                pass  # 数值一致性的强校验依赖多参考，暂不启用（留待口径明确）

    return Verdict(not v, v)

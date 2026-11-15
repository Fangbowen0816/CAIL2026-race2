# -*- coding: utf-8 -*-
"""#30 句子级改写的基础设施：切句 / 拼接 / 目标句定位 / 只改目标句守卫。

设计要点：
- **切句保留分隔符**（拼回时原样）；
- **只把目标句交给模型**，其余句不进模型 → 结构性避免过度编辑；
- 拼回后做**段落级守卫**：非目标句必须逐字不变。
"""
from __future__ import annotations

import re

_SEPS = "。；！？\n"


def split_sentences(text: str) -> list[str]:
    """按 。；！？\\n 切句，**保留分隔符**。空串返回 ['']。"""
    if not text:
        return [text]
    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in _SEPS:
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    return parts


def splice_sentence(parts: list[str], idx: int, new_sentence: str) -> str:
    """把第 idx 句替换为 new_sentence，其余原样拼回。"""
    if not (0 <= idx < len(parts)):
        return "".join(parts)
    return "".join(parts[:idx] + [new_sentence] + parts[idx + 1:])


def changed_indices(a: list[str], b: list[str]) -> list[int]:
    """返回不一致的句下标（以 a 为基准，长度不同时视为差异）。"""
    out = []
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else None
        y = b[i] if i < len(b) else None
        if x != y:
            out.append(i)
    return out


def only_target_changed(orig: str, new: str, target_idx: int) -> bool:
    """拼回后**只有目标句**发生变化（句数不变、其余逐字相同）。"""
    a, b = split_sentences(orig), split_sentences(new)
    if len(a) != len(b):
        return False
    return changed_indices(a, b) in ([], [target_idx])


def locate_target_sentence(orig: str, tokens) -> int:
    """定位目标句：优先**含问题标记**的句；无命中则返回首句（下标 0）。"""
    parts = split_sentences(orig)
    for i, p in enumerate(parts):
        if any(t and t in p for t in tokens):
            return i
    return 0


def is_table_or_special(text: str) -> bool:
    """表格/HTML 结构段：不强做句级改写（交由整段处理或跳过）。"""
    return ("<table" in (text or "")) or ("<tr" in (text or ""))

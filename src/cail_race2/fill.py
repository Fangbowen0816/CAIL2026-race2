# -*- coding: utf-8 -*-
"""#1 要素缺失确定性补写。

原则：**最小改动 + 规范表述**——只把缺失的要素（时间等）按规范短语插入原句，
保留其余原文逐字不变，避免 LLM 式的整段改写/过度补全。

规范短语取自 gold 示例口径（如交付：`在本合同生效后10个工作日内`）。
只在段内**确无时间信息**时补写；无法判定类型则不动（交回 LLM）。
"""
from __future__ import annotations

import re

from .records import LocalizationRecord, RevisionRecord

CANON = {
    "delivery_time": "在本合同生效后10个工作日内",
    "payment_time": "在验收完成后10个工作日内",
    "acceptance_time": "在本合同生效后10个工作日内",
    "service_time": "在本合同生效后10个工作日内",
}
_PAYMENT_VERBS = ("支付", "付款", "付清", "付讫", "汇付", "结算")
_DELIVERY_VERBS = ("交付", "交货", "送至", "送达", "发货", "运输", "配送")
_ACCEPTANCE_VERBS = ("验收", "检验", "检查")
_SERVICE_VERBS = ("提供", "完成", "履行", "承担", "开具", "提交")
_MODALS = ("负责", "应当", "须", "需", "应于", "将于", "应")
_TIME_RE = re.compile(r"\d+\s*(?:个工作日|工作日|日|天|个月|月|年)")
# 相对时间引用：出现则认为“已有时间”，不补（防误补）
_REL_TIME_RE = re.compile(
    r"(?:验收|完成|生效|签署|签订|交货|交付|收到|送达|付款|支付|结算)(?:之日)?(?:后|前|内|起)"
    r"|之(?:日)?(?:后|前|起)")


def classify_missing(text: str) -> str | None:
    """按条款动词判断缺失要素类型（付款优先于交付，再验收/服务）。"""
    if any(v in text for v in _PAYMENT_VERBS):
        return "payment_time"
    if any(v in text for v in _DELIVERY_VERBS):
        return "delivery_time"
    if any(v in text for v in _ACCEPTANCE_VERBS):
        return "acceptance_time"
    if any(v in text for v in _SERVICE_VERBS):
        return "service_time"
    return None


_VERBS_BY_KIND = {
    "payment_time": _PAYMENT_VERBS,
    "delivery_time": _DELIVERY_VERBS,
    "acceptance_time": _ACCEPTANCE_VERBS,
    "service_time": _SERVICE_VERBS,
}


def _insert_before_verb(text: str, phrase: str, verbs) -> str | None:
    pos = -1
    for v in verbs:
        i = text.find(v)
        if i >= 0 and (pos < 0 or i < pos):
            pos = i
    if pos < 0:
        return None
    # 若动词前紧邻模态词（负责/应当/…），插到模态词之后，保证语序自然
    ins, best = pos, -1
    for m in sorted(_MODALS, key=len, reverse=True):
        k = text.rfind(m, 0, pos)
        if k >= 0:
            e = k + len(m)
            if e > best:
                best = e
    if 0 < best <= pos:
        ins = best
    return text[:ins] + phrase + text[ins:]


def missing_fill(text: str) -> tuple[str, str] | None:
    """返回 (类型, 补写后文本)；无可确定性补写时返回 None。"""
    if not text or _TIME_RE.search(text) or _REL_TIME_RE.search(text):
        return None
    kind = classify_missing(text)
    if not kind:
        return None
    verbs = _VERBS_BY_KIND[kind]
    new = _insert_before_verb(text, CANON[kind], verbs)
    if not new or new == text:
        return None
    return kind, new


def apply_missing_fills(contract_id: str, paragraphs: dict[int, str],
                        locs: list[LocalizationRecord], revs: list[RevisionRecord]):
    """对被定位为 missing_element 的段落，用确定性补写替换 LLM 的过度补全。"""
    pids: set[int] = set()
    for r in locs:
        if r.error_type == "missing_element":
            for s, e in (r.location or []):
                pids.update(range(s, e + 1))
    if not pids:
        return locs, revs
    out = list(revs)
    for pid in sorted(pids):
        res = missing_fill(paragraphs.get(pid, ""))
        if not res:
            continue
        _, text = res
        out = [r for r in out if not (r.location and r.location[0][0] == pid)]
        out.append(RevisionRecord(contract_id, [[pid, pid]], ["missing_element"],
                                  paragraphs.get(pid, ""), text))
    return locs, out

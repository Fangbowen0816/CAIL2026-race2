# -*- coding: utf-8 -*-
"""确定性一致性检查。

三类信号：
- conflict   ：同一槽位出现互相冲突的取值（当事人名、合同总价、编号）
- arithmetic ：单价 × 数量 ≠ 总价（同段内）
- missing    ：条款含「另行协商/待定/空字段」等缺失标记
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .facts import Fact, extract_facts


@dataclass
class Conflict:
    kind: str                       # conflict | arithmetic | missing
    pids: list[int]
    detail: str
    slot: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "pids": self.pids, "detail": self.detail,
                "slot": self.slot}


_MISSING_MARKERS = ("另行协商", "另行约定", "另行确定", "另行签订", "另行补充", "另行商定",
                    "待定", "待补充", "待商定", "待确定", "未约定", "暂无",
                    "详见附件", "见附件", "以实际为准", "TBD", "＿＿", "____",
                    "（　）", "（）", "( )")
# 强标记：几乎必然是缺失（用于确定性合并进召回）
_STRONG_MISSING = ("另行协商", "另行约定", "另行确定", "另行签订", "另行补充", "另行商定",
                   "待定", "待补充", "待商定", "待确定", "未约定", "暂无")
_EMPTY_FIELD_RE = re.compile(
    r"(?:甲方|乙方|金额|日期|时间|地点|数量|单价|总价|价款|账户|开户行|税号)"
    r"\s*[:：]\s*(?=[，。；\n]|$)")
# 占位符未填（高精度）：只用日期占位。
# 数据集用 XX 做**脱敏**（如「北京XX体育文化传播有限公司」），下划线也常用于排版，
# 均不得当作缺失；仅识别「XX年XX月」这类待填日期。
_PLACEHOLDER_RE = re.compile(r"(?:【\s*】|XX\s*年\s*XX\s*月)")


def find_conflicts(facts: list[Fact]) -> list[Conflict]:
    groups: dict = defaultdict(list)
    for f in facts:
        if f.kind == "party" and f.slot:
            groups[("party", f.slot)].append(f)
        elif f.kind == "money" and f.slot == "总价":
            groups[("money", "总价")].append(f)
        elif f.kind == "code":
            groups[("code", "编号")].append(f)

    out: list[Conflict] = []
    for (kind, slot), fs in groups.items():
        values = sorted({f.value for f in fs})
        if len(values) >= 2:
            pids = sorted({f.pid for f in fs})
            out.append(Conflict("conflict", pids,
                                f"{kind}/{slot} 取值冲突: " + " vs ".join(str(v) for v in values), slot))
    return out


def check_arithmetic(facts: list[Fact], paragraphs: dict[int, str]) -> list[Conflict]:
    """同段内：单价 × 数量 与 总价 校验（各值唯一时才判，避免多标的误报）。"""
    by_pid: dict = defaultdict(lambda: {"unit": [], "qty": [], "total": []})
    for f in facts:
        if f.kind == "money" and f.slot == "单价":
            by_pid[f.pid]["unit"].append(f)
        elif f.kind == "quantity" and f.slot == "数量":
            by_pid[f.pid]["qty"].append(f)
        elif f.kind == "money" and f.slot == "总价":
            by_pid[f.pid]["total"].append(f)

    out: list[Conflict] = []
    for pid, g in by_pid.items():
        if len(g["unit"]) == 1 and len(g["qty"]) == 1 and len(g["total"]) == 1:
            unit, qty, total = g["unit"][0], g["qty"][0], g["total"][0]
            if unit.number is not None and qty.number is not None and total.number is not None:
                expected = unit.number * qty.number
                if abs(expected - total.number) > 0.01:
                    out.append(Conflict(
                        "arithmetic", [pid],
                        f"单价{unit.value}×数量{qty.number:g}={expected:g}，与总价{total.value}不符",
                        "总价"))
    return out


def find_missing_candidates(paragraphs: dict[int, str], strong: bool = False) -> list[Conflict]:
    markers = _STRONG_MISSING if strong else _MISSING_MARKERS
    out: list[Conflict] = []
    for pid in sorted(paragraphs):
        text = paragraphs[pid]
        if _PLACEHOLDER_RE.search(text):
            out.append(Conflict("missing", [pid], "占位符未填（XX/＿＿）"))
            continue
        hits = [m for m in markers if m in text]
        if hits:
            out.append(Conflict("missing", [pid], "缺失标记: " + "、".join(hits)))
        elif not strong and _EMPTY_FIELD_RE.search(text):
            out.append(Conflict("missing", [pid], "空字段"))
    return out


_SLOT_TRIGGERS = ("交付", "交货", "付款", "支付", "验收", "结算", "完成")
# 相对时间引用：出现则**不算**缺失（如「验收完成后」「生效后10日」）
_REL_TIME_RE = re.compile(
    r"(?:验收|完成|生效|签署|签订|交货|交付|收到|送达|付款|支付|结算)(?:之日)?(?:后|前|内|起)"
    r"|之(?:日)?(?:后|前|起)|起\s*\d|后\s*\d|内\s*(?:完成|支付|交付|付清)")


def find_slot_gap_candidates(paragraphs: dict[int, str], facts) -> list[Conflict]:
    """交付/付款类条款但段内无时间信息 → 疑似要素缺失（仅作提示，不强制判定）。"""
    by_pid: dict = defaultdict(list)
    for f in facts:
        by_pid[f.pid].append(f)
    out: list[Conflict] = []
    for pid in sorted(paragraphs):
        text = paragraphs[pid]
        if not any(t in text for t in _SLOT_TRIGGERS):
            continue
        if any(f.kind in ("date", "duration") for f in by_pid.get(pid, [])):
            continue
        if _REL_TIME_RE.search(text):
            continue
        if any(m in text for m in _STRONG_MISSING):
            continue
        out.append(Conflict("missing_gap", [pid], "交付/付款类条款段内未见时间"))
    return out


def verify(paragraphs: dict[int, str], facts: list[Fact] | None = None) -> list[Conflict]:
    facts = facts if facts is not None else extract_facts(paragraphs)
    out = (find_conflicts(facts) + check_arithmetic(facts, paragraphs)
           + find_missing_candidates(paragraphs))
    return sorted(out, key=lambda c: (c.pids[0] if c.pids else 0, c.kind))

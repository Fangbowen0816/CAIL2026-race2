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
# 兜底条款语境（“未尽事项/补充协议…”）：其“另行…”**不算缺失**
_BOILERPLATE = ("未尽", "补充协议", "其他约定", "其他事项", "协商解决", "附页", "其他未尽")
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
        elif f.kind == "place" and f.slot:
            groups[("place", f.slot)].append(f)

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
            if any(b in text for b in _BOILERPLATE):
                continue   # #26：兜底条款排除
            out.append(Conflict("missing", [pid], "缺失标记: " + "、".join(hits)))
        elif not strong and _EMPTY_FIELD_RE.search(text):
            out.append(Conflict("missing", [pid], "空字段"))
    return out


_SLOT_TRIGGERS = ("交付", "交货", "付款", "支付", "验收", "结算", "完成")
# 合同类型 → 必备要素清单（用于提示“建议核查是否缺失”）；#41
ESSENTIALS = {
    "买卖": ("标的物与数量", "质量标准", "交付时间", "交付地点", "价款及支付时间", "违约责任"),
    "租赁": ("租赁物", "租期", "租金及支付时间", "押金", "维修责任", "返还方式"),
    "服务": ("服务内容与标准", "服务期限", "付款时间", "验收标准", "成果归属", "违约责任"),
    "工程": ("工程范围", "工期", "价款与支付", "质量标准", "验收", "违约责任"),
    "劳动": ("岗位与职责", "劳动报酬", "工作地点", "合同期限", "社会保险"),
    "通用": ("当事人", "金额", "时间", "违约责任", "争议解决"),
}


def contract_type(paragraphs: dict[int, str]) -> str:
    t = "\n".join(paragraphs.values())
    for name, kws in [("租赁", ("租赁", "出租", "承租")), ("服务", ("服务", "委托", "策划")),
                      ("工程", ("工程", "施工", "承包")), ("劳动", ("劳动", "聘用")),
                      ("买卖", ("买卖", "购销", "供货", "采购"))]:
        if any(k in t for k in kws):
            return name
    return "通用"
# 标题/条款名（用于空缺检测排除标题行）
_HEADING_RE = re.compile(r"^\s*[（(]?\s*(?:第[一二三四五六七八九十百]+[条章节款项]|[一二三四五六七八九十]+[、.．]|\d+[、.．])")
# 立场失衡（stance）线索词：仅作提示，需 LLM 复核“是否确实失衡”
_STANCE_MARKERS = (
    "单方", "无需提供", "无需承担", "概不", "免除任", "免除.{0,8}责任", "无限期", "无条件",
    "自行承担", "自担", "不承担", "拒绝履行", "拒绝赔偿", "视为放弃", "不得异议", "逾期不予",
)


def find_stance_candidates(paragraphs: dict[int, str]) -> list[Conflict]:
    """扫描“失衡措辞”段落，作为 stance 的**线索**（不强制并入定位）。"""
    out: list[Conflict] = []
    for pid in sorted(paragraphs):
        text = paragraphs[pid]
        hits = [m for m in _STANCE_MARKERS if re.search(m, text)]
        if hits:
            out.append(Conflict("stance", [pid], "失衡措辞: " + "、".join(hits)))
    return out
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
        if _HEADING_RE.match(text.strip()):
            continue   # #26：标题行排除
        if any(f.kind in ("money", "quantity", "ratio") for f in by_pid.get(pid, [])):
            continue   # #26：同段已有具体值，不算“不见时间”的缺失
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
           + find_missing_candidates(paragraphs)
           + find_structure_gaps(paragraphs)
           + find_slot_gap_candidates(paragraphs, facts))
    dedup: dict = {}
    for c in out:
        dedup.setdefault((c.kind, tuple(c.pids)), c)
    return sorted(dedup.values(), key=lambda c: (c.pids[0] if c.pids else 0, c.kind))


# --- 结构化要素完整性（#45 P0）------------------------------------------------
_PARTY_LABELS = ("甲方", "乙方", "丙方", "丁方")
_CREDIT_CODE = ("统一社会信用代码", "社会信用代码")
_ACCOUNT_RE = re.compile(r"户\s*名|账户名称|收款人|收款账户")
_ACCOUNT_FIELDS = ("账号", "帐号", "开户行", "开户银行", "银行账号")
_INVOICE_TRIGGER = ("开票信息", "发票信息")
_INVOICE_BANK = ("开户行", "开户银行", "银行账号", "账号", "帐号")
_DELIVERY_TRIGGER = ("交付", "交货", "送货", "移交", "运送", "提货")
_DELIVERY_PLACE = ("地点", "地址", "仓库", "现场", "送至", "交付至", "交付地点",
                   "指定", "上门", "工地", "场所", "处所", "甲方处", "乙方处")
_DELIVERY_METHOD = ("方式", "快递", "物流", "运输", "自提", "承运", "邮寄", "托运")


def _party_defs(paragraphs: dict[int, str]) -> dict:
    """各方定义段：首次出现「X方：」且非短标题的段落。"""
    defs: dict = {}
    for pid in sorted(paragraphs):
        t = paragraphs[pid] or ""
        if _HEADING_RE.match(t.strip()) and len(t) < 40:
            continue
        for lab in _PARTY_LABELS:
            if lab not in defs and re.search(lab + r"\s*[:：]", t):
                defs[lab] = pid
    return defs


def find_structure_gaps(paragraphs: dict[int, str]) -> list[Conflict]:
    """结构化要素缺失：主体信息对等 / 收款账户 / 开票信息 / 交付三要素。"""
    out: list[Conflict] = []
    pids_sorted = sorted(paragraphs)

    def window(pid: int, span: int) -> str:
        ids = [p for p in pids_sorted if p >= pid][:span]
        return "".join((paragraphs.get(p) or "") for p in ids)

    # 1) 主体信息对等：一方有统一社会信用代码、另一方没有
    defs = _party_defs(paragraphs)
    has: dict = {}
    for lab, pid in defs.items():
        w = window(pid, 2)
        m = re.search(lab + r"\s*[:：]", w)
        suffix = w[m.end():] if m else w      # 只看本标签之后，避免把上一方的代码算进来
        has[lab] = any(k in suffix for k in _CREDIT_CODE)
    if defs and any(has.values()):
        for lab, pid in defs.items():
            if not has[lab]:
                out.append(Conflict("party_gap", [pid],
                                    f"{lab}主体信息不全（未列统一社会信用代码）"))

    # 2) 收款账户：有户名但缺开户行/账号（排除标题行与“...如下：”引导行）
    for pid in pids_sorted:
        t = (paragraphs[pid] or "").strip()
        if not _ACCOUNT_RE.search(t):
            continue
        if _HEADING_RE.match(t) or (t.endswith(("：", ":")) and len(t) < 30):
            continue
        if not any(k in window(pid, 2) for k in _ACCOUNT_FIELDS):
            out.append(Conflict("account_gap", [pid], "收款账户信息不全（缺开户行/账号）"))

    # 3) 开票信息：以“开票信息/发票信息”引导段为准判整块完整性
    for pid in pids_sorted:
        t = paragraphs[pid] or ""
        if not any(k in t for k in _INVOICE_TRIGGER):
            continue
        w = window(pid, 3)
        if not any(k in w for k in _INVOICE_BANK) or ("地址" not in w and "电话" not in w):
            out.append(Conflict("invoice_gap", [pid], "开票信息不全（缺开户行/账号/地址电话）"))
    return out

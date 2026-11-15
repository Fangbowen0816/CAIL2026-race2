# -*- coding: utf-8 -*-
"""确定性事实抽取（正则）。

把合同里的当事人、金额、数量、比例、日期、期限、编号抽成 (类型, 值, 段落号, 槽位)。
供 verify 做全局一致性检查；不调用任何模型。

Fact.kind 取值：
  party / money / quantity / ratio / date / duration / code
- money：number 为折合「元」的数值（万元/亿元已换算）
- quantity / ratio：number 为数值本身
- date：value 归一化为 YYYY-MM 或 YYYY-MM-DD
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PARTY_LABELS = (r"甲方|乙方|丙方|丁方|委托人|受托人|发包人|承包人|买方|卖方|"
                r"出租人|承租人|出卖人|买受人|供应商|采购人|服务方|客户|借款人|贷款人|"
                r"供方|需方|出租方|承租方|受托方|委托方|购买方|供货方|收货方|收货人|购买人|托管方|保管方")
# 标签内的空格（「甲 方」「乙 方」）先归一再抽取
_LABEL_SPACE_RE = re.compile(r"([甲乙丙丁供需])\s+(方)")


def _norm_labels(t: str) -> str:
    return _LABEL_SPACE_RE.sub(r"\1\2", t or "")
_COMPANY_SUFFIX = (r"有限公司|有限责任公司|股份有限公司|公司|集团|中心|学院|大学|"
                   r"研究院|研究所|事务所|委员会|管理局|医院|学校")
# 当事人提及里不应出现的动词/虚词（多字符，避免误伤「华为」等含单字的名称）
_MENTION_BLOCK = ("应", "负责", "指定", "交付", "提供", "支付", "开具", "按照",
                  "根据", "另行", "进行", "承担", "属于", "作为", "因为", "由于", "已经")
# 以这些字开头的候选几乎不可能是机构名（如「因疾病住医院」）
_MENTION_START_BLOCK = set("因由经系是该其此若如或被受于对向在将不未已的")

PARTY_DEF_RE = re.compile(
    rf"(?P<label>{PARTY_LABELS})(?:[（(](?P<paren>[^)）]{{1,8}})[)）])?\s*[:：]\s*"
    rf"(?P<name>[^，。；;、：:\n（）()\s]{{2,40}})")
PARTY_MENTION_RE = re.compile(
    rf"(?P<label>{PARTY_LABELS})(?P<name>[\u4e00-\u9fffA-Za-z0-9]{{2,30}}?(?:{_COMPANY_SUFFIX}))")
# 无标签机构名（兜底，kind=org）
ORG_RE = re.compile(rf"(?P<name>[\u4e00-\u9fff]{{2,20}}(?:{_COMPANY_SUFFIX}))")
# #23 地点字段：带标签（履行/交付/服务/所在地/地址/地点）+ 冒号或“为”
PLACE_RE = re.compile(
    r"(?P<label>履行地点|交付地点|交货地点|服务地点|交货地|交付地|所在地|地址|地点)"
    r"\s*[:：为]\s*(?P<value>[^，。；\n]{2,40})")

MONEY_RE = re.compile(r"(?P<num>[0-9][0-9,，]*(?:\.[0-9]+)?)\s*(?P<unit>亿元|万元|元)")
QTY_RE = re.compile(r"(?P<num>[0-9]+(?:\.[0-9]+)?)\s*"
                    r"(?P<unit>张|台|个|件|套|份|批|吨|千克|公斤|米|平方米|箱|盒|本|页|项|人|次|名|辆|部|间|层)")
DUR_RE = re.compile(r"(?P<num>[0-9]+)\s*"
                    r"(?P<unit>个工作日|工作日|个自然日|自然日|个月|月|日|天|周|年|小时|分钟)")
RATIO_RE = re.compile(r"(?P<num>[0-9]+(?:\.[0-9]+)?)\s*%")
DATE_CN_RE = re.compile(r"(?P<y>\d{4})\s*年\s*(?P<m>\d{1,2})\s*月(?:\s*(?P<d>\d{1,2})\s*日)?")
DATE_ISO_RE = re.compile(r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})")
CODE_RE = re.compile(r"(?:合同编号|项目编号|编号)\s*[:：]\s*([A-Za-z0-9\-]+)")

_MONEY_MUL = {"元": 1.0, "万元": 1e4, "亿元": 1e8}
# 槽位关键词 -> 归一名（越靠后越优先，取窗口内最靠右命中的）
_SLOT_MAP = [
    ("合同编号", "合同编号"), ("项目名称", "项目名称"),
    ("合同总价", "总价"), ("总金额", "总价"), ("总额", "总价"), ("总价", "总价"), ("价款", "价款"),
    ("单价", "单价"), ("金额", "金额"), ("数量", "数量"),
    ("税率", "比例"), ("比例", "比例"),
    ("定金", "定金"), ("押金", "定金"), ("违约金", "违约金"), ("赔偿金", "违约金"),
    ("滞纳金", "违约金"), ("保证金", "保证金"),
    ("预付款", "预付款"), ("尾款", "尾款"), ("服务费", "服务费"), ("报酬", "报酬"),
]


@dataclass(frozen=True)
class Fact:
    kind: str
    value: str
    pid: int
    slot: str = ""
    number: float | None = None
    start: int = -1          # 数值在段内的字符起止（用于确定性重写）
    end: int = -1

    def group_key(self):
        return (self.kind, self.slot)


def _infer_slot(text: str, pos: int, window: int = 24) -> str:
    # 派生金额（「即 1100 元」「50%，即…」）不应归给总价/单价槽位
    if any(ch in text[max(0, pos - 4):pos] for ch in ("即", "%")):
        return ""
    seg = text[max(0, pos - window):pos]
    best, best_idx = "", -1
    for kw, slot in _SLOT_MAP:
        i = seg.rfind(kw)
        if i > best_idx:
            best_idx, best = i, slot
    return best


def _num(s: str) -> float:
    return float(s.replace(",", "").replace("，", ""))


def extract_facts(paragraphs: dict[int, str]) -> list[Fact]:
    facts: list[Fact] = []
    seen: set = set()

    def add(kind, value, pid, slot="", number=None, start=-1, end=-1):
        key = (kind, value, pid, slot)
        if key not in seen:
            seen.add(key)
            facts.append(Fact(kind, value, pid, slot, number, start, end))

    for pid in sorted(paragraphs):
        text = paragraphs[pid]
        ptext = _norm_labels(text)   # #22：标签内空格归一（「甲 方」→「甲方」）

        for m in PARTY_DEF_RE.finditer(ptext):
            slot = m.group("paren") or m.group("label")
            add("party", m.group("name"), pid, slot)
        for m in PARTY_MENTION_RE.finditer(ptext):
            name = m.group("name")
            if name[0] in _MENTION_START_BLOCK or any(b in name for b in _MENTION_BLOCK):
                continue
            add("party", name, pid, m.group("label"))
        # #24 机构名兜底：无标签但含公司后缀的 token → org（仅作候选，不直接当冲突）
        party_names = {f.value for f in facts if f.kind == "party"}
        for m in ORG_RE.finditer(ptext):
            nm = m.group("name")
            if any(nm in p or p in nm for p in party_names):
                continue
            add("org", nm, pid, "机构")

        for m in CODE_RE.finditer(text):
            add("code", m.group(1), pid, "编号")

        for m in PLACE_RE.finditer(ptext):
            add("place", m.group("value").strip(), pid, m.group("label"))

        for m in MONEY_RE.finditer(text):
            unit = m.group("unit")
            add("money", _num(m.group("num")), pid, _infer_slot(text, m.start()),
                _num(m.group("num")) * _MONEY_MUL[unit], m.start("num"), m.end("num"))

        for m in QTY_RE.finditer(text):
            add("quantity", m.group("num") + m.group("unit"), pid,
                _infer_slot(text, m.start()), _num(m.group("num")))

        for m in DUR_RE.finditer(text):
            add("duration", m.group("num") + m.group("unit"), pid,
                _infer_slot(text, m.start()), float(m.group("num")))

        for m in RATIO_RE.finditer(text):
            add("ratio", m.group("num") + "%", pid, _infer_slot(text, m.start()),
                _num(m.group("num")))

        for m in DATE_ISO_RE.finditer(text):
            add("date", "%04d-%02d-%02d" % (int(m.group("y")), int(m.group("m")), int(m.group("d"))), pid)
        for m in DATE_CN_RE.finditer(text):
            d = m.group("d")
            val = "%04d-%02d" % (int(m.group("y")), int(m.group("m")))
            if d:
                val += "-%02d" % int(d)
            add("date", val, pid)

    return facts

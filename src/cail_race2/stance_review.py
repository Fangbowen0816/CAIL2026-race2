# -*- coding: utf-8 -*-
"""#43 stance 审查：逐条款穷举 + 判据清单 + 法律原则 + gold few-shot + 排除规则。

独立于主 detect 的一次专用调用（避免拖累 typo/inc/missing 的检测）。
产出：stance 定位（LocalizationRecord）。
"""
from __future__ import annotations

import re

from .contracts import Contract
from .records import LocalizationRecord
from .verify import _HEADING_RE, _PLACEHOLDER_RE, _STRONG_MISSING

# 判据清单（A–E）
_CHECKLIST = """A. 履行顺序/担保：是否要求一方在对方履约前先行付款/履行，且未给对方对等保障（预付、无担保）；
B. 责任免除：是否免除一方的赔偿/违约责任，或限制对方主要权利（无须承担、概不负责、无权索赔）；
C. 单方/无条件/无限期：是否赋予一方单方、无条件或无限期的权利（单方解除且不补偿、无限期、随时、任意）；
D. 风险/费用转嫁：是否让对方承担不合理的风险或费用（无过错也担责、全部费用由对方承担）；
E. 救济缺失：是否缺少对等义务或补救期限（只约束一方、不给整改/救济机会）。"""

# 法律原则（辅助）
_LAW = """参照「显失公平」与「格式条款」规则：免除己方责任、加重对方责任、限制对方主要权利的条款，倾向判为 stance。"""

# gold few-shot（复赛 5 份示例中的 6 条）
_FEWSHOT = """示例（判为 stance 的原文 → 理由）：
1. 「甲方支付合同总价2000元与乙方交付全部货物同时履行。」→ 名为同时履行，实为要求甲方先行付款（A）。
2. 「甲方应在货物交付前付清全部价款，乙方无需提供相应履约保障。」→ 要求买方交付前付清且卖方无担保（A/B）。
3. 「需方可在验收合格后无限期推迟付款，且不承担迟延付款责任。」→ 无限期且不担责（C/B）。
4. 「一方严重违约且经催告后15日内仍未纠正的，守约方无权解除合同。」→ 限制守约方主要权利（B/E）。
5. 「甲方交付的种羊不符合合同质量标准时，乙方不得要求甲方更换，甲方也无须承担更换费用。」→ 免除一方责任（B）。
6. 「货物不符合约定质量标准的，供方应免费更换并承担运输费用。」→ 责任归属未区分、由供方独担全部（D）。"""

_STANCE_SYS = f"""你是资深合同审查专家。请**逐条**判断每个条款是否存在**立场失衡（stance，显失公平/权利义务明显不对等）**。

判据（命中任一即为 stance）：
{_CHECKLIST}

{_LAW}

{_FEWSHOT}

规则：
1. **逐条**给出结论，不得跳过任何一条；
2. **对等、合理、有救济**（给了合理期限/补救机会）的条款判为 "ok"；
3. 仅含占位符/缺失标记/表述不清的条款**不判 stance**（那是要素缺失）；
4. 先在心里核对判据 A–E，再给 verdict。

严格只输出 JSON：
{{"reviews":[{{"pid":N,"verdict":"stance|ok","reason":"简要理由"}}]}}"""


# #45 P0-B：已知滥报形态（离线实测 F1 0.421→0.465）
_FP_MARK = ("无偿", "单方", "无须", "无需", "概不", "全部", "无限期", "同时履行",
            "不得", "有权", "先", "仅", "只")
_RE_ACCT = re.compile(r"统一社会信用代码|纳税人识别号|开票信息|开户行|账\s*号")
_RE_TERM = re.compile(r"(自.*起生效|合同期限|有效期|履行期限|租赁期)")


def is_stance_overreport(text: str) -> bool:
    """确定性的 stance 滥报形态：纯数值段 / 主体账户信息 / 期限生效条款。"""
    t = text or ""
    if re.search(r"\d", t) and not any(k in t for k in _FP_MARK):
        return True
    if _RE_ACCT.search(t):
        return True
    if _RE_TERM.search(t) and not any(k in t for k in ("无偿", "单方", "无限期")):
        return True
    return False


def filter_stance_overreport(contract_id: str, paragraphs: dict[int, str], locs: list) -> list:
    """剔除滥报的 stance 定位（仅对 error_type==stance 生效）。"""
    out = []
    for r in locs:
        if r.error_type != "stance" or not r.location:
            out.append(r)
            continue
        keep = [p for s, e in r.location for p in range(s, e + 1)
                if not is_stance_overreport(paragraphs.get(p, "") or "")]
        if keep:
            out.append(LocalizationRecord(r.contract_id, [[min(keep), max(keep)]], "stance"))
    return out


def _reviewable(paragraphs: dict[int, str]) -> list[int]:
    return [pid for pid in sorted(paragraphs)
            if (paragraphs[pid] or "").strip() and not _HEADING_RE.match(paragraphs[pid].strip())]


def stance_messages(contract: Contract) -> list[dict]:
    lines = [f"p{pid}: {contract.paragraphs[pid]}" for pid in _reviewable(contract.paragraphs)]
    return [{"role": "system", "content": _STANCE_SYS},
            {"role": "user", "content": "逐条审查以下条款：\n" + "\n".join(lines)}]


def _excluded(text: str) -> bool:
    """含占位符/强缺失标记 → 归 missing，不报 stance。"""
    t = text or ""
    return bool(_PLACEHOLDER_RE.search(t)) or any(m in t for m in _STRONG_MISSING)


def parse_stance_reviews(contract: Contract, obj) -> list[int]:
    """从 reviews 里取 verdict==stance 的 pid（校验存在、非空、非标题、非占位符）。"""
    items = obj.get("reviews") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return []
    out: list[int] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        pid = it.get("pid")
        if it.get("verdict") != "stance" or not isinstance(pid, int) or pid not in contract.paragraphs:
            continue
        text = contract.paragraphs[pid]
        if not (text or "").strip() or _HEADING_RE.match(text.strip()) or _excluded(text):
            continue
        if pid not in out:
            out.append(pid)
    return out


def review_stance(contract: Contract, client) -> list[LocalizationRecord]:
    """专用一次调用；失败返回空（由其它通道兜底）。"""
    try:
        obj = client.complete_json(stance_messages(contract))
    except Exception:
        return []
    pids = parse_stance_reviews(contract, obj)
    return [LocalizationRecord(contract.contract_id, [[p, p]], "stance") for p in pids]

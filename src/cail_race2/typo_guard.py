# -*- coding: utf-8 -*-
"""错别字修订的确定性后置校验（precision-first）。

设计依据（见 docs/召回分析.md 与 typo 编辑审计）：
  - 5 gold 上我们的 typo 修订只做 1–2 处等长同音替换 → 机制正确；
  - 45 合同上出现大量**非纠错**改动：删空白、当事人互换(甲↔乙)、集外替换、长跨度改写。
规则：
  G1 空白保真：只差空白 → 回退；
  G2 专名/数字保护：当事人称谓(甲/乙/丙/丁)与数字的增删改 → 回退；
  G3 混淆集闸门：汉字替换必须"同音或形近"（same_pinyin / same_stroke / 同拼音）；
  G4 合法结构编辑：连续重复字删除、重复标点删除、补全未闭合括号 → 保留；
  其余（单字乱插、集外多字改写等）→ 回退。
"""
from __future__ import annotations

import os
from difflib import SequenceMatcher
from functools import lru_cache

WHITESPACE = set(" \t\r\n\u3000\xa0\x0b\x0c\ufeff")
PARTY = set("甲乙丙丁")
_OPEN_BRACKETS = "（(【[《<「『"
_CLOSE_BRACKETS = "）)】]》>」』"
_PUNCT = set("。，、；：！？…—·")
_COMMON_PUNCT = set("，。、；：！？")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "resources", "confusion")

# same_stroke.txt 按共用部件分组，遗漏若干高频形近字（如 己/已/巳）；补一份高置信表。
_EXTRA_FORM = [
    "己已巳", "未末", "戊戌戍", "日曰", "千干", "人入", "力刀", "问间",
    "候侯", "账帐", "燥躁", "辩辨瓣瓣", "折拆", "待侍", "亨享", "哀衰",
    "采釆", "晴睛", "崇崈", "灸炙", "亳毫", "冈罔", "土士", "卩卪",
]


def _strip_ws(s: str) -> str:
    return "".join(c for c in s if c not in WHITESPACE)


@lru_cache(maxsize=1)
def _load_confusion() -> frozenset:
    pairs = set()
    for group in _EXTRA_FORM:
        chars = list(group)
        for i, a in enumerate(chars):
            for b in chars[i + 1:]:
                pairs.add((a, b))
                pairs.add((b, a))
    for name in ("same_pinyin.txt", "same_stroke.txt"):
        path = os.path.join(_DATA_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                chars = [c for col in line.split("\t") for c in col.strip() if c]
                for i, a in enumerate(chars):
                    for b in chars[i + 1:]:
                        pairs.add((a, b))
                        pairs.add((b, a))
    return frozenset(pairs)


@lru_cache(maxsize=4096)
def _pinyin(ch: str) -> str:
    try:
        from pypinyin import lazy_pinyin, Style
        return "".join(lazy_pinyin(ch, style=Style.NORMAL))
    except Exception:
        return ch


def confused(x: str, y: str) -> bool:
    """两个字是否"音似 / 形近"（可互相误写）。"""
    if x == y:
        return True
    if (x, y) in _load_confusion():
        return True
    return _pinyin(x) == _pinyin(y)


def _protected(s: str) -> list:
    return [c for c in s if c in PARTY or c.isdigit()]


def _is_duplicate_removal(a: str, orig: str, i1: int, i2: int) -> bool:
    """删除的是连续重复字 / 重复标点（原文里确有重复）。"""
    prev = orig[i1 - 1] if i1 > 0 else ""
    nxt = orig[i2] if i2 < len(orig) else ""
    for c in a:
        if c in _PUNCT:
            if prev == c or nxt == c:
                continue
            return False
        if c in (prev, nxt) or (orig.count(c) >= 2):
            continue
        return False
    return True


def _is_bracket_completion(b: str, orig: str, i1: int) -> bool:
    """插入的是闭合括号，用于补全前文未闭合的左括号。"""
    if not b or any(c not in _CLOSE_BRACKETS for c in b):
        return False
    prefix = orig[:i1]
    opens = sum(prefix.count(c) for c in _OPEN_BRACKETS)
    closes = sum(prefix.count(c) for c in _CLOSE_BRACKETS)
    return opens > closes


def _is_missing_char(s: str) -> bool:
    """少字补全：插入 1–2 个汉字/常用标点（则 以/的/进… 属真纠错）。"""
    return 1 <= len(s) <= 2 and all("\u4e00" <= c <= "\u9fff" or c in _COMMON_PUNCT for c in s)


def _verdict(a: str, b: str, orig: str, i1: int, i2: int):
    """返回 (是否保留, 原因)。"""
    ac, bc = _strip_ws(a), _strip_ws(b)
    if ac == bc:                                   # G1 只差空白 → 回退
        return False, "whitespace"
    if _protected(ac) != _protected(bc):           # G2 当事人/数字变动 → 回退
        return False, "protected"
    if not a:                                      # 插入
        if _is_missing_char(bc):
            return True, "add-char"                # 少字补全 → 保留
        return (True, "bracket") if _is_bracket_completion(bc, orig, i1) else (False, "insert")
    if not b:                                      # 删除
        return (True, "dup-del") if _is_duplicate_removal(ac, orig, i1, i2) else (False, "del")
    if len(ac) != len(bc):                         # 长度不等的改写 → 回退
        return False, "structural"
    if all(confused(x, y) for x, y in zip(ac, bc)):
        return True, "subst-ok"                    # G3 混淆集内替换
    return False, "subst-out"


def audit_text(original: str, revised: str) -> list:
    """审计一段文本的编辑：[{tag, old, new, keep, reason}]（词序颠倒计为 swap）。"""
    original = original or ""
    revised = revised or ""
    ops = [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2
           in SequenceMatcher(None, original, revised, autojunk=False).get_opcodes() if t != "equal"]
    swap = set()
    for k in range(len(ops) - 1):
        t1, a1, b1 = ops[k][0], original[ops[k][1]:ops[k][2]], revised[ops[k][3]:ops[k][4]]
        t2, a2, b2 = ops[k + 1][0], original[ops[k + 1][1]:ops[k + 1][2]], revised[ops[k + 1][3]:ops[k + 1][4]]
        if {t1, t2} == {"insert", "delete"}:
            x = b1 if t1 == "insert" else a1
            y = b2 if t2 == "insert" else a2
            if x and x == y:
                swap |= {k, k + 1}
    out = []
    for k, (tag, i1, i2, j1, j2) in enumerate(ops):
        if k in swap:
            out.append({"tag": tag, "old": original[i1:i2], "new": revised[j1:j2],
                        "keep": True, "reason": "swap"})
            continue
        keep, reason = _verdict(original[i1:i2], revised[j1:j2], original, i1, i2)
        out.append({"tag": tag, "old": original[i1:i2], "new": revised[j1:j2],
                    "keep": keep, "reason": reason})
    return out


def guard_text(original: str, revised: str) -> str:
    """对一段 typo 修订做后置校验，迭代到不动点后返回。"""
    if not original or not revised or original == revised:
        return revised
    cur = revised
    for _ in range(6):
        nxt = _guard_once(original, cur)
        if nxt == cur:
            break
        cur = nxt
    return cur


def _guard_once(original: str, revised: str) -> str:
    ops = [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2
           in SequenceMatcher(None, original, revised, autojunk=False).get_opcodes() if t != "equal"]
    swap = set()                                   # 词序颠倒：相邻 insert(X)/delete(X)
    for k in range(len(ops) - 1):
        t1, a1, b1 = ops[k][0], original[ops[k][1]:ops[k][2]], revised[ops[k][3]:ops[k][4]]
        t2, a2, b2 = ops[k + 1][0], original[ops[k + 1][1]:ops[k + 1][2]], revised[ops[k + 1][3]:ops[k + 1][4]]
        if {t1, t2} == {"insert", "delete"}:
            x = b1 if t1 == "insert" else a1
            y = b2 if t2 == "insert" else a2
            if x and x == y:
                swap |= {k, k + 1}
    out = []
    pos_o = pos_n = 0
    for k, (tag, i1, i2, j1, j2) in enumerate(ops):
        out.append(original[pos_o:i1])
        if k in swap:
            keep = True
        else:
            keep, _ = _verdict(original[i1:i2], revised[j1:j2], original, i1, i2)
        out.append(revised[j1:j2] if keep else original[i1:i2])
        pos_o, pos_n = i2, j2
    out.append(original[pos_o:])
    return "".join(out)


def preserve_whitespace(original: str, revised: str) -> str:
    """只做空白保真：内容不变、仅空白差异的编辑一律回退（对所有类型安全）。"""
    if not original or not revised or original == revised:
        return revised
    cur = revised
    for _ in range(4):
        ops = [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2
               in SequenceMatcher(None, original, cur, autojunk=False).get_opcodes() if t != "equal"]
        parts, pos = [], 0
        for tag, i1, i2, j1, j2 in ops:
            parts.append(original[pos:i1])
            a, b = original[i1:i2], cur[j1:j2]
            parts.append(a if _strip_ws(a) == _strip_ws(b) else b)
            pos = i2
        nxt = "".join(parts) + original[pos:]
        if nxt == cur:
            break
        cur = nxt
    return cur


def guard_records(contract_id: str, paragraphs: dict, records: list) -> list:
    """批量后置校验：**仅做空白保真**。

    R3 线上实证：完整规则（混淆集闸门/专名/结构）使 Rev_typo 61.70→59.91
    （TP −42 而 FP 仅 −17，即回退的编辑里 ~71% 其实是 gold）→ 过激，已降级；
    `guard_text()` 仍保留完整规则供离线分析/按需启用。
    """
    out = []
    for r in records:
        orig = getattr(r, "original_text", None) or ""
        ans = getattr(r, "correct_answer", None) or ""
        new = preserve_whitespace(orig, ans)
        if new == ans:
            out.append(r)
            continue
        out.append(type(r)(contract_id=r.contract_id, location=r.location,
                           error_types=r.error_types, original_text=r.original_text,
                           correct_answer=new))
    return out


def guard_record(record):
    """单条后置校验（纯 typo 段全规则，其它仅空白保真）。"""
    return guard_records(record.contract_id, None, [record])[0]

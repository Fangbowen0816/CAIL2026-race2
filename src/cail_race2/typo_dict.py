# -*- coding: utf-8 -*-
"""词典驱动的错别字检测/纠正（通用词典，构建自公开资源）。

词典位置：`resources/typo/general.jsonl`——由公开 CSC 语料（SIGHAN/MCSC/EC-LAW）
与混淆集（same_pinyin / same_stroke）+ 常用词表生成，**不含任何竞赛合同数据**。
竞赛合同的错别字集（`resources/typo/contract/`）**只用于验证算法**，不被本模块查询。

用法：
    d = TypoDict.load()
    d.find("乙方应向甲方提共办公桌")   # -> [{'start':8,'end':10,'wrong':'提共','right':'提供'}]
    d.fix("乙方应向甲方提共办公桌")    # -> '乙方应向甲方提供办公桌'
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from .typo_guard import confused

_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "resources", "typo", "general.jsonl")

_PARTY = set("甲乙丙丁")
#: 视为「真错别字」的类别（其余归跨段一致性/改写，不入词典）
KEEP_KINDS = {"subst", "punct", "dup", "missing", "transpose"}


def _is_single_cjk(s: str) -> bool:
    return len(s) == 1 and "\u4e00" <= s <= "\u9fff"


def _cjk_alnum(c: str) -> bool:
    return "\u4e00" <= c <= "\u9fff" or c.isalnum()


def nonpunct(s: str) -> str:
    return "".join(c for c in s if _cjk_alnum(c))


def _subseq(short: str, long: str) -> bool:
    it = iter(long)
    return all(c in it for c in short)


def _prot(rec: str) -> list:
    return [c for c in rec if c in _PARTY or c.isdigit()]


@lru_cache(maxsize=1)
def _wordset() -> frozenset:
    """jieba 词表（用于判断「错形」是否为合法词）。"""
    return frozenset(jieba_FREQ())


@lru_cache(maxsize=1)
def _wordfreq() -> dict:
    return jieba_FREQ()


@lru_cache(maxsize=1)
def jieba_FREQ() -> dict:
    try:
        import jieba
        jieba.initialize()
        return dict(jieba.dt.FREQ)
    except Exception:
        return {}


def is_valid_word(s: str) -> bool:
    """s 是否为常见合法词（是 → 其「错形」上下文相关，不能入典）。"""
    return len(s) >= 2 and s in _wordset()


def _token_starts(text: str) -> set:
    """jieba 分词起点集合（命中必须落在词首）。"""
    try:
        import jieba
        starts, pos = set(), 0
        for tok in jieba.cut(text):
            starts.add(pos)
            pos += len(tok)
        starts.add(pos)
        return starts
    except Exception:
        return set()


def _boundary_ok(text: str, i: int, n: int, valid=frozenset()) -> bool:
    """命中 [i,i+n) 是否不是更长词的内部（前减一/后加一/两侧都不构成词）。"""
    for s in (text[i - 1:i + n] if i > 0 else "", text[i:i + n + 1],
              text[i - 1:i + n + 1] if i > 0 else ""):
        if len(s) > n and s in valid:
            return False
    return True


def classify_pair(w: str, r: str):
    """判错别字类型：subst/punct/dup/missing/transpose/len/num/rewrite（None=无变化）。"""
    if not w or not r or w == r:
        return None
    if nonpunct(w) == nonpunct(r):
        if _prot(w) != _prot(r):
            return "num"
        return "punct"
    if len(w) == len(r):
        if all(confused(x, y) for x, y in zip(w, r)):
            return "subst"
        return "num" if _prot(w) != _prot(r) else "subst-out"
    if _subseq(w, r):
        return "missing"
    if _subseq(r, w):
        return "dup"
    if sorted(w) == sorted(r):
        return "transpose"
    if _prot(w) != _prot(r):
        return "num"
    return "len" if abs(len(w) - len(r)) <= 2 else "rewrite"


def build_lexicon(annotations, safe_only: bool = True) -> dict:
    """从标注（[{contract_id,wrong,right}]）构建词典：{(w,r): {count, contracts}}。

    safe_only=True：只保留「错形本身不是合法词」且非纯标点的条目
    （如 工做/没备/签定 保留；对方/响应/不足 这类合法词不入典，避免乱改）。
    """
    lex = {}
    for d in annotations:
        w, r = d["wrong"], d["right"]
        kind = classify_pair(w, r)
        if kind not in KEEP_KINDS:
            continue
        if safe_only and (kind == "punct" or is_valid_word(w)):
            continue
        e = lex.setdefault((w, r), {"count": 0, "contracts": set()})
        e["count"] += 1
        e["contracts"].add(d["contract_id"])
    for k in [(w, r) for (w, r) in lex if (r, w) in lex]:
        del lex[k]                                   # 剔双向歧义
    return lex


class TypoDict:
    """最长匹配、非重叠、左到右的词典检测器。"""

    def __init__(self, entries):
        self.entries = [(w, r) for w, r in entries
                        if w and r and w != r and not _is_single_cjk(w)]
        self._by_first = {}
        for w, r in self.entries:
            self._by_first.setdefault(w[0], []).append((w, r))
        for k in self._by_first:
            self._by_first[k].sort(key=lambda t: -len(t[0]))

    @classmethod
    def load(cls, path: str | None = None) -> "TypoDict":
        path = path or _DEFAULT
        entries = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        entries.append((d["wrong"], d["right"]))
        return cls(entries)

    def find(self, text: str, boundary: bool = True) -> list:
        """定位词典命中。boundary=True：命中的**首尾都须对齐分词边界且不在更长词内部**
        （避免在「共和国」里命中「和国」、「联系人」里命中「的人」）。"""
        out, i, n = [], 0, len(text or "")
        ws = _wordset() if boundary else frozenset()
        starts = _token_starts(text) if boundary else None
        while i < n:
            hit = None
            if not boundary or i in starts:
                for w, r in self._by_first.get(text[i], ()):
                    if text.startswith(w, i):
                        hit = (w, r)
                        break
            if hit and (not boundary or _boundary_ok(text, i, len(hit[0]), ws)):
                end = i + len(hit[0])
                if boundary and end not in starts:
                    i += 1
                    continue
                out.append({"start": i, "end": end, "wrong": hit[0], "right": hit[1]})
                i += len(hit[0])
            else:
                i += 1
        return out

    def fix(self, text: str) -> str:
        hits = self.find(text)
        if not hits:
            return text
        parts, pos = [], 0
        for h in hits:
            parts.append(text[pos:h["start"]] + h["right"])
            pos = h["end"]
        parts.append(text[pos:])
        return "".join(parts)

    def scan(self, paragraphs: dict) -> list:
        """扫描整份合同 → [{pid, wrong, right}]。"""
        out = []
        for pid in sorted(paragraphs):
            for h in self.find(paragraphs[pid] or ""):
                out.append({"pid": pid, "wrong": h["wrong"], "right": h["right"]})
        return out

    def candidates(self, paragraphs: dict, limit: int = 12, min_right_freq: int = 3000) -> list:
        """供 LLM 参考的**候选**（按正形词频降序，只留较高频正形）。"""
        freq = _wordfreq()
        out = []
        for pid in sorted(paragraphs):
            for h in self.find(paragraphs[pid] or ""):
                f = freq.get(h["right"], 0)
                if f >= min_right_freq:
                    out.append({"pid": pid, "wrong": h["wrong"], "right": h["right"], "freq": f})
        out.sort(key=lambda x: (-x["freq"], x["pid"]))
        return out[:limit]


def apply_typo_dict(contract_id: str, paragraphs: dict, locs: list, revs: list,
                    dictionary: "TypoDict | None" = None):
    """确定性词典补漏：对命中段落补齐 typo 定位与修订（LLM 已改的在其结果上继续改）。

    仅当错形不是合法词（词典已过滤）时才替换，因此误改风险低。
    """
    from .records import LocalizationRecord, RevisionRecord
    d = dictionary or TypoDict.load()
    if not d.entries:
        return locs, revs
    single = {r.location[0][0]: r for r in revs
              if r.location and len(r.location) == 1 and r.location[0][0] == r.location[0][1]}
    loc_types = {(r.location[0][0], r.error_type) for r in locs
                 if r.location and r.error_type}
    new_locs, out = list(locs), list(revs)
    for pid in sorted(paragraphs):
        src = paragraphs.get(pid) or ""
        r = single.get(pid)
        cur = (r.correct_answer if r is not None else src) or ""
        fixed = d.fix(cur)
        if fixed == cur:
            continue
        if (pid, "typo") not in loc_types:
            new_locs.append(LocalizationRecord(contract_id, [[pid, pid]], "typo"))
            loc_types.add((pid, "typo"))
        if r is not None:
            types = list(dict.fromkeys(list(r.error_types or []) + ["typo"]))
            out = [x for x in out if x is not r]
            out.append(RevisionRecord(contract_id, r.location, types,
                                      r.original_text, fixed))
        else:
            out.append(RevisionRecord(contract_id, [[pid, pid]], ["typo"], src, fixed))
    return new_locs, out

# -*- coding: utf-8 -*-
"""构建**通用**错别字纠错词典（只用公开资源，不含任何竞赛合同数据）。

来源：
  1. 公开 CSC 语料（SIGHAN-2015 / MCSC / EC-LAW）里的 错误片段 → 正确片段；
  2. 混淆集（same_pinyin / same_stroke）+ 常用词表 → 生成「错形非法词、正形合法词」的对。
过滤：错形不在 jieba 词表（非法词）、正形在词表、且无双向歧义。

用法：
  python scripts/build_general_lexicon.py --out resources/typo/general.jsonl --report
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cail_race2.typo_dict import _wordset  # noqa: E402
from cail_race2.typo_guard import _load_confusion  # noqa: E402

PUBLIC = os.path.join(ROOT, "resources", "typo", "public")


def _cjk(s: str) -> bool:
    return bool(s) and all("\u4e00" <= c <= "\u9fff" for c in s)


def pairs_from_tsv(path: str) -> list:
    """从「错误句\\t正确句」语料抽取片段级 错→正 对。"""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2 or parts[0] == parts[1]:
                continue
            sm = difflib.SequenceMatcher(None, parts[0], parts[1], autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                a, b = parts[0][i1:i2], parts[1][j1:j2]
                if _cjk(a) and _cjk(b) and len(a) <= 4 and len(b) <= 4:
                    out.append((a, b))
    return out


def _confusable_index():
    idx = collections.defaultdict(set)
    for a, b in _load_confusion():
        idx[a].add(b)
    return idx


def generate_pairs(words, idx, valid, common_char, max_per_char=4, min_word_freq=2000):
    """由常用词 + 混淆字生成：正形为常用词、错形为非法词。"""
    out = collections.Counter()
    for w, freq in words:
        if not (2 <= len(w) <= 4) or freq < min_word_freq or not _cjk(w):
            continue
        for i, c in enumerate(w):
            picks = [c2 for c2 in idx.get(c, ()) if common_char.get(c2, 0) > 0]
            picks.sort(key=lambda x: -common_char.get(x, 0))
            for c2 in picks[:max_per_char]:
                v = w[:i] + c2 + w[i + 1:]
                if v not in valid and v != w:
                    out[(v, w)] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    import jieba
    jieba.initialize()
    freq = jieba.dt.FREQ
    valid = set(freq)
    common_char = {c: f for c, f in freq.items() if len(c) == 1}

    pairs = collections.Counter()
    for name in ("sighan2015_test.tsv", "mcsc_test.tsv", "ec_law_test.tsv"):
        got = pairs_from_tsv(os.path.join(PUBLIC, name))
        for p in got:
            pairs[p] += 1
        if a.report:
            print("  %-22s 抽取 %d 对" % (name, len(got)))
    from_public = len(pairs)
    words = sorted(((w, f) for w, f in freq.items() if isinstance(w, str)),
                   key=lambda t: -t[1])[:20000]
    gen = generate_pairs(words, _confusable_index(), valid, common_char)
    if a.report:
        print("  公开语料 %d 对 | 生成 %d 对" % (from_public, len(gen)))
    for k, n in gen.items():
        pairs[k] += 0
    # 过滤：错形非法词、正形合法词、正形长度≥错形、无双向歧义
    keep = {}
    for (w, r) in pairs:
        if w in valid or r not in valid:
            continue
        keep[(w, r)] = 1
    for k in [(w, r) for (w, r) in keep if (r, w) in keep]:
        del keep[k]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for (w, r) in sorted(keep, key=lambda k: (-len(k[0]), k[0])):
            f.write(json.dumps({"wrong": w, "right": r}, ensure_ascii=False) + "\n")
    if a.report:
        print("通用词典 → %d 条 (%s, %.1f KB)" % (len(keep), a.out,
              os.path.getsize(a.out) / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

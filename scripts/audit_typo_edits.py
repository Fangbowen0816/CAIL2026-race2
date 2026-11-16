# -*- coding: utf-8 -*-
"""审计 typo 修订的字符级编辑：验证'句级自由改写是否改错字'。"""
import json, collections, difflib, sys
from pypinyin import lazy_pinyin, Style
sys.path.insert(0, "src")

rev = [json.loads(l) for l in open("outputs/semi_kdeep/revision_predictions.jsonl", encoding="utf-8")]


def py(ch):
    try:
        return "".join(lazy_pinyin(ch, style=Style.NORMAL))
    except Exception:
        return ch


def is_cjk(s):
    return all("\u4e00" <= c <= "\u9fff" for c in s)


typo = [r for r in rev if r["location"] and "typo" in (r.get("error_types") or [])]
print("typo 修订记录:", len(typo))

ops = collections.Counter()
subs_same = subs_diff = subs_punct = 0
per = collections.Counter()
ex_same, ex_diff, ex_ins, ex_del = [], [], [], []

for r in typo:
    o = r["original_text"] or ""
    n = r["correct_answer"] or ""
    cid = r["contract_id"]
    pid = r["location"][0][0]
    if o == n:
        per[0] += 1
        ops["原样"] += 1
        continue
    sm = difflib.SequenceMatcher(None, o, n, autojunk=False)
    ne = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        a, b = o[i1:i2], n[j1:j2]
        ne += 1
        if tag == "replace" and len(a) == len(b):
            for x, y in zip(a, b):
                ops["替换"] += 1
                if is_cjk(x) and is_cjk(y):
                    if py(x) == py(y):
                        subs_same += 1
                        ex_same.append((cid, pid, x, y))
                    else:
                        subs_diff += 1
                        ex_diff.append((cid, pid, x, y))
                else:
                    subs_punct += 1
        elif tag == "insert":
            ops["插入"] += 1
            ex_ins.append((cid, pid, b))
        elif tag == "delete":
            ops["删除"] += 1
            ex_del.append((cid, pid, a))
        else:
            ops["长度不等替换"] += 1
    per[ne] += 1

print("编辑操作:", dict(ops))
tot = subs_same + subs_diff + subs_punct
print("单字替换 %d: 同音 %d (%.0f%%) | 异音 %d (%.0f%%) | 含非汉字 %d"
      % (tot, subs_same, 100 * subs_same / max(tot, 1), subs_diff, 100 * subs_diff / max(tot, 1), subs_punct))
print("每段编辑次数分布:", dict(sorted(per.items())))
print("插入抽样:", ex_ins[:10])
print("删除抽样:", ex_del[:10])
print()
print("=== 异音替换（疑似改写而非纠错）抽样 ===")
for cid, pid, x, y in ex_diff[:20]:
    print("  %s p%s: %s(%s) -> %s(%s)" % (cid, pid, x, py(x), y, py(y)))
print()
print("=== 同音替换抽样（典型错别字纠正）===")
for cid, pid, x, y in ex_same[:15]:
    print("  %s p%s: %s -> %s (%s)" % (cid, pid, x, y, py(x)))

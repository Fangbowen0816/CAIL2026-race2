# -*- coding: utf-8 -*-
"""#25 detect 顺带输出结构化事实：解析 + 防幻觉校验 + 与正则合并。"""
from cail_race2.contracts import Contract, parse_paragraphs
from cail_race2.facts import Fact, extract_facts
from cail_race2.predictor import merge_facts, parse_facts

CTX = '<p id="1">合同总价2000元，履行地点：北京市朝阳区。</p>'
PARAS = parse_paragraphs(CTX)
C = Contract("C1", CTX, PARAS)


def test_parse_facts_keeps_in_text_values_only():
    obj = {"facts": [
        {"pid": 1, "kind": "money", "value": "2000元", "slot": "总价"},
        {"pid": 1, "kind": "place", "value": "北京市朝阳区", "slot": "履行地点"},
        {"pid": 1, "kind": "money", "value": "9999元", "slot": "总价"},   # 幻觉：原文无 → 丢弃
        {"pid": 9, "kind": "money", "value": "2000元"},                    # 段落不存在 → 丢弃
    ]}
    facts = parse_facts(C, obj)
    vals = {(f.kind, f.value) for f in facts}
    assert ("money", "2000元") in vals and ("place", "北京市朝阳区") in vals
    assert ("money", "9999元") not in vals


def test_merge_facts_dedup():
    a = extract_facts(PARAS)
    b = parse_facts(C, {"facts": [{"pid": 1, "kind": "money", "value": "2000元", "slot": "总价"}]})
    merged = merge_facts(a, b)
    keys = [(f.kind, f.value, f.pid, f.slot) for f in merged]
    assert len(keys) == len(set(keys))

# -*- coding: utf-8 -*-
from cail_race2.facts import extract_facts
from cail_race2.hints import build_hints
from cail_race2.verify import verify

PARAS = {
    1: "甲方：华辰科技有限公司；乙方：远山办公设备有限公司。",
    4: "交付时间另行协商。",
    5: "办公桌单价100元，数量20张，合同总价2200元。",
}


def test_hints_include_parties_conflicts_missing():
    facts = extract_facts(PARAS)
    hints = build_hints(PARAS, facts, verify(PARAS, facts))
    assert "远山办公设备有限公司" in hints
    assert "另行协商" in hints
    assert "总价" in hints and "p5" in hints


def test_hints_empty_when_nothing_found():
    assert build_hints({1: "甲乙双方友好协商。"}, [], []) == ""

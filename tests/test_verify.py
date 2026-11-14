# -*- coding: utf-8 -*-
from cail_race2.facts import extract_facts
from cail_race2.verify import verify


def _verify(paras):
    return verify(paras, extract_facts(paras))


def test_party_conflict_across_paragraphs():
    paras = {1: "甲方：华辰科技有限公司；乙方：远山办公设备有限公司。",
             3: "乙方北辰办公设备有限公司应在验收完成后开具发票。"}
    cs = [c for c in _verify(paras) if c.kind == "conflict"]
    assert cs and cs[0].pids == [1, 3]


def test_total_price_conflict_same_slot():
    paras = {1: "合同总价2000元。", 2: "最终合同总价2200元。"}
    cs = [c for c in _verify(paras) if c.kind == "conflict"]
    assert cs and cs[0].slot == "总价"


def test_arithmetic_mismatch_detected():
    paras = {5: "办公桌单价100元，数量20张，合同总价2200元。"}
    cs = [c for c in _verify(paras) if c.kind == "arithmetic"]
    assert cs and cs[0].pids == [5]


def test_arithmetic_ok_no_conflict():
    paras = {5: "办公桌单价100元，数量20张，合同总价2000元。"}
    assert [c for c in _verify(paras) if c.kind == "arithmetic"] == []


def test_missing_marker_detected():
    cs = [c for c in _verify({4: "交付时间另行协商。"}) if c.kind == "missing"]
    assert cs and cs[0].pids == [4]


def test_clean_paragraph_has_no_conflict():
    paras = {1: "甲方应在30日内支付合同价款。"}
    assert [c for c in _verify(paras) if c.kind in ("conflict", "arithmetic")] == []


def test_verify_output_sorted_by_pid():
    paras = {5: "交付时间另行协商。", 2: "合同总价2000元。", 9: "合同总价2200元。"}
    cs = _verify(paras)
    assert [c.pids[0] for c in cs] == sorted(c.pids[0] for c in cs)

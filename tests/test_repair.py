# -*- coding: utf-8 -*-
from cail_race2.facts import extract_facts
from cail_race2.repair import arithmetic_repairs


def test_c001_arithmetic_repair_fixes_total_and_derived_amount():
    paras = {5: "办公桌单价100元，数量20张，合同总价2200元。",
             6: "甲方支付合同总价的50%，即1100元；余款30日内付清。"}
    rep = arithmetic_repairs(paras, extract_facts(paras))
    assert "合同总价2000元" in rep[5]
    assert "即1000元" in rep[6]


def test_derived_amount_slot_is_empty():
    f = extract_facts({1: "合同总价的50%，即1100元。"})
    assert any(x.kind == "money" and x.number == 1100 and x.slot == "" for x in f)

# -*- coding: utf-8 -*-
from cail_race2.facts import extract_facts


def _facts(paras):
    return extract_facts(paras)


def test_party_definitions_extract_slot_and_name():
    f = _facts({1: "甲方：华辰科技有限公司；乙方：远山办公设备有限公司。"})
    parties = {(x.slot, x.value) for x in f if x.kind == "party"}
    assert ("甲方", "华辰科技有限公司") in parties
    assert ("乙方", "远山办公设备有限公司") in parties


def test_party_definition_with_parenthetical_uses_paren_slot():
    f = _facts({1: "委托人（甲方）：国家体育总局"})
    assert any(x.kind == "party" and x.slot == "甲方" and x.value == "国家体育总局" for x in f)


def test_party_mention_in_body_is_extracted():
    f = _facts({3: "乙方北辰办公设备有限公司应在验收完城后开具发票。"})
    assert any(x.kind == "party" and x.slot == "乙方" and "北辰" in x.value for x in f)


def test_party_mention_with_verb_is_filtered():
    f = _facts({1: "乙方向甲方交付XX公司产品。"})
    assert not [x for x in f if x.kind == "party"]


def test_money_slot_and_amount_conversion():
    f = _facts({5: "办公桌单价100元，数量20张，合同总价2000元。"})
    unit = [x for x in f if x.kind == "money" and x.slot == "单价"]
    total = [x for x in f if x.kind == "money" and x.slot == "总价"]
    assert unit and unit[0].number == 100
    assert total and total[0].number == 2000
    f2 = _facts({1: "合同总价3万元。"})
    assert any(x.kind == "money" and x.number == 30000 for x in f2)


def test_quantity_ratio_date_duration_code():
    f = _facts({1: "数量20张，比例50%，期限10个工作日，签署日2025年3月15日，合同编号：BP2025001。"})
    kinds = {x.kind for x in f}
    assert {"quantity", "ratio", "duration", "date", "code"} <= kinds
    assert any(x.kind == "date" and x.value == "2025-03-15" for x in f)
    assert any(x.kind == "ratio" and x.number == 50 for x in f)

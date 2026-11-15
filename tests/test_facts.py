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


def test_party_label_with_spaces_is_normalized():
    f = _facts({1: "甲 方：xx品牌营销有限公司\n乙 方：XX创意策划有限公司"})
    parties = {(x.slot, x.value) for x in f if x.kind == "party"}
    assert ("甲方", "xx品牌营销有限公司") in parties
    assert ("乙方", "XX创意策划有限公司") in parties


def test_party_label_variants_extended():
    f = _facts({1: "受托方（乙方）：山东某某信息科技有限公司"})
    assert any(x.kind == "party" and x.value.startswith("山东") for x in f)
    f2 = _facts({1: "供方：远山办公设备有限公司；需方：华辰科技有限公司"})
    assert any(x.kind == "party" and x.value.startswith("远山") for x in f2)


def test_org_fallback_for_unlabeled_company():
    f = _facts({1: "开户名称：北京某体育文化传播有限公司"})
    assert any(x.kind == "org" and "体育文化传播" in x.value for x in f)


def test_org_not_duplicated_when_labeled_party():
    f = _facts({1: "乙方：远山办公设备有限公司"})
    assert any(x.kind == "party" for x in f)
    assert not any(x.kind == "org" and "远山" in x.value for x in f)


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

# --- #10 鲁棒性：边界与反例 ---


def test_money_with_thousands_separator_and_decimals():
    f = _facts({1: "本合同总价款为：￥1,500,000.00元（大写：人民币壹佰伍拾万元整）。"})
    assert any(x.kind == "money" and x.number == 1500000 for x in f)


def test_iso_date_and_month_duration():
    f = _facts({1: "服务期自2026-03-01起至2026-12-31止，共 12 个月。"})
    assert any(x.kind == "date" and x.value == "2026-03-01" for x in f)
    assert any(x.kind == "duration" and x.number == 12 for x in f)


def test_no_false_money_without_unit():
    f = _facts({1: "第1条 本合同共3份，双方各执一份。"})
    assert [x for x in f if x.kind == "money"] == []


def test_large_amount_wan_and_yi_units():
    f = _facts({1: "总价3万元，保证金1.5亿元。"})
    nums = {round(x.number) for x in f if x.kind == "money"}
    assert 30000 in nums and 150000000 in nums


def test_money_slot_synonyms_map_to_canonical():
    f = _facts({1: "甲方应支付赔偿金5000元，另交押金800元。"})
    slots = {x.slot for x in f if x.kind == "money"}
    assert "违约金" in slots and "定金" in slots

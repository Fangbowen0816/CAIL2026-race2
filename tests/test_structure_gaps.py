# -*- coding: utf-8 -*-
"""结构化要素缺失规则（主体信息对等 / 收款账户 / 开票信息 / 交付三要素）。"""
from cail_race2.verify import find_structure_gaps


def kinds(paras):
    return {(c.kind, tuple(c.pids)) for c in find_structure_gaps(paras)}


def test_party_gap_when_other_party_has_code():
    paras = {1: "甲方：AAA有限公司  统一社会信用代码：91AAA", 2: "乙方：BBB有限公司"}
    assert ("party_gap", (2,)) in kinds(paras)


def test_no_party_gap_when_both_have_code():
    paras = {1: "甲方：AAA有限公司 统一社会信用代码：91AAA",
             2: "乙方：BBB有限公司 统一社会信用代码：91BBB"}
    assert not any(k == "party_gap" for k, _ in kinds(paras))


def test_no_party_gap_when_nobody_has_code():
    paras = {1: "甲方：AAA有限公司", 2: "乙方：BBB有限公司"}
    assert not any(k == "party_gap" for k, _ in kinds(paras))


def test_account_gap_when_only_holder_name():
    paras = {1: "户 名：AAA有限公司"}
    assert ("account_gap", (1,)) in kinds(paras)


def test_no_account_gap_when_complete():
    paras = {1: "户名：AAA有限公司 开户行：XX支行 账号：6228XXXX"}
    assert not any(k == "account_gap" for k, _ in kinds(paras))


def test_invoice_gap_when_block_incomplete():
    paras = {1: "甲方开票信息：", 2: "纳税人识别号：91AAA", 3: "户名：AAA有限公司"}
    assert any(k == "invoice_gap" for k, _ in kinds(paras))


def test_no_delivery_gap_rule_removed():
    # 交付地点/方式规则因精度仅 3% 已移除（见 docs/召回分析.md）
    assert not any(c.kind == "delivery_gap" for c in find_structure_gaps({1: "乙方应交付全部货物。"}))


def test_account_gap_skips_intro_line():
    paras = {1: "乙方收款账户信息如下：", 2: "户名：AAA 开户行：X 账号：1"}
    assert not any(k == "account_gap" for k, _ in kinds(paras))

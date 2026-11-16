# -*- coding: utf-8 -*-
"""typo_guard：错别字修订的确定性后置校验（空白保真/专名保护/混淆集闸门/合法结构编辑）。"""
from cail_race2.typo_guard import guard_text, confused


# --- 混淆集判定 ---
def test_confused_same_pinyin():
    assert confused("共", "供")      # 同音
    assert confused("间", "件")      # jian/jian
    assert confused("予", "于")      # yu/yu


def test_confused_stroke_form():
    assert confused("己", "已")      # 形近
    assert confused("地", "的")      # 形近/同音


def test_not_confused_unrelated():
    assert not confused("甲", "乙")
    assert not confused("北", "远")


# --- G1 空白保真 ---
def test_whitespace_only_reverted():
    assert guard_text("甲方  乙方。", "甲方 乙方。") == "甲方  乙方。"


def test_leading_whitespace_preserved():
    assert guard_text("\t7.1 交付", "7.1 交付") == "\t7.1 交付"


# --- G2 当事人/数字保护 ---
def test_party_swap_reverted():
    assert guard_text("乙方应付款。", "甲方应付款。") == "乙方应付款。"


def test_digit_change_reverted():
    assert guard_text("金额100元", "金额200元") == "金额100元"


# --- G3 混淆集闸门 ---
def test_same_pinyin_typo_kept():
    assert guard_text("提共办公桌", "提供办公桌") == "提供办公桌"


def test_stroke_typo_kept():
    assert guard_text("验收完城", "验收完成") == "验收完成"


def test_unrelated_substitution_reverted():
    assert guard_text("乙方付款", "丙方付款") == "乙方付款"


# --- G4 合法结构编辑 ---
def test_duplicate_char_deleted_kept():
    assert guard_text("司法送送达地址", "司法送达地址") == "司法送达地址"


def test_duplicate_punct_kept():
    assert guard_text("告知。。", "告知。") == "告知。"


def test_bracket_completion_kept():
    assert guard_text("（1如果发生", "（1）如果发生") == "（1）如果发生"


# --- G5 词序颠倒 / 少字（实证为真纠错）---
def test_transposition_kept():
    assert guard_text("不履行要主合同义务", "不履行主要合同义务") == "不履行主要合同义务"
    assert guard_text("本合同定约的保密期限", "本合同约定的保密期限") == "本合同约定的保密期限"
    assert guard_text("火灾、风台、暴雨", "火灾、台风、暴雨") == "火灾、台风、暴雨"


def test_missing_char_insert_kept():
    assert guard_text("违约金不足弥补损失", "违约金不足以弥补损失") == "违约金不足以弥补损失"


def test_multi_char_rewrite_reverted():
    assert guard_text("不可拒的因素", "不可抗力") == "不可拒的因素"


# --- 组合 ---
def test_mixed_keep_typo_revert_party():
    orig = "甲方向乙方提共办公桌。"
    rev = "乙方向甲方提供办公桌。"
    assert guard_text(orig, rev) == "甲方向乙方提供办公桌。"


def test_no_change_when_identical():
    s = "本合同自双方签字之日起生效。"
    assert guard_text(s, s) == s


# --- preserve_whitespace / guard_records ---
def test_preserve_whitespace_reverts_ws_only():
    from cail_race2.typo_guard import preserve_whitespace
    assert preserve_whitespace("甲方\t乙方  丙方", "甲方乙方丙方") == "甲方\t乙方  丙方"
    assert preserve_whitespace("金额 100", "金额200") == "金额200"   # 内容变则不回退


def test_guard_records_scope():
    from cail_race2.records import RevisionRecord
    from cail_race2.typo_guard import guard_records
    recs = [
        RevisionRecord("C", [[1, 1]], ["typo"], "提共办公桌", "提供办公桌"),
        RevisionRecord("C", [[2, 2]], ["stance"], "甲 方应付款", "甲方应付款"),
    ]
    out = guard_records("C", {}, recs)
    assert out[0].correct_answer == "提供办公桌"          # 纯 typo：保留真纠错
    assert out[1].correct_answer == "甲 方应付款"          # 非 typo：仅空白保真

# -*- coding: utf-8 -*-
"""#33 S7 规则复核：R1–R7。"""
from cail_race2.rule_review import review_candidate


def test_accepts_clean_single_sentence_rewrite():
    orig = {1: "乙方负责将货物送至甲方指定仓库。"}
    cand = "乙方负责在本合同生效后10个工作日内将货物送至甲方指定仓库。"
    assert review_candidate(1, orig, cand).accept is True


def test_rejects_empty_or_tagged():
    orig = {1: "条款。"}
    assert review_candidate(1, orig, "").accept is False
    assert review_candidate(1, orig, "<p>条款。</p>").accept is False


def test_rejects_multi_sentence_change():
    orig = {1: "第一句。第二句。第三句。"}
    cand = "第一句改。第二句改。第三句。"
    v = review_candidate(1, orig, cand)
    assert v.accept is False and any(x.startswith("R1") for x in v.violations)


def test_rejects_huge_rewrite():
    orig = {1: "甲方应支付价款。"}
    cand = "甲、乙双方应依照《中华人民共和国民法典》及相关法律法规之规定，本着平等自愿、诚实信用的原则，就本次交易项下全部价款之支付事宜另行达成书面约定并严格履行。"
    v = review_candidate(1, orig, cand)
    assert v.accept is False and any(x.startswith("R2") for x in v.violations)


def test_rejects_new_conflict():
    orig = {5: "合同总价2000元。", 6: "合同总价2200元。"}
    cand = "合同总价3000元。"            # 与原 p6 形成新冲突
    v = review_candidate(5, orig, cand)
    assert v.accept is False and any(x.startswith("R5") for x in v.violations)

# -*- coding: utf-8 -*-
"""#5 修订过度编辑抑制：TDD 测点。"""
from cail_race2.revise import guard_typo_edit
from cail_race2.records import RevisionRecord
from cail_race2.revise import guard_revisions

ORIG = "乙方应向甲方提共办公桌20张。"


def test_guard_keeps_minimal_typo_fix():
    assert guard_typo_edit(["typo"], ORIG, "乙方应向甲方提供办公桌20张。") == \
        "乙方应向甲方提供办公桌20张。"


def test_guard_reverts_large_typo_only_rewrite():
    big = "乙方应当向甲方提供办公桌共计二十张，并保证产品质量符合约定标准。"
    assert guard_typo_edit(["typo"], ORIG, big) == ORIG


def test_guard_reverts_content_appended_to_typo_only():
    orig = "乙方应向甲方提供办公桌20张。"
    ans = "乙方应在本合同生效后10个工作日内向甲方提供办公桌20张。"
    assert guard_typo_edit(["typo"], orig, ans) == orig


def test_guard_keeps_short_typo_fix():
    assert guard_typo_edit(["typo"], "乙应提共", "乙应提供") == "乙应提供"


def test_guard_ignores_multi_type_and_inconsistency():
    big = "乙方应当向甲方提供办公桌共计二十张，并保证产品质量符合约定标准。"
    assert guard_typo_edit(["typo", "inconsistency"], ORIG, big) == big
    assert guard_typo_edit(["inconsistency"], ORIG, big) == big


def test_guard_revisions_applies_per_record():
    revs = [RevisionRecord("C1", [[2, 2]], ["typo"], ORIG,
                           "乙方应当向甲方提供办公桌共计二十张，并保证质量。")]
    out = guard_revisions("C1", {2: ORIG}, revs)
    assert out[0].correct_answer == ORIG and out[0].original_text == ORIG


def test_guard_reverts_overedited_missing_without_deterministic_fill():
    orig = "本合同一式两份，双方各执一份。"
    ans = orig + "并严格遵守中华人民共和国法律法规及行业规范与质量标准。"
    revs = [RevisionRecord("C1", [[1, 1]], ["missing_element"], orig, ans)]
    out = guard_revisions("C1", {1: orig}, revs)
    assert out[0].correct_answer == orig   # 过度改写且无确定性补写 → 回退原文

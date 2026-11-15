# -*- coding: utf-8 -*-
"""#1 要素缺失确定性补写：TDD 测点（关键行为）。"""
from cail_race2.fill import missing_fill, classify_missing, apply_missing_fills
from cail_race2.records import LocalizationRecord, RevisionRecord


def test_delivery_time_fill_matches_gold_sample():
    # 与 gold C001 第 4 段逐字一致
    assert missing_fill("乙方负责将货物送至甲方指定仓库。") == (
        "delivery_time", "乙方负责在本合同生效后10个工作日内将货物送至甲方指定仓库。")


def test_payment_time_fill_keeps_rest():
    kind, text = missing_fill("甲方支付合同价款的50%。")
    assert kind == "payment_time"
    assert text == "甲方在验收完成后10个工作日内支付合同价款的50%。"


def test_no_trigger_returns_none():
    assert classify_missing("本合同一式两份，双方各执一份。") is None
    assert missing_fill("本合同一式两份，双方各执一份。") is None


def test_existing_time_not_refilled():
    assert missing_fill("乙方在验收完成后5日内将货物送至仓库。") is None


def test_apply_missing_fills_replaces_llm_overfill():
    paras = {4: "乙方负责将货物送至甲方指定仓库。"}
    locs = [LocalizationRecord("C1", [[4, 4]], "missing_element")]
    revs = [RevisionRecord("C1", [[4, 4]], ["missing_element"],
                           "乙方负责将货物送至甲方指定仓库。",
                           "乙方负责将货物送至甲方指定仓库，并提交进度计划、验收报告等材料。")]
    _, revs2 = apply_missing_fills("C1", paras, locs, revs)
    r = [r for r in revs2 if r.location and r.location[0][0] == 4][0]
    assert r.correct_answer == "乙方负责在本合同生效后10个工作日内将货物送至甲方指定仓库。"
    assert "missing_element" in r.error_types


def test_apply_missing_fills_noop_without_target():
    paras = {1: "甲方：华辰科技有限公司。"}
    locs = [LocalizationRecord("C1", [[1, 1]], "typo")]
    revs = [RevisionRecord("C1", [[1, 1]], ["typo"], "甲方：华辰科技有限公司。", "甲方：华辰科技有限公司。")]
    _, revs2 = apply_missing_fills("C1", paras, locs, revs)
    assert len(revs2) == 1 and revs2[0].error_types == ["typo"]


def test_acceptance_or_service_time_fill():
    got = missing_fill("乙方负责验收全部货物。")
    assert got and got[0] == "acceptance_time" and "在本合同生效后10个工作日内" in got[1]
    got2 = missing_fill("乙方负责提供技术服务。")
    assert got2 and got2[0] == "service_time"


def test_relative_time_clause_not_filled():
    assert missing_fill("乙方应在验收完成后开具发票。") is None
    assert missing_fill("甲方应在生效后10日内支付。") is None


def test_classify_missing_multi_supports_several_kinds():
    from cail_race2.fill import classify_missing_multi
    kinds = classify_missing_multi("乙方应在验收合格后交付货物并于当日支付全部价款。")
    assert "payment_time" in kinds and "delivery_time" in kinds and "acceptance_time" in kinds


def test_insert_does_not_split_word():
    # #32：「需方」不得被拆成「需…方」
    got = missing_fill("需方按本合同约定支付货款。")
    assert got is not None
    assert "需在" not in got[1] and got[1].startswith("需方")


def test_apply_keeps_reasonable_llm_version():
    from cail_race2.fill import apply_missing_fills
    orig = "乙方负责将货物送至甲方指定仓库。"
    ans = "乙方应在合同生效后十日内将货物送至甲方指定仓库。"
    locs = [LocalizationRecord("C1", [[4, 4]], "missing_element")]
    revs = [RevisionRecord("C1", [[4, 4]], ["missing_element"], orig, ans)]
    _, out = apply_missing_fills("C1", {4: orig}, locs, revs)
    llm = [x for x in out if x.location and x.location[0][0] == 4][0]
    assert llm.correct_answer == ans   # 不过度覆盖合理版本


def test_sentence_rewrite_only_changes_target():
    from cail_race2.revise import sentence_rewrite

    class Fake:
        def complete_json(self, m, **k):
            return {"sentence": "乙方负责在本合同生效后10个工作日内将货物送至仓库。"}

    orig = "第一句。乙方负责将货物送至仓库。第三句。"
    out = sentence_rewrite(1, {1: orig}, ["送至"], Fake(), "缺交付时间")
    assert out == "第一句。乙方负责在本合同生效后10个工作日内将货物送至仓库。第三句。"


def test_sentence_rewrite_reverts_when_guard_fails():
    from cail_race2.revise import sentence_rewrite

    class Fake:
        def complete_json(self, m, **k):
            return {"sentence": "第二句改。又加了一句。"}   # 多出句子 → 守卫失败

    orig = "第一句。第二句。"
    assert sentence_rewrite(1, {1: orig}, ["第二句"], Fake()) == orig


def test_sentence_rewrite_table_untouched():
    from cail_race2.revise import sentence_rewrite

    class Fake:
        def complete_json(self, m, **k):
            return {"sentence": "x"}

    t = "<table><tr><td>x</td></tr></table>"
    assert sentence_rewrite(1, {1: t}, ["x"], Fake()) == t
    # #29：底稿只吸收“不过度”的修订
    from cail_race2.revise import build_base
    orig = {1: "乙方应向甲方提共办公桌20张。"}
    ok = RevisionRecord("C1", [[1, 1]], ["typo"], orig[1], "乙方应向甲方提供办公桌20张。")
    assert build_base(orig, [ok])[1] == "乙方应向甲方提供办公桌20张。"
    over = RevisionRecord("C1", [[1, 1]], ["missing_element"], orig[1],
                          orig[1] + "，并提交进度计划、验收报告、质量保证书及全部附件材料。")
    assert build_base(orig, [over])[1] == orig[1]

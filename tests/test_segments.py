# -*- coding: utf-8 -*-
"""#30 句级改写：切句 / 拼接 / 守卫 / evidence 的单元测试。"""
from cail_race2.evidence import build_evidence, evidence_text
from cail_race2.segments import (changed_indices, is_table_or_special,
                                 locate_target_sentence, only_target_changed,
                                 splice_sentence, split_sentences)


def test_split_keeps_separators_and_roundtrips():
    t = "合同总价按单价乘数量计算。办公桌单价100元，数量20张，合同总价2200元。"
    parts = split_sentences(t)
    assert parts == ["合同总价按单价乘数量计算。", "办公桌单价100元，数量20张，合同总价2200元。"]
    assert "".join(parts) == t


def test_splice_replaces_only_target():
    t = "第一句。第二句。第三句。"
    parts = split_sentences(t)
    new = splice_sentence(parts, 1, "第二句已改。")
    assert new == "第一句。第二句已改。第三句。"


def test_only_target_changed_guard():
    orig = "第一句。第二句。第三句。"
    assert only_target_changed(orig, "第一句。第二句改。第三句。", 1) is True
    assert only_target_changed(orig, "第一句改。第二句改。第三句。", 1) is False
    assert only_target_changed(orig, "第一句。第二句。", 1) is False


def test_locate_target_sentence_by_token():
    t = "甲方付款。乙方负责将货物送至指定仓库。"
    assert locate_target_sentence(t, ["送至"]) == 1
    assert locate_target_sentence(t, ["不存在的词"]) == 0


def test_table_detection():
    assert is_table_or_special("<table><tr><td>x</td></tr></table>") is True
    assert is_table_or_special("普通条款。") is False


class _F:
    def __init__(self, kind, value, pid, slot=""):
        self.kind, self.value, self.pid, self.slot = kind, value, pid, slot


def test_build_evidence_scopes_to_pid_and_slot():
    facts = [_F("money", 2000, 5, "总价"), _F("money", 2200, 6, "金额"), _F("party", "远山公司", 1, "乙方")]
    ev = build_evidence(5, {5: "合同总价2000元。"}, facts, [], ["inconsistency"])
    assert ev["local_facts"] == [("money", "2000")]
    assert "total" not in ev["same_slot"]        # 槽位为「总价」
    assert "总价" in ev["same_slot"]
    txt = evidence_text(ev)
    assert "同槽位" in txt and "p5" in txt

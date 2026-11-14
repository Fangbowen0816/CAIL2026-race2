# -*- coding: utf-8 -*-
from cail_race2.records import LocalizationRecord, RevisionRecord
from cail_race2.revise import apply_revisions, reconcile, revise


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        return self.responses.pop(0)


PARAS = {1: "甲", 2: "乙应提共", 3: "丙"}


def test_revise_backfills_original_text_and_applies():
    client = FakeClient([{"revisions": [{"location": [[2, 2]], "error_types": ["typo"],
                                         "original_text": "模型抄错", "correct_answer": "乙应提供"}]}])
    locs = [LocalizationRecord("C1", [[2, 2]], "typo")]
    revs = revise("C1", "<p id=\"2\">乙应提共</p>", PARAS, locs, client, hints="H")
    assert revs[0].original_text == "乙应提共"      # 强制回填原文
    content = client.calls[0][-1]["content"]
    assert "<p id=\"2\">乙应提共</p>" in content and "H" in content
    final = apply_revisions(PARAS, revs)
    assert final[2] == "乙应提供" and final[1] == "甲"


def test_revise_empty_becomes_sentinel_and_no_change():
    revs = revise("C1", "ctx", PARAS, [], FakeClient([{"revisions": []}]))
    assert revs[0].location == []
    assert apply_revisions(PARAS, revs) == PARAS


def test_reconcile_overwrites_types_from_localization_union():
    locs = [LocalizationRecord("C1", [[2, 2]], "typo"),
            LocalizationRecord("C1", [[2, 2]], "inconsistency")]
    revs = [RevisionRecord("C1", [[2, 2]], ["typo"], "乙应提共", "乙应提供")]
    _, new_revs = reconcile("C1", locs, revs)
    assert new_revs[0].error_types == ["inconsistency", "typo"]


def test_reconcile_adds_localization_for_unlocalized_revision():
    revs = [RevisionRecord("C1", [[3, 3]], ["missing_element"], "丙", "丙已补")]
    locs, new_revs = reconcile("C1", [], revs)
    assert any(r.location == [[3, 3]] and r.error_type == "missing_element" for r in locs)
    assert new_revs[0].error_types == ["missing_element"]

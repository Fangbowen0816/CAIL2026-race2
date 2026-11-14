# -*- coding: utf-8 -*-
from cail_race2.detect import detect, merge_deterministic
from cail_race2.records import LocalizationRecord


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        return self.responses.pop(0)


PARAS = {1: "甲", 2: "乙", 3: "丙"}


def test_detect_parses_valid_issue():
    client = FakeClient([{"issues": [{"location": [[2, 2]], "error_type": "typo"}]}])
    recs = detect("C1", "<p id=\"2\">乙</p>", PARAS, client, hints="H")
    assert len(recs) == 1 and recs[0].location == [[2, 2]]
    # 合同原文与 hints 都应进入 user 消息
    content = client.calls[0][-1]["content"]
    assert "<p id=\"2\">乙</p>" in content and "H" in content


def test_detect_empty_becomes_sentinel():
    recs = detect("C1", "ctx", PARAS, FakeClient([{"issues": []}]))
    assert len(recs) == 1 and recs[0].location == [] and recs[0].error_type is None


def test_merge_deterministic_adds_strong_missing_and_drops_sentinel():
    merged = merge_deterministic([LocalizationRecord("C1", [], None)], "C1",
                                 {1: "交付时间另行协商。", 2: "正常条款。"})
    assert len(merged) == 1 and merged[0].location == [[1, 1]]
    assert merged[0].error_type == "missing_element"


def test_merge_deterministic_no_duplicate_for_covered_pid():
    locs = [LocalizationRecord("C1", [[1, 1]], "missing_element")]
    assert len(merge_deterministic(locs, "C1", {1: "另行协商。"})) == 1


def test_merge_adds_all_inconsistency_sides():
    paras = {1: "甲方：华辰科技有限公司；乙方：远山办公设备有限公司。",
             3: "乙方北辰办公设备有限公司应在验收完成后开具发票。"}
    locs = [LocalizationRecord("C1", [[3, 3]], "inconsistency")]  # 只报了一侧
    merged = merge_deterministic(locs, "C1", paras)
    atoms = {(r.error_type, p) for r in merged
             for s, e in (r.location or []) for p in range(s, e + 1)}
    assert ("inconsistency", 1) in atoms and ("inconsistency", 3) in atoms

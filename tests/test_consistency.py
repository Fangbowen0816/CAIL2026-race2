# -*- coding: utf-8 -*-
"""#3 不一致整组取值统一：TDD 测点。"""
from cail_race2.consistency import unify_party_conflicts, apply_party_unification
from cail_race2.facts import extract_facts
from cail_race2.records import LocalizationRecord, RevisionRecord

P1 = "甲方：华辰科技有限公司；乙方：远山办公设备有限公司。"
P3 = "乙方北辰办公设备有限公司应在验收完成后开具发票。"


def test_unify_prefers_definition_value():
    out = unify_party_conflicts({1: P1, 3: P3}, extract_facts({1: P1, 3: P3}))
    assert out == {3: "乙方远山办公设备有限公司应在验收完成后开具发票。"}


def test_no_conflict_no_change():
    same = {1: P1, 3: "乙方远山办公设备有限公司应在验收完成后开具发票。"}
    assert unify_party_conflicts(same, extract_facts(same)) == {}


def test_apply_updates_revision_text_keeping_type():
    paras = {1: P1, 3: P3}
    locs = [LocalizationRecord("C1", [[1, 1], [3, 3]], "inconsistency")]
    revs = [RevisionRecord("C1", [[3, 3]], ["inconsistency"], P3, P3)]
    _, revs2 = apply_party_unification("C1", paras, extract_facts(paras), locs, revs)
    r = [x for x in revs2 if x.location and x.location[0][0] == 3][0]
    assert r.correct_answer == "乙方远山办公设备有限公司应在验收完成后开具发票。"
    assert r.error_types == ["inconsistency"]

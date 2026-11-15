# -*- coding: utf-8 -*-
"""#17 自检/评审：定位↔修订不变量。"""
from cail_race2.critique import critique
from cail_race2.records import LocalizationRecord, RevisionRecord

P = {1: "乙方应向甲方提共办公桌20张。"}


def test_critique_passes_consistent():
    locs = [LocalizationRecord("C1", [[1, 1]], "typo")]
    revs = [RevisionRecord("C1", [[1, 1]], ["typo"], P[1], "乙方应向甲方提供办公桌20张。")]
    assert critique("C1", P, locs, revs) == []


def test_critique_flags_unlocalized_revision():
    revs = [RevisionRecord("C1", [[1, 1]], ["inconsistency"], P[1], "x")]
    kinds = {i.kind for i in critique("C1", P, [], revs)}
    assert "unlocalized_revision" in kinds and "revision_on_clean_contract" in kinds


def test_critique_flags_type_and_original_mismatch():
    locs = [LocalizationRecord("C1", [[1, 1]], "typo")]
    revs = [RevisionRecord("C1", [[1, 1]], ["inconsistency"], "错误原文", "x")]
    kinds = {i.kind for i in critique("C1", P, locs, revs)}
    assert "type_mismatch" in kinds and "original_mismatch" in kinds

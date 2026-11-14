# -*- coding: utf-8 -*-
from cail_race2.records import (LocalizationRecord, RevisionRecord, check_intervals,
                                validate_localization, validate_revision)

PARAS = {1: "甲", 2: "乙", 3: "丙"}


def test_intervals_reject_overlap_and_descending_order():
    assert check_intervals([[1, 1], [2, 2]], PARAS) == []
    assert check_intervals([[2, 2], [1, 1]], PARAS)  # 非升序
    assert check_intervals([[1, 2], [2, 3]], PARAS)  # 重叠
    assert check_intervals([[1, 1], [1, 1]], PARAS)  # 重复


def test_intervals_reject_unknown_id_and_bad_shape():
    assert any("不存在" in e for e in check_intervals([[9, 9]], PARAS))
    assert any("形状" in e for e in check_intervals([[1]], PARAS))
    assert any("起点大于终点" in e for e in check_intervals([[3, 1]], PARAS))


def test_localization_empty_location_requires_null_type():
    assert validate_localization(LocalizationRecord("C", [], None), PARAS) == []
    assert validate_localization(LocalizationRecord("C", [], "typo"), PARAS)


def test_localization_rejects_bad_error_type():
    assert validate_localization(LocalizationRecord("C", [[1, 1]], "typo"), PARAS) == []
    assert validate_localization(LocalizationRecord("C", [[1, 1]], "错别字"), PARAS)


def test_revision_original_text_must_match_source():
    ok = RevisionRecord("C", [[1, 1]], ["typo"], "甲", "甲改")
    assert validate_revision(ok, PARAS) == []
    bad = RevisionRecord("C", [[1, 1]], ["typo"], "不是原文", "甲改")
    assert any("original_text" in e for e in validate_revision(bad, PARAS))


def test_revision_rejects_tags_and_empty_answer():
    tagged = RevisionRecord("C", [[1, 1]], ["typo"], "甲", "<p id=1>甲改</p>")
    assert any("标签" in e for e in validate_revision(tagged, PARAS))
    empty = RevisionRecord("C", [[1, 1]], ["typo"], "甲", "")
    assert any("correct_answer" in e for e in validate_revision(empty, PARAS))


def test_revision_requires_single_point_and_unique_types():
    multi = RevisionRecord("C", [[1, 2]], ["typo"], "甲", "甲改")
    assert any("单点区间" in e for e in validate_revision(multi, PARAS))
    dup = RevisionRecord("C", [[1, 1]], ["typo", "typo"], "甲", "甲改")
    assert any("重复" in e for e in validate_revision(dup, PARAS))


def test_revision_sentinel_passes():
    assert validate_revision(RevisionRecord("C", [], [], None, None), PARAS) == []

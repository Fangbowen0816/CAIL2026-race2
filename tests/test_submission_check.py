# -*- coding: utf-8 -*-
"""#12 提交硬约束校验：不变量单测。"""
from cail_race2.contracts import Contract, parse_paragraphs
from cail_race2.submission_check import check

CTX = '<root><p id="1">乙方应向甲方提共办公桌20张。</p></root>'
CONTRACTS = [Contract("C1", CTX, parse_paragraphs(CTX))]

LOC_OK = (1, {"contract_id": "C1", "location": [[1, 1]], "error_type": "typo"})
REV_OK = (1, {"contract_id": "C1", "location": [[1, 1]], "error_types": ["typo"],
              "original_text": "乙方应向甲方提共办公桌20张。",
              "correct_answer": "乙方应向甲方提供办公桌20张。"})


def test_valid_submission_passes():
    assert check(CONTRACTS, [LOC_OK], [REV_OK]) == ([], [])


def test_original_text_must_match_exactly():
    bad = (1, {**REV_OK[1], "original_text": "乙方应向甲方提供办公桌20张。"})
    errs, _ = check(CONTRACTS, [LOC_OK], [bad])
    assert any("original_text" in e for e in errs)


def test_error_types_must_equal_localization_union():
    bad = (1, {**REV_OK[1], "error_types": ["inconsistency"]})
    errs, _ = check(CONTRACTS, [LOC_OK], [bad])
    assert any("error_types" in e for e in errs)


def test_duplicate_pid_revision_rejected():
    errs, _ = check(CONTRACTS, [LOC_OK], [REV_OK, (2, REV_OK[1])])
    assert any("重复修订" in e for e in errs)


def test_missing_contract_coverage_rejected():
    errs, _ = check(CONTRACTS, [], [])
    assert any("未覆盖" in e for e in errs)


def test_extra_field_rejected():
    bad = (1, {**LOC_OK[1], "extra": 1})
    errs, _ = check(CONTRACTS, [bad], [])
    assert any("字段" in e for e in errs)


def test_overlapping_intervals_rejected():
    bad = (1, {"contract_id": "C1", "location": [[1, 1], [1, 1]], "error_type": "typo"})
    errs, _ = check(CONTRACTS, [bad], [])
    assert any("升序或重叠" in e for e in errs)

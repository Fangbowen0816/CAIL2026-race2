# -*- coding: utf-8 -*-
from cail_race2.contracts import Contract, parse_paragraphs
from cail_race2.predictor import (NullPredictor, parse_localization,
                                  parse_revisions)


def _contract():
    ctx = '<p id="1">甲</p><p id="2">乙</p><p id="3">丙</p>'
    return Contract("C1", ctx, parse_paragraphs(ctx))


def test_localization_parses_valid_and_drops_bad_type():
    c = _contract()
    obj = {"issues": [
        {"location": [[1, 1]], "error_type": "typo"},
        {"location": [[2, 2]], "error_type": "错字"},   # 非法，丢弃
    ]}
    recs = parse_localization(c, obj)
    assert len(recs) == 1 and recs[0].error_type == "typo"


def test_localization_empty_becomes_sentinel():
    recs = parse_localization(_contract(), {"issues": []})
    assert len(recs) == 1 and recs[0].location == [] and recs[0].error_type is None


def test_localization_drops_overlapping_intervals():
    obj = {"issues": [{"location": [[1, 2], [2, 3]], "error_type": "typo"}]}
    recs = parse_localization(_contract(), obj)
    assert recs[0].location == []  # 全被丢弃 → 哨兵


def test_revisions_autofill_original_text_from_source():
    c = _contract()
    obj = {"revisions": [{"location": [[1, 1]], "error_types": ["typo"],
                          "original_text": "模型抄错了", "correct_answer": "甲改"}]}
    recs = parse_revisions(c, obj)
    assert recs[0].original_text == "甲" and recs[0].correct_answer == "甲改"


def test_revisions_dedupe_same_pid_and_drop_bad_location():
    obj = {"revisions": [
        {"location": [[1, 1]], "error_types": ["typo"], "correct_answer": "甲1"},
        {"location": [[1, 1]], "error_types": ["typo"], "correct_answer": "甲2"},
        {"location": [[1, 2]], "error_types": ["typo"], "correct_answer": "x"},
    ]}
    recs = parse_revisions(_contract(), obj)
    assert len(recs) == 1 and recs[0].correct_answer == "甲1"


def test_null_predictor_is_sentinel():
    locs, revs = NullPredictor().predict(_contract())
    assert locs[0].location == [] and revs[0].location == []

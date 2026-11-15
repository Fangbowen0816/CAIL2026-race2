# -*- coding: utf-8 -*-
"""#35 `stance` 全链路支持：白名单 / 校验 / 计分。"""
from cail_race2.contracts import Contract, parse_paragraphs
from cail_race2.evaluate import localization_score, official_report
from cail_race2.predictor import parse_localization
from cail_race2.records import ERROR_TYPE_SET, LocalizationRecord, validate_localization

CTX = '<p id="1">甲方应在货物交付前付清全部价款。</p>'
PARAS = parse_paragraphs(CTX)


def test_stance_in_error_types():
    assert "stance" in ERROR_TYPE_SET


def test_stance_localization_is_valid():
    rec = LocalizationRecord("C1", [[1, 1]], "stance")
    assert validate_localization(rec, PARAS) == []


def test_parse_localization_keeps_stance():
    c = Contract("C1", CTX, PARAS)
    recs = parse_localization(c, {"issues": [{"location": [[1, 1]], "error_type": "stance"}]})
    assert [r.error_type for r in recs] == ["stance"]


def test_stance_scored_and_weighted():
    gold = [{"contract_id": "C1", "location": [[1, 1]], "error_type": "stance"}]
    s = localization_score(gold, gold)
    assert s["stance"]["f1"] == 1.0
    assert s["L"] == 30.0   # stance 占位权重 30


def test_official_report_exposes_stance_fields():
    c = Contract("C1", CTX, PARAS)
    gold = {"localization": [{"contract_id": "C1", "location": [[1, 1]], "error_type": "stance"}],
            "revision": [{"contract_id": "C1", "location": [[1, 1]], "error_types": ["stance"],
                          "original_text": PARAS[1],
                          "correct_answer": "甲方应在货物交付并验收合格后5个工作日内付清全部价款。"}]}
    rep = official_report({"C1": c}, gold, gold)
    assert rep["Loc_stance"] == 100.0 and rep["Rev_stance"] == 100.0

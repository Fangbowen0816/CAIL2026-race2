# -*- coding: utf-8 -*-
from cail_race2.contracts import Contract, parse_paragraphs  # noqa: E402
from cail_race2.evaluate import (char_f_beta, edit_similarity, levenshtein,
                                 localization_score, revision_score, total_score)

import pytest


def _loc(cid, loc, et):
    return {"contract_id": cid, "location": loc, "error_type": et}


def test_localization_perfect_is_full_marks():
    gold = [_loc("C1", [[2, 2]], "typo"), _loc("C1", [[1, 1], [3, 3]], "inconsistency"),
            _loc("C1", [[4, 4]], "missing_element")]
    s = localization_score(gold, list(gold))
    assert s["L"] == 100.0
    assert s["typo"]["f1"] == 1.0 and s["inconsistency"]["f1"] == 1.0


def test_localization_empty_pred_is_zero():
    gold = [_loc("C1", [[2, 2]], "typo")]
    s = localization_score(gold, [])
    assert s["L"] == 0.0


def test_localization_cross_段_partial_credit():
    gold = [_loc("C1", [[1, 1], [3, 3]], "inconsistency")]
    pred = [_loc("C1", [[3, 3]], "inconsistency")]  # 只命中一侧
    s = localization_score(gold, pred)
    assert s["inconsistency"]["recall"] == 0.5


def test_char_f_beta_extremes():
    assert char_f_beta("乙方应向甲方提供办公桌", "乙方应向甲方提供办公桌") == 1.0
    assert char_f_beta("完全无关", "甲乙丙丁") == 0.0


def test_levenshtein_and_similarity():
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "abd") == 1
    assert edit_similarity("abc", "abd") == pytest.approx(2 / 3)


def test_revision_perfect_is_full_marks():
    ctx = ('<p id="1">乙方应向甲方提共办公桌</p>'
           '<p id="2">总价2200元</p>'
           '<p id="3">乙方负责将货物送至仓库</p>')
    contracts = {"C1": Contract("C1", ctx, parse_paragraphs(ctx))}
    gold = [
        {"contract_id": "C1", "location": [[1, 1]], "error_types": ["typo"],
         "original_text": "乙方应向甲方提共办公桌", "correct_answer": "乙方应向甲方提供办公桌"},
        {"contract_id": "C1", "location": [[2, 2]], "error_types": ["inconsistency"],
         "original_text": "总价2200元", "correct_answer": "总价2000元"},
        {"contract_id": "C1", "location": [[3, 3]], "error_types": ["missing_element"],
         "original_text": "乙方负责将货物送至仓库", "correct_answer": "乙方负责生效后10日将货物送至仓库"},
    ]
    rev = revision_score(contracts, gold, list(gold))
    assert rev["T"] == 100.0 and rev["C"] == 100.0 and rev["M"] == 100.0
    assert rev["R"] == 100.0


def test_revision_unmodified_scores_lower():
    ctx = '<p id="2">乙方应向甲方提共办公桌</p>'
    contracts = {"C1": Contract("C1", ctx, parse_paragraphs(ctx))}
    gold = [{"contract_id": "C1", "location": [[2, 2]], "error_types": ["typo"],
             "original_text": "乙方应向甲方提共办公桌",
             "correct_answer": "乙方应向甲方提供办公桌"}]
    rev = revision_score(contracts, gold, [])  # 未修改
    assert rev["T"] < 100.0


def test_total_score_average():
    assert total_score(80.0, 60.0) == 70.0

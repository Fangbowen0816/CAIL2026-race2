# -*- coding: utf-8 -*-
"""官方口径评分反推校准测试。

用两次平台实测字段验证公式：
  提交A: Loc 47.531 / Rev 8.4198 / Total 27.9754；Typo TP135/FP160/FN11 → 50.91
  提交B: Loc 45.0615 / Rev 5.6434 / Total 25.3524；Typo TP100/FP139/FN46 → 45.3721
"""
import pytest

from cail_race2.contracts import Contract, parse_paragraphs
from cail_race2.evaluate import (f_beta, official_report, total_score,
                                 char_edit_f_beta, localization_score,
                                 revision_score)
from mcp_eval.scorer import score_review, PLATFORM_FIELDS


def _f05(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 100 * f_beta(p, r, 0.5)


def test_char_f05_matches_platform():
    assert _f05(135, 160, 11) == pytest.approx(50.91, abs=0.01)   # 提交A Rev_typo
    assert _f05(100, 139, 46) == pytest.approx(45.3721, abs=0.02)  # 提交B Rev_typo


def test_total_matches_platform():
    # 提交A
    L = 0.1 * 81.08 + 0.3 * 73.39 + 0.6 * 29.01
    R = 0.1 * 50.91 + 0.3 * 10.67 + 0.6 * 0.22
    assert L == pytest.approx(47.531, abs=0.01)
    assert R == pytest.approx(8.4198, abs=0.01)
    assert total_score(L, R) == pytest.approx(27.9754, abs=0.01)
    # 提交B
    L2 = 0.1 * 77.6119 + 0.3 * 61.1765 + 0.6 * 31.5789
    R2 = 0.1 * 45.3721 + 0.3 * 1.3333 + 0.6 * 1.177
    assert L2 == pytest.approx(45.0615, abs=0.01)
    assert R2 == pytest.approx(5.6434, abs=0.01)
    assert total_score(L2, R2) == pytest.approx(25.3524, abs=0.01)


def test_char_edit_f05_isolates_edits():
    # 只改一个字：字级 F0.5 = 100
    e = char_edit_f_beta("乙方应向甲方提共办公桌", "乙方应向甲方提供办公桌",
                         "乙方应向甲方提供办公桌")
    assert e["f"] == pytest.approx(1.0) and e["fp"] == 0 and e["fn"] == 0
    # 未修改：0
    e2 = char_edit_f_beta("甲方提共", "甲方提供", "甲方提共")
    assert e2["f"] == 0.0 and e2["tp"] == 0


def test_localization_weights_and_f1():
    gold = [{"contract_id": "C1", "location": [[2, 2]], "error_type": "typo"},
            {"contract_id": "C1", "location": [[1, 1], [3, 3]], "error_type": "inconsistency"},
            {"contract_id": "C1", "location": [[4, 4]], "error_type": "missing_element"}]
    s = localization_score(gold, list(gold))
    assert s["L"] == 70.0
    # 错一个类别 → 按 1:3:6 扣分
    s2 = localization_score(gold, gold[:2])
    assert s2["missing_element"]["f1"] == 0.0 and s2["L"] == 30.0


def test_revision_progress_metric():
    ctx = '<p id="4">乙方负责将货物送至仓库</p>'
    contracts = {"C1": Contract("C1", ctx, parse_paragraphs(ctx))}
    gold = [{"contract_id": "C1", "location": [[4, 4]], "error_types": ["missing_element"],
             "original_text": "乙方负责将货物送至仓库",
             "correct_answer": "乙方负责生效后10日将货物送至仓库"}]
    perfect = revision_score(contracts, gold, list(gold))
    unmodified = revision_score(contracts, gold, [])
    assert perfect["M"] == 100.0
    assert unmodified["M"] == 0.0   # pred==orig → 完成度 0


def _full_gold_pred():
    ctx = ('<p id="1">乙方应向甲方提共办公桌</p>'
           '<p id="2">合同总价2200元</p>'
           '<p id="3">乙方负责将货物送至仓库</p>')
    contracts = {"C1": Contract("C1", ctx, parse_paragraphs(ctx))}
    loc = [{"contract_id": "C1", "location": [[1, 1]], "error_type": "typo"},
           {"contract_id": "C1", "location": [[2, 2]], "error_type": "inconsistency"},
           {"contract_id": "C1", "location": [[3, 3]], "error_type": "missing_element"}]
    rev = [{"contract_id": "C1", "location": [[1, 1]], "error_types": ["typo"],
            "original_text": "乙方应向甲方提共办公桌",
            "correct_answer": "乙方应向甲方提供办公桌"},
           {"contract_id": "C1", "location": [[2, 2]], "error_types": ["inconsistency"],
            "original_text": "合同总价2200元", "correct_answer": "合同总价2000元"},
           {"contract_id": "C1", "location": [[3, 3]], "error_types": ["missing_element"],
            "original_text": "乙方负责将货物送至仓库",
            "correct_answer": "乙方负责生效后10日将货物送至仓库"}]
    return contracts, {"localization": loc, "revision": rev}


def test_official_report_perfect_sample():
    contracts, gold = _full_gold_pred()
    rep = official_report(contracts, gold, gold)
    assert rep["Total"] == 70.0 and rep["Loc_typo"] == 100.0


def test_scorer_returns_platform_fields():
    ctx = ('<p id="1">乙方应向甲方提共办公桌</p>'
           '<p id="2">合同总价2200元</p>'
           '<p id="3">乙方负责将货物送至仓库</p>')
    _, gold = _full_gold_pred()
    out = score_review("C1", ctx, gold["localization"], gold["revision"], gold=gold)
    assert out["mode"] == "cail_gold"
    for f in PLATFORM_FIELDS:
        assert f in out["breakdown"]
    assert out["score"] == pytest.approx(70.0)

# -*- coding: utf-8 -*-
from mcp_eval.scorer import score_review

CLEAN = '<root><p id="1">甲方：甲公司。</p><p id="2">乙方：乙公司。</p></root>'


def test_self_check_clean_is_full():
    out = score_review("C1", CLEAN, [], [])
    assert out["mode"] == "self_check" and out["score"] == 100.0


def test_self_check_flags_residual_problem():
    # 总价与单价×数量不符 → 修订不改动时残余问题 > 0
    ctx = '<root><p id="5">办公桌单价100元，数量20张，合同总价2200元。</p></root>'
    loc = [{"contract_id": "C1", "location": [[5, 5]], "error_type": "inconsistency"}]
    out = score_review("C1", ctx, loc, [])
    assert out["score"] < 100.0 and out["breakdown"]["residual_problems"] >= 1

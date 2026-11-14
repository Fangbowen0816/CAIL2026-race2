# -*- coding: utf-8 -*-
"""#9 本地回归：gold-vs-gold 自检必须满分（代理评测基线）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scripts"))

from eval_samples import evaluate  # noqa: E402


def test_gold_selfcheck_is_full_marks():
    rep = evaluate()
    assert rep["Total"] == 100.0 and rep["Loc_missing"] == 100.0 and rep["Rev_missing"] == 100.0

# -*- coding: utf-8 -*-
"""提示词规格守护：关键约束必须在位（防误删）。"""
from cail_race2.prompts import _LOCATE_SYS, _REVISE_SYS


def test_locate_prompt_requires_typo_precision():
    assert "确有把握" in _LOCATE_SYS
    assert "专有名词" in _LOCATE_SYS and "脱敏" in _LOCATE_SYS


def test_locate_prompt_covers_stance():
    assert "stance" in _LOCATE_SYS and "显失公平" in _LOCATE_SYS


def test_revise_prompt_requires_minimal_typo_edit():
    assert "只改错字" in _REVISE_SYS


def test_revise_prompt_covers_stance_rebalance():
    assert "对等" in _REVISE_SYS and "stance" in _REVISE_SYS

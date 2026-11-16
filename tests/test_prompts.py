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
    # few-shot：官方口径的改法示例
    assert "验收合格后5个工作日内付清" in _REVISE_SYS
    assert "守约方**有权**" in _REVISE_SYS


def test_revise_prompt_missing_rules():
    assert "不发明数值" in _REVISE_SYS
    assert "不得只写" in _REVISE_SYS and "在本合同生效后10个工作日内" in _REVISE_SYS

# -*- coding: utf-8 -*-
"""TypoDict：词典驱动的错别字检测器。"""
from cail_race2.typo_dict import TypoDict, _is_single_cjk


def _d():
    return TypoDict([("提共", "提供"), ("提供", "提供"), ("。。", "。"),
                     ("必需", "必须"), ("不足弥补", "不足以弥补"), ("已", "以")])


def test_single_cjk_excluded():
    assert _is_single_cjk("已")
    assert not _is_single_cjk("提共")
    d = _d()
    d.find("已经完成") == []          # 单字条目被排除，不误改
    assert "已" not in {w for w, _ in d.entries}


def test_find_basic():
    hits = _d().find("乙方应向甲方提共办公桌")
    assert hits == [{"start": 6, "end": 8, "wrong": "提共", "right": "提供"}]


def test_fix_basic():
    assert _d().fix("乙方应向甲方提共办公桌") == "乙方应向甲方提供办公桌"


def test_longest_match_wins():
    d = TypoDict([("不足", "x"), ("不足弥补", "不足以弥补")])
    assert d.fix("不足弥补甲方损失") == "不足以弥补甲方损失"


def test_non_overlapping_and_repeat():
    assert _d().fix("告知。。完毕。。") == "告知。完毕。"


def test_no_change_when_clean():
    s = "本合同自双方签字之日起生效。"
    assert _d().fix(s) == s


def test_scan_paragraphs():
    d = TypoDict([("必需", "必须")])
    out = d.scan({1: "此条必需遵守", 2: "无关"})
    assert out == [{"pid": 1, "wrong": "必需", "right": "必须"}]


def test_empty_input():
    assert _d().find("") == []
    assert _d().fix("") == ""

# -*- coding: utf-8 -*-
"""#43 stance 审查：逐条款穷举 + 排除规则。"""
from cail_race2.contracts import Contract, parse_paragraphs
from cail_race2.stance_review import (parse_stance_reviews, review_stance,
                                      stance_messages, _reviewable)

CTX = ('<p id="1">甲方应在货物交付前付清全部价款，乙方无需提供相应履约保障。</p>'
       '<p id="2">双方应在验收完成后签署交接单。</p>'
       '<p id="3">第二条 交付</p>'
       '<p id="4"></p>')
PARAS = parse_paragraphs(CTX)
C = Contract("C1", CTX, PARAS)


def test_reviewable_skips_heading_and_empty():
    assert _reviewable(PARAS) == [1, 2]


def test_stance_messages_lists_each_clause():
    msgs = stance_messages(C)
    body = msgs[-1]["content"]
    assert "p1:" in body and "p2:" in body
    assert "p3:" not in body and "p4:" not in body       # 标题/空段不入清单
    assert "逐条" in msgs[0]["content"] and "stance" in msgs[0]["content"]


def test_parse_keeps_only_stance_verdicts():
    obj = {"reviews": [{"pid": 1, "verdict": "stance", "reason": "x"},
                       {"pid": 2, "verdict": "ok", "reason": "y"}]}
    assert parse_stance_reviews(C, obj) == [1]


def test_parse_excludes_placeholder_and_heading_pids():
    ctx = '<p id="1">付款时间另行协商。</p><p id="2">第二条 交付</p>'
    c = Contract("C1", ctx, parse_paragraphs(ctx))
    obj = {"reviews": [{"pid": 1, "verdict": "stance"}, {"pid": 2, "verdict": "stance"}]}
    assert parse_stance_reviews(c, obj) == []   # 缺失标记→missing；标题不报


class _Fake:
    def __init__(self, obj):
        self.obj = obj

    def complete_json(self, messages, **kw):
        return self.obj


def test_review_stance_end_to_end():
    recs = review_stance(C, _Fake({"reviews": [{"pid": 1, "verdict": "stance"}]}))
    assert [r.error_type for r in recs] == ["stance"] and recs[0].location == [[1, 1]]

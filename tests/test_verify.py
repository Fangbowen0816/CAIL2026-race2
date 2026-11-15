# -*- coding: utf-8 -*-
from cail_race2.facts import extract_facts
from cail_race2.verify import find_missing_candidates, verify


def _verify(paras):
    return verify(paras, extract_facts(paras))


def test_party_conflict_across_paragraphs():
    paras = {1: "甲方：华辰科技有限公司；乙方：远山办公设备有限公司。",
             3: "乙方北辰办公设备有限公司应在验收完成后开具发票。"}
    cs = [c for c in _verify(paras) if c.kind == "conflict"]
    assert cs and cs[0].pids == [1, 3]


def test_total_price_conflict_same_slot():
    paras = {1: "合同总价2000元。", 2: "最终合同总价2200元。"}
    cs = [c for c in _verify(paras) if c.kind == "conflict"]
    assert cs and cs[0].slot == "总价"


def test_arithmetic_mismatch_detected():
    paras = {5: "办公桌单价100元，数量20张，合同总价2200元。"}
    cs = [c for c in _verify(paras) if c.kind == "arithmetic"]
    assert cs and cs[0].pids == [5]


def test_arithmetic_ok_no_conflict():
    paras = {5: "办公桌单价100元，数量20张，合同总价2000元。"}
    assert [c for c in _verify(paras) if c.kind == "arithmetic"] == []


def test_missing_marker_detected():
    cs = [c for c in _verify({4: "交付时间另行协商。"}) if c.kind == "missing"]
    assert cs and cs[0].pids == [4]


def test_clean_paragraph_has_no_conflict():
    paras = {1: "甲方应在30日内支付合同价款。"}
    assert [c for c in _verify(paras) if c.kind in ("conflict", "arithmetic")] == []


def test_find_missing_candidates_strong_filters_weak_markers():
    paras = {1: "详见附件。", 2: "另行协商。"}
    assert [c.pids[0] for c in find_missing_candidates(paras)] == [1, 2]
    assert [c.pids[0] for c in find_missing_candidates(paras, strong=True)] == [2]


def test_verify_output_sorted_by_pid():
    paras = {5: "交付时间另行协商。", 2: "合同总价2000元。", 9: "合同总价2200元。"}
    cs = _verify(paras)
    assert [c.pids[0] for c in cs] == sorted(c.pids[0] for c in cs)


def test_placeholder_xx_detected():
    paras = {33: "乙方应于本合同签订后的【5】日（自XX年XX月XX日至XX年XX月XX日）内提供服务。"}
    cs = [c for c in _verify(paras) if c.kind == "missing"]
    assert cs and cs[0].pids == [33]


def test_placeholder_underscore_detected():
    # 脱敏/排版下划线不得误判为缺失（数据集用 XX 脱敏、下划线排版）
    assert [c for c in _verify({2: "乙方：北京XX体育文化传播有限公司。"}) if c.kind == "missing"] == []
    assert [c for c in _verify({2: "签订地点：_武汉市江汉区___。"}) if c.kind == "missing"] == []


def test_empty_field_label_detected():
    cs = [c for c in _verify({5: "履行地点："}) if c.kind == "missing"]
    assert cs and cs[0].pids == [5]


def test_clean_obligation_not_missing():
    assert [c for c in _verify({1: "乙方应在30日内支付合同价款。"}) if c.kind == "missing"] == []


def test_relative_time_clause_not_gap():
    from cail_race2.verify import find_slot_gap_candidates
    paras = {3: "乙方远山办公设备有限公司应在验收完成后开具发票。",
             7: "双方应在验收完成后签署交接单。",
             6: "甲方在验收完成后5日内支付合同总价的50%。"}
    assert find_slot_gap_candidates(paras, extract_facts(paras)) == []


def test_delivery_without_time_is_gap():
    from cail_race2.verify import find_slot_gap_candidates
    paras = {4: "乙方负责交付全部货物。"}
    gaps = find_slot_gap_candidates(paras, extract_facts(paras))
    assert gaps and gaps[0].pids == [4]


def test_stance_clue_detected():
    from cail_race2.verify import find_stance_candidates
    cs = find_stance_candidates({3: "甲方应在货物交付前付清全部价款，乙方无需提供相应履约保障。"})
    assert cs and cs[0].pids == [3]


def test_stance_clue_clean_not_flagged():
    from cail_race2.verify import find_stance_candidates
    assert find_stance_candidates({1: "双方应在验收完成后签署交接单。"}) == []

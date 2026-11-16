# -*- coding: utf-8 -*-
"""stance 滥报过滤与隐蔽形态判据。"""
from cail_race2.records import LocalizationRecord
from cail_race2.stance_review import (filter_stance_overreport, is_stance_overreport,
                                      _CHECKLIST, _STANCE_SYS)


def test_overreport_numeric_clause():
    assert is_stance_overreport("本协议年度服务费总金额为人民币70,000.00元（含税价）。")


def test_overreport_account_clause():
    assert is_stance_overreport("纳税人识别号：914201XXXXXXXXX")
    assert is_stance_overreport("开户行：XX支行 账号：6228XXXX")


def test_overreport_term_clause():
    assert is_stance_overreport("本合同自双方签字盖章之日起生效。")


def test_kept_when_asymmetry_marker_present():
    assert not is_stance_overreport("甲方可单方决定费用金额为100元。")
    assert not is_stance_overreport("乙方应无偿承担全部费用。")


def test_filter_records():
    locs = [LocalizationRecord("C", [[1, 1]], "stance"),      # 数值段 → 剔除
            LocalizationRecord("C", [[2, 2]], "stance"),      # 真失衡 → 保留
            LocalizationRecord("C", [[3, 3]], "inconsistency")]  # 非 stance → 原样
    paras = {1: "服务费总金额为70,000.00元。", 2: "乙方应无偿承担全部费用。",
             3: "甲方：AAA；乙方：BBB"}
    out = filter_stance_overreport("C", paras, locs)
    assert [(r.error_type, r.location) for r in out] == [
        ("stance", [[2, 2]]), ("inconsistency", [[3, 3]])]


def test_prompt_has_original_criteria():
    # P0-B/P1 曾尝试改 prompt（新增 F–J + 对等性），实测反而更差已回退（见 docs/召回分析.md）
    assert "A." in _CHECKLIST and "E." in _CHECKLIST
    assert "逐条" in _STANCE_SYS


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, messages, **kw):
        return self.payload


def test_cross_review_penalty_only_gate():
    from cail_race2.contracts import Contract
    from cail_race2.stance_review import review_stance_cross
    paras = {1: "甲方逾期付款的，应向乙方支付违约金。",          # 罚则类 → 保留
             2: "本合同自双方签字之日起生效。",                  # 非罚则 → 剔除
             3: "服务费总金额为人民币70,000.00元。"}             # 数值段 → 剔除
    c = Contract("C", "", paras)
    client = _FakeClient({"errors": [{"pid": 1, "reason": "罚则未量化"},
                                     {"pid": 2, "reason": "x"}, {"pid": 3, "reason": "y"}]})
    out = review_stance_cross(c, client)
    assert [r.location[0][0] for r in out] == [1]


def test_cross_review_all_kinds_when_disabled():
    from cail_race2.contracts import Contract
    from cail_race2.stance_review import review_stance_cross
    # 取非罚则、也非滥报形态的条款（避免被 is_stance_overreport 提前剔除）
    paras = {1: "乙方应无偿承担全部费用。", 2: "乙方应妥善保管甲方交付的全部设备。"}
    c = Contract("C", "", paras)
    client = _FakeClient({"errors": [{"pid": 1, "reason": "a"}, {"pid": 2, "reason": "b"}]})
    out = review_stance_cross(c, client, penalty_only=False)
    assert sorted(r.location[0][0] for r in out) == [1, 2]

# -*- coding: utf-8 -*-
from cail_race2.stage import Stage, run_stages
from cail_race2.stages import FactsStage, VerifyStage
from cail_race2.state import ContractState


def _state():
    return ContractState("C1", {1: "合同总价2000元。", 5: "交付时间另行协商。"})


def test_stages_implement_protocol():
    assert isinstance(FactsStage(), Stage)
    assert isinstance(VerifyStage(), Stage)


def test_run_stages_populates_and_bumps_version():
    st = run_stages(_state(), [FactsStage(), VerifyStage()])
    assert st.version == 2
    assert st.facts and st.conflicts
    assert any(c.kind == "missing" for c in st.conflicts)


def test_stage_does_not_mutate_input():
    src = _state()
    run_stages(src, [FactsStage(), VerifyStage()])
    assert src.facts == [] and src.conflicts == [] and src.version == 0

# -*- coding: utf-8 -*-
import json

from cail_race2.pipeline import run_staged


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        sys = messages[0]["content"] if messages else ""
        if "reviews" in sys:          # #43 stance 审查 → 默认无
            return {"reviews": []}
        if not self.responses:
            raise AssertionError("不应再调用模型（应命中缓存）")
        return self.responses.pop(0)


def _write_contracts(tmp_path):
    p = tmp_path / "contracts.jsonl"
    p.write_text(
        json.dumps({"contract_id": "C1", "context": '<p id="1">甲</p><p id="2">乙应提共</p>'},
                   ensure_ascii=False) + "\n" +
        json.dumps({"contract_id": "C2", "context": '<p id="1">丙</p>'}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return p


def test_run_staged_writes_valid_outputs(tmp_path):
    client = FakeClient([
        {"issues": [{"location": [[2, 2]], "error_type": "typo"}]},
        {"revisions": [{"location": [[2, 2]], "error_types": ["typo"],
                        "correct_answer": "乙应提供"}]},
        {"issues": []},
        {"revisions": []},
    ])
    out = tmp_path / "out"
    stats = run_staged(str(_write_contracts(tmp_path)), str(out), client)
    assert stats.contracts == 2 and stats.localizations == 2 and stats.revisions == 2

    loc = [json.loads(l) for l in (out / "localization_predictions.jsonl")
           .read_text(encoding="utf-8").splitlines()]
    rev = [json.loads(l) for l in (out / "revision_predictions.jsonl")
           .read_text(encoding="utf-8").splitlines()]
    assert loc[0] == {"contract_id": "C1", "location": [[2, 2]], "error_type": "typo"}
    assert loc[1] == {"contract_id": "C2", "location": [], "error_type": None}
    assert rev[0]["original_text"] == "乙应提共" and rev[0]["correct_answer"] == "乙应提供"


def test_run_staged_reuses_cache(tmp_path):
    cpath = _write_contracts(tmp_path)
    out = tmp_path / "out"
    run_staged(str(cpath), str(out), FakeClient([
        {"issues": []}, {"revisions": []}, {"issues": []}, {"revisions": []}]))
    # 第二次空 responses：若命中缓存则不会调用
    stats = run_staged(str(cpath), str(out), FakeClient([]))
    assert stats.contracts == 2

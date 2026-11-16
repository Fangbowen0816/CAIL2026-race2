# -*- coding: utf-8 -*-
import json
import os

import pytest

from agent.mcp_client import MCPClient, default_command

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "mcp_eval", "server.py")


@pytest.fixture
def mcp():
    c = MCPClient(default_command(SERVER))
    c.initialize()
    yield c
    c.close()


def test_tools_listed(mcp):
    names = {t["name"] for t in mcp.list_tools()}
    assert {"score_review", "submit_contract_review", "get_review_result"} <= names


def test_score_review_gold_mode(mcp):
    ex = os.path.join(ROOT, "resources", "datasets", "race2_contract_review", "提交示例")
    ctx = {json.loads(l)["contract_id"]: json.loads(l)["context"]
           for l in open(os.path.join(ex, "contracts.jsonl"), encoding="utf-8")}
    loc = [json.loads(l) for l in open(os.path.join(ex, "localization_predictions.jsonl"),
                                       encoding="utf-8")]
    rev = [json.loads(l) for l in open(os.path.join(ex, "revision_predictions.jsonl"),
                                       encoding="utf-8")]
    out = json.loads(mcp.call_tool("score_review", {
        "contract_id": "C001", "context": ctx["C001"], "localization": loc, "revision": rev}))
    assert out["mode"] == "cail_gold" and out["score"] == 70.0


def test_submit_and_get_result(mcp):
    out = json.loads(mcp.call_tool("submit_contract_review", {
        "contract_id": "X", "context": "<p id=\"1\">甲乙丙。</p>",
        "localization": [], "revision": []}))
    assert out["accepted"] is True
    res = json.loads(mcp.call_tool("get_review_result", {"task_id": out["task_id"]}))
    assert "score" in res

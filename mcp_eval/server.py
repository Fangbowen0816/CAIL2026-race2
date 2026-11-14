# -*- coding: utf-8 -*-
"""MCP 评测服务（stdio，newline-delimited JSON-RPC 2.0）。

工具：
- submit_contract_review(contract_id, context, localization, revision) -> {task_id}
- get_review_result(task_id) -> {score, breakdown, feedback}
- score_review(...)  便捷：直接返回评分
- list_rubric()      返回评分口径说明

仅 stdout 输出 JSON-RPC；日志走 stderr。
"""
from __future__ import annotations

import json
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from mcp_eval.scorer import score_review  # noqa: E402

GOLD_DIR = os.environ.get(
    "CAIL_GOLD_DIR",
    os.path.join(ROOT, "resources", "datasets", "race2_contract_review", "提交示例"))
_TASKS: dict[str, dict] = {}
_GOLD_CACHE: dict | None = None


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _as_json(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return []
    return v or []


def _gold_for(contract_id):
    global _GOLD_CACHE
    if _GOLD_CACHE is None:
        _GOLD_CACHE = {}
        for kind in ("localization", "revision"):
            p = os.path.join(GOLD_DIR, f"{kind}_predictions.jsonl")
            if os.path.exists(p):
                for line in open(p, encoding="utf-8"):
                    if line.strip():
                        o = json.loads(line)
                        _GOLD_CACHE.setdefault(o["contract_id"], {})[kind] = \
                            _GOLD_CACHE.setdefault(o["contract_id"], {}).get(kind, []) + [o]
    return _GOLD_CACHE.get(contract_id)


TOOLS = [
    {"name": "submit_contract_review",
     "description": "提交一份合同的审查结果（定位+修订），返回 task_id；随后用 get_review_result 取分。",
     "inputSchema": {"type": "object", "properties": {
         "contract_id": {"type": "string"},
         "context": {"type": "string", "description": "合同原文（含 <p id> 标签）"},
         "localization": {"type": "array", "description": "定位记录列表"},
         "revision": {"type": "array", "description": "修订记录列表"}},
         "required": ["contract_id", "context", "localization", "revision"]}},
    {"name": "get_review_result",
     "description": "按 task_id 取回评分结果。",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}},
                     "required": ["task_id"]}},
    {"name": "score_review",
     "description": "直接对审查结果评分（不排队），返回分数与反馈。",
     "inputSchema": {"type": "object", "properties": {
         "contract_id": {"type": "string"}, "context": {"type": "string"},
         "localization": {"type": "array"}, "revision": {"type": "array"}},
         "required": ["contract_id", "context", "localization", "revision"]}},
    {"name": "list_rubric",
     "description": "返回本评分服务的口径说明。",
     "inputSchema": {"type": "object", "properties": {}}},
]


def handle_tool(name, args):
    if name == "list_rubric":
        return {"rubric": "有 gold：CAIL 口径 L/R/Total（定位 1:3:6，修订 10:30:60）；"
                          "无 gold：自检分（结构合法性 + 修订后残余问题）。"}
    if name == "submit_contract_review":
        res = score_review(args["contract_id"], args["context"],
                           _as_json(args.get("localization")), _as_json(args.get("revision")),
                           gold=_gold_for(args["contract_id"]))
        task_id = "task-" + uuid.uuid4().hex[:8]
        _TASKS[task_id] = res
        return {"task_id": task_id, "accepted": True}
    if name == "get_review_result":
        return _TASKS.get(args["task_id"], {"error": "task 不存在"})
    if name == "score_review":
        return score_review(args["contract_id"], args["context"],
                            _as_json(args.get("localization")), _as_json(args.get("revision")),
                            gold=_gold_for(args["contract_id"]))
    return {"error": f"未知工具 {name}"}


def _result_text(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def main():
    _log("mcp_eval server started")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method")
        if method == "notifications/initialized":
            continue
        if "id" not in req:  # notification
            continue
        rid = req["id"]
        try:
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05",
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "cail-eval", "version": "0.1"}}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = req.get("params") or {}
                out = handle_tool(params.get("name"), params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": _result_text(out)}],
                          "isError": False}
            else:
                raise ValueError(f"未知方法 {method}")
            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32603, "message": str(e)}}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

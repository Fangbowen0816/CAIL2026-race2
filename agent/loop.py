# -*- coding: utf-8 -*-
"""Agent 循环：LLM 通过 tool_calls 调用工作区工具与 MCP 工具，直到给出最终答复。"""
from __future__ import annotations

import json

from .tools import TOOL_SCHEMAS, Workspace, dispatch


def mcp_schemas(mcp_tools: list[dict]) -> list[dict]:
    out = []
    for t in mcp_tools:
        out.append({"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
        }})
    return out


class Agent:
    def __init__(self, client, workspace: Workspace, mcp=None,
                 max_steps: int = 15, on_event=lambda e: None, extra_tools=None):
        self.client = client
        self.ws = workspace
        self.mcp = mcp
        self.max_steps = max_steps
        self.on_event = on_event
        self.tools = {"read_file": lambda **k: dispatch(self.ws, "read_file", k),
                      "write_file": lambda **k: dispatch(self.ws, "write_file", k),
                      "list_dir": lambda **k: dispatch(self.ws, "list_dir", k),
                      "run_shell": lambda **k: dispatch(self.ws, "run_shell", k)}
        self.schemas = list(TOOL_SCHEMAS)
        for name, (fn, schema) in (extra_tools or {}).items():
            self.tools[name] = fn
            self.schemas.append(schema)
        if mcp is not None:
            for t in mcp.list_tools():
                name = t["name"]
                self.tools[name] = (lambda n: lambda **k: mcp.call_tool(n, k))(name)
            self.schemas += mcp_schemas(mcp.list_tools())

    def run(self, system: str, task: str) -> dict:
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": task}]
        trace = []
        for step in range(self.max_steps):
            msg = self.client.chat_message(messages, tools=self.schemas, temperature=0)
            calls = msg.get("tool_calls") or []
            assistant = {"role": "assistant", "content": msg.get("content") or ""}
            if calls:
                assistant["tool_calls"] = calls
            messages.append(assistant)
            if not calls:
                return {"answer": msg.get("content") or "", "steps": step + 1, "trace": trace}
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                fn = self.tools.get(name)
                out = str(fn(**args)) if fn else f"[未知工具] {name}"
                trace.append({"step": step, "tool": name, "args": args,
                              "result": out[:400]})
                self.on_event({"type": "tool", "name": name, "args": args})
                messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                 "content": out[:8000]})
        return {"answer": "[达到最大步数，未完成]", "steps": self.max_steps, "trace": trace}

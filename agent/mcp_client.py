# -*- coding: utf-8 -*-
"""最小 MCP（Model Context Protocol）stdio 客户端。

协议子集：newline-delimited JSON-RPC 2.0
  initialize / notifications/initialized / tools/list / tools/call
连接器由本文件担任：拉起 server 子进程，负责通信与结果解析。
"""
from __future__ import annotations

import json
import subprocess
import sys


class MCPError(RuntimeError):
    pass


class MCPClient:
    def __init__(self, command: list[str], cwd: str | None = None, timeout: int = 120):
        self.proc = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self.timeout = timeout
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False):
        self._id += 1
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            msg["id"] = self._id
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read()[:500] if self.proc.stderr else ""
            raise MCPError(f"MCP 无响应（{method}）: {err}")
        resp = json.loads(line)
        if "error" in resp:
            raise MCPError(f"MCP error: {resp['error']}")
        return resp.get("result")

    def initialize(self) -> dict:
        result = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cail-agent", "version": "0.1"},
        })
        self._rpc("notifications/initialized", {}, notify=True)
        return result

    def list_tools(self) -> list[dict]:
        return (self._rpc("tools/list", {}) or {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        parts = []
        for c in (result or {}).get("content", []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
        text = "\n".join(parts)
        if (result or {}).get("isError"):
            return f"[MCP 工具错误] {text}"
        return text

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def default_command(server_script: str) -> list[str]:
    return [sys.executable, "-u", server_script]

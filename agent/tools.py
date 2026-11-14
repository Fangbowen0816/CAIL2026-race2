# -*- coding: utf-8 -*-
"""Agent 工具：read / write / list / shell（限定在工作区根目录内，防越界）。"""
from __future__ import annotations

import os
import subprocess


class ToolError(RuntimeError):
    pass


class Workspace:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def resolve(self, path: str) -> str:
        p = os.path.abspath(os.path.join(self.root, path or "."))
        if p != self.root and not p.startswith(self.root + os.sep):
            raise ToolError(f"路径越界（只允许工作区内）: {path}")
        return p

    def read_file(self, path: str, max_bytes: int = 200_000) -> str:
        p = self.resolve(path)
        if not os.path.isfile(p):
            raise ToolError(f"文件不存在: {path}")
        data = open(p, "rb").read(max_bytes + 1)
        if len(data) > max_bytes:
            return data[:max_bytes].decode("utf-8", "replace") + "\n...[已截断]"
        return data.decode("utf-8", "replace")

    def write_file(self, path: str, content: str) -> str:
        p = self.resolve(path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return f"已写入 {path}（{len(content)} 字符）"

    def list_dir(self, path: str = ".") -> str:
        p = self.resolve(path)
        if not os.path.isdir(p):
            raise ToolError(f"目录不存在: {path}")
        out = []
        for name in sorted(os.listdir(p)):
            full = os.path.join(p, name)
            out.append(("[DIR] " if os.path.isdir(full) else "      ") + name)
        return "\n".join(out) or "(空目录)"

    def run_shell(self, command: str, timeout: int = 300) -> str:
        try:
            r = subprocess.run(command, shell=True, cwd=self.root, timeout=timeout,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
        except subprocess.TimeoutExpired:
            return f"[超时 {timeout}s] {command}"
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return f"[exit={r.returncode}]\n" + out[:20_000]


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "读取工作区内的文本文件",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "将内容写入工作区内的文件（覆盖）",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "列出工作区内目录内容",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "run_shell", "description": "在工作区内执行 shell 命令并返回输出",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
]


def dispatch(ws: Workspace, name: str, args: dict) -> str:
    try:
        if name == "read_file":
            return ws.read_file(args["path"])
        if name == "write_file":
            return ws.write_file(args["path"], args.get("content", ""))
        if name == "list_dir":
            return ws.list_dir(args.get("path", "."))
        if name == "run_shell":
            return ws.run_shell(args["command"])
        return f"[未知工具] {name}"
    except Exception as e:  # 工具错误回喂给模型，不中断循环
        return f"[工具错误] {type(e).__name__}: {e}"

# -*- coding: utf-8 -*-
import os

import pytest

from agent.tools import ToolError, Workspace, dispatch


def test_resolve_rejects_path_escape(tmp_path):
    ws = Workspace(str(tmp_path))
    with pytest.raises(ToolError):
        ws.resolve("../outside.txt")


def test_write_read_roundtrip(tmp_path):
    ws = Workspace(str(tmp_path))
    ws.write_file("a/b.txt", "你好")
    assert ws.read_file("a/b.txt") == "你好"
    assert "b.txt" in ws.list_dir("a")


def test_dispatch_unknown_tool_returns_message(tmp_path):
    assert "未知工具" in dispatch(Workspace(str(tmp_path)), "nope", {})

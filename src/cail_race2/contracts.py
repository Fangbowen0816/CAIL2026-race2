# -*- coding: utf-8 -*-
"""合同读取与段落解析。

输入 JSONL 每行：{"contract_id": "CAIL-001", "context": "<root>\\n<p id=\"1\">…</p>…</root>"}
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

# 段落标签：<p id="N">正文</p>；正文可跨行，非贪婪匹配到最近的 </p>
_P_RE = re.compile(r'<p\s+id="(?P<pid>[^"]+)"\s*>(?P<text>.*?)</p>', re.S)


@dataclass(frozen=True)
class Contract:
    contract_id: str
    context: str
    paragraphs: dict[int, str]  # 段落编号 -> 解码后正文（不含标签）


def parse_paragraphs(context: str) -> dict[int, str]:
    """从 context 提取 {段落编号: 正文}，保持出现顺序。"""
    result: dict[int, str] = {}
    for m in _P_RE.finditer(context or ""):
        result[int(m.group("pid"))] = m.group("text")
    return result


def load_contracts(path) -> list[Contract]:
    contracts: list[Contract] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            ctx = obj["context"]
            contracts.append(Contract(obj["contract_id"], ctx, parse_paragraphs(ctx)))
    return contracts

# -*- coding: utf-8 -*-
"""提示词（占位版；具体方案确定后重写）。

两阶段：先定位（localize），带定位结果再修订（revise）。
只要求模型输出 JSON，解析在 predictor.py 中做归一化与校验。
"""
from __future__ import annotations

from .contracts import Contract

_LOCATE_SYS = """你是一名资深合同审查专家。阅读带段落编号的合同全文，找出其中的问题并定位到段落编号。

问题分三类：
- typo（错别字）：可根据上下文还原的错字、漏字、多字等文字错误。
- inconsistency（上下文不一致）：同一主体或事项的名称、金额、日期、数量、义务等表述相互冲突。
- missing_element（要素缺失）：已有条款内部缺少必要信息（如交付时间仍写“另行协商”）。

定位规则：
- 定位到段落编号粒度；一个问题涉及多段时列出全部相关 id（含冲突的每一侧）。
- 同段可有不同类型的问题，分别报告；同类型、同一组位置的多个问题合并为一条。
- 跨段连续区间才用 [s,e]；不连续用多个单点区间，严禁为连接两处而包含无关中间段。

严格只输出 JSON：{"issues": [{"location": [[s, e]], "error_type": "typo|inconsistency|missing_element"}]}
若合同没有任何问题，输出 {"issues": []}。"""


def locate_messages(contract: Contract) -> list[dict]:
    return [
        {"role": "system", "content": _LOCATE_SYS},
        {"role": "user", "content": "合同全文：\n" + contract.context},
    ]


_REVISE_SYS = """你是一名资深合同审查专家。根据合同全文与已定位的问题，修订问题条款。

修订要求：
- 只返回实际修改的段落；每段给出完整最终正文（不含 <p> 标签），一次修订解决该段所有问题。
- 错别字：纠正文字错误，保留原意。不一致：选择一个可成立的完整方案并同步所有关联位置。
- 要素缺失：按全文已知信息补齐；全文无法确定时可自行拟定合理、内部协调的约定。
- original_text 必须与原文该段逐字一致。

严格只输出 JSON：
{"revisions": [{"location": [[p, p]], "error_types": ["typo"], "original_text": "...", "correct_answer": "..."}]}
无需修改则输出 {"revisions": []}。"""


def revise_messages(contract: Contract, issues_json: str) -> list[dict]:
    return [
        {"role": "system", "content": _REVISE_SYS},
        {"role": "user", "content": "合同全文：\n" + contract.context
         + "\n\n已定位的问题：\n" + issues_json},
    ]

# -*- coding: utf-8 -*-
import json

from cail_race2.contracts import load_contracts, parse_paragraphs


def test_parse_extracts_ids_and_multiline_text():
    ctx = '<root>\n<p id="1">甲</p>\n<p id="2">乙\n丙</p>\n</root>'
    assert parse_paragraphs(ctx) == {1: "甲", 2: "乙\n丙"}


def test_parse_keeps_empty_and_ignores_non_p_tags():
    ctx = '<root><p id="1"></p>abc<p id="2">x</p><span>y</span></root>'
    assert parse_paragraphs(ctx) == {1: "", 2: "x"}


def test_parse_decodes_html_entities():
    ctx = '<p id="1">&lt;table&gt;</p><p id="2">A&amp;B</p>'
    assert parse_paragraphs(ctx) == {1: "<table>", 2: "A&B"}


def test_load_contracts_reads_all_lines(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(
        json.dumps({"contract_id": "C1", "context": '<p id="1">a</p>'}) + "\n" +
        json.dumps({"contract_id": "C2", "context": '<p id="1">b</p>'}) + "\n",
        encoding="utf-8")
    cs = load_contracts(p)
    assert [c.contract_id for c in cs] == ["C1", "C2"]
    assert cs[0].paragraphs == {1: "a"}

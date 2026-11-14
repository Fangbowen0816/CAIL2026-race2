# -*- coding: utf-8 -*-
import os

from agent.skills import SkillCatalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_catalog_lists_two_skills():
    cat = SkillCatalog(os.path.join(ROOT, "skills"))
    assert {"contract-review", "mcp-eval"} <= set(cat.names())


def test_catalog_text_and_load_body():
    cat = SkillCatalog(os.path.join(ROOT, "skills"))
    assert "contract-review" in cat.catalog_text()
    s = cat.load("contract-review")
    assert s is not None and "合同审查" in s.body

# -*- coding: utf-8 -*-
"""Skill 目录（渐进式披露）：启动只给目录摘要，任务匹配后再读全文。"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    path: str
    body: str


def _frontmatter(text: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        return meta, text[m.end():]
    return {}, text


class SkillCatalog:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self._skills: dict[str, Skill] = {}
        self._scan()

    def _scan(self):
        if not os.path.isdir(self.root):
            return
        for name in sorted(os.listdir(self.root)):
            p = os.path.join(self.root, name, "SKILL.md")
            if os.path.isfile(p):
                text = open(p, encoding="utf-8").read()
                meta, body = _frontmatter(text)
                self._skills[meta.get("name", name)] = Skill(
                    meta.get("name", name), meta.get("description", ""), p, body)

    def catalog_text(self) -> str:
        return "\n".join(f"- {s.name}: {s.description}" for s in self._skills.values())

    def load(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self):
        return list(self._skills)

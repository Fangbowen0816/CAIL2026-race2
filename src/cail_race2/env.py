# -*- coding: utf-8 -*-
"""极简 .env 加载器（避免引入 python-dotenv 依赖）。"""
from __future__ import annotations

import os


def load_dotenv(path: str = ".env") -> None:
    """把 path 中的 KEY=VALUE 注入 os.environ（不覆盖已存在变量）。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

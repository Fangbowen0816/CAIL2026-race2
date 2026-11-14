# -*- coding: utf-8 -*-
"""Agent 的 LLM provider 配置。

优先用 ksxc（金山云码）provider：base_url + 客户端识别头 + deepseek-v4.1-flash。
配置来源优先级：环境变量 → ~/.pi/agent/models.json → ~/.ksxc/auth.json。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

KSXC_BASE_URL = "https://shared.kscc.api.ksyun.com/v1"
KSXC_HEADERS = {"ksyun-code-type": "ksxc-cli"}
KSXC_MODEL = "deepseek-v4.1-flash"


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    api_key: str
    headers: dict

    def redacted(self) -> str:
        return (f"{self.name} | model={self.model} | base_url={self.base_url} | "
                f"headers={sorted(self.headers)} | api_key=***")


def _from_models_json() -> dict | None:
    path = os.path.expanduser("~/.pi/agent/models.json")
    if not os.path.exists(path):
        return None
    try:
        cfg = json.load(open(path, encoding="utf-8"))
        p = (cfg.get("providers") or {}).get("ksxc") or {}
        if p:
            return {"base_url": p.get("baseUrl"), "api_key": p.get("apiKey"),
                    "headers": p.get("headers") or {}}
    except Exception:
        return None
    return None


def _from_ksxc_auth() -> dict | None:
    path = os.path.expanduser("~/.ksxc/auth.json")
    if not os.path.exists(path):
        return None
    try:
        return {"api_key": json.load(open(path, encoding="utf-8")).get("authToken")}
    except Exception:
        return None


def load_ksxc_provider(model: str = KSXC_MODEL) -> Provider:
    base_url = os.environ.get("CAIL_BASE_URL", KSXC_BASE_URL)
    headers = dict(KSXC_HEADERS)
    key = os.environ.get("CAIL_API_KEY") or os.environ.get("KSXC_AUTH_TOKEN")

    src = _from_models_json()
    if src:
        base_url = os.environ.get("CAIL_BASE_URL", src.get("base_url") or base_url)
        if src.get("headers"):
            headers = dict(src["headers"])
        key = key or src.get("api_key")

    if not key:
        a = _from_ksxc_auth()
        key = (a or {}).get("api_key")

    if not key:
        raise RuntimeError("找不到 ksxc token：请配置 ~/.pi/agent/models.json 或 ~/.ksxc/auth.json")
    return Provider("ksxc", base_url.rstrip("/"), model, key, headers)

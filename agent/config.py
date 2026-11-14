# -*- coding: utf-8 -*-
"""Agent 的 LLM provider 配置（金山云星流 / Star Stream，OpenAI 兼容）。

配置来源优先级：环境变量（含 .env） → ~/.pi/agent/models.json(ksxc) → ~/.ksxc/auth.json。
默认端点 https://kspmas.ksyun.com/v1 ，模型 deepseek-v4.1-flash。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://kspmas.ksyun.com/v1"
DEFAULT_HEADERS: dict = {}
DEFAULT_MODEL = "deepseek-v4.1-flash"


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


def load_provider(name: str, models_json_path: str | None = None) -> Provider:
    """按名字从 models.json 读 provider（用于切换出分端点，如 ksxc）。"""
    path = models_json_path or os.path.expanduser("~/.pi/agent/models.json")
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"读取 models.json 失败: {type(e).__name__}") from e
    p = (cfg.get("providers") or {}).get(name)
    if not p:
        raise RuntimeError(f"models.json 无 provider: {name}")
    model = ((p.get("models") or [{}])[0] or {}).get("id") or DEFAULT_MODEL
    return Provider(name, (p.get("baseUrl") or "").rstrip("/"), model,
                    p.get("apiKey") or "", dict(p.get("headers") or {}))


def load_ksxc_provider(model: str | None = None) -> Provider:
    base_url = os.environ.get("CAIL_BASE_URL") or DEFAULT_BASE_URL
    headers = dict(DEFAULT_HEADERS)
    key = os.environ.get("CAIL_API_KEY") or os.environ.get("KSXC_AUTH_TOKEN")

    if os.environ.get("CAIL_HEADERS") is not None:
        try:
            headers = json.loads(os.environ["CAIL_HEADERS"] or "{}")
        except json.JSONDecodeError:
            headers = dict(DEFAULT_HEADERS)

    if not key:
        src = _from_models_json()
        if src:
            base_url = base_url or src.get("base_url")
            key = src.get("api_key")
            if os.environ.get("CAIL_HEADERS") is None and src.get("headers"):
                headers = dict(src["headers"])
    if not key:
        key = (_from_ksxc_auth() or {}).get("api_key")
    if not key:
        raise RuntimeError("找不到 API key：请配置 .env / CAIL_API_KEY，或 ~/.pi/agent/models.json")

    return Provider("starstream", base_url.rstrip("/"),
                    model or os.environ.get("CAIL_MODEL") or DEFAULT_MODEL, key, headers)

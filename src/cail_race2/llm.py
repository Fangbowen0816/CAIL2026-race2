# -*- coding: utf-8 -*-
"""OpenAI 兼容 Chat 客户端（默认指向金山云码 ksxc 网关的 deepseek-v4.1-flash）。

安全约定：
- API key 只从环境变量 / 显式参数读取，绝不写日志、绝不进 repr；
- 报错信息只含 HTTP 状态与响应正文，不含请求头。

配置（环境变量，均可被显式参数覆盖）：
- CAIL_API_KEY   必填；回退 DEEPSEEK_API_KEY / KSXC_AUTH_TOKEN
- CAIL_BASE_URL  默认 https://kspmas.ksyun.com/v1（金山云星流）
- CAIL_MODEL     默认 deepseek-v4.1-flash
- CAIL_HEADERS   额外请求头 JSON，默认空（星流不需要）
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

DEFAULT_BASE_URL = "https://kspmas.ksyun.com/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_HEADERS: dict = {}


class LLMError(RuntimeError):
    pass


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_REASONING = re.compile(r"<(think|thinking)>.*?</\1>", re.S | re.I)


def extract_json(text: str):
    """从模型输出里提取 JSON（容忍 ```json 代码块、前后噪声与 <think> 思考块）。"""
    if text is None or not text.strip():
        raise LLMError("空响应")
    t = _REASONING.sub("", text).strip()
    m = _FENCE.search(t)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
        if starts:
            start = min(starts)
            end = max(t.rfind("}"), t.rfind("]"))
            if end > start:
                try:
                    return json.loads(t[start:end + 1])
                except json.JSONDecodeError:
                    pass
        raise LLMError("无法从响应中解析 JSON")


def _env_headers() -> dict:
    raw = os.environ.get("CAIL_HEADERS")
    if not raw:
        return dict(DEFAULT_HEADERS)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else dict(DEFAULT_HEADERS)
    except json.JSONDecodeError:
        return dict(DEFAULT_HEADERS)


class LLMClient:
    def __init__(self, api_key=None, base_url=None, model=None, headers=None,
                 timeout=600, session=None, json_mode=None, seed=None):
        self.api_key = (api_key or os.environ.get("CAIL_API_KEY")
                        or os.environ.get("DEEPSEEK_API_KEY")
                        or os.environ.get("KSXC_AUTH_TOKEN"))
        if not self.api_key:
            raise LLMError("缺少 API key（请设置 CAIL_API_KEY 环境变量，勿写入代码）")
        self.base_url = (base_url or os.environ.get("CAIL_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("CAIL_MODEL") or DEFAULT_MODEL
        self.extra_headers = dict(headers) if headers is not None else _env_headers()
        if json_mode is None:
            json_mode = os.environ.get("CAIL_JSON_MODE", "1") not in ("0", "false", "False")
        self.json_mode = json_mode
        self.seed = seed if seed is not None else int(os.environ.get("CAIL_SEED", "42"))
        self.timeout = timeout
        self.session = session or requests.Session()

    def __repr__(self) -> str:  # 防止 key 随 repr 泄漏
        return (f"LLMClient(model={self.model!r}, base_url={self.base_url!r}, "
                f"headers={sorted(self.extra_headers)}, timeout={self.timeout}, api_key=***)")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                **self.extra_headers}

    def chat(self, messages, temperature=0.0, max_retries=3) -> str:
        url = self.base_url + "/chat/completions"
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "seed": self.seed}
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        last = None
        for attempt in range(max_retries):
            try:
                r = self.session.post(url, json=payload, headers=self._headers(),
                                      timeout=self.timeout)
            except requests.RequestException as e:
                last = LLMError(f"网络错误: {type(e).__name__}")
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 400 and "temperature" in r.text \
                    and payload.get("temperature") not in (1, 1.0):
                payload["temperature"] = 1.0   # 部分模型仅接受 temperature=1
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = LLMError(f"HTTP {r.status_code}（可重试）")
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
            content = r.json()["choices"][0]["message"].get("content")
            if not content:
                last = LLMError("空响应（可重试）")
                time.sleep(2 ** attempt)
                continue
            return content
        raise last or LLMError("请求失败")

    def complete_json(self, messages, **kwargs):
        return extract_json(self.chat(messages, **kwargs))

    def chat_message(self, messages, tools=None, tool_choice="auto",
                     temperature=None, max_retries=3) -> dict:
        """返回完整 assistant message（可能含 tool_calls），供 Agent 循环使用。"""
        url = self.base_url + "/chat/completions"
        payload = {"model": self.model, "messages": messages, "seed": self.seed}
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        last = None
        for attempt in range(max_retries):
            try:
                r = self.session.post(url, json=payload, headers=self._headers(),
                                      timeout=self.timeout)
            except requests.RequestException as e:
                last = LLMError(f"网络错误: {type(e).__name__}")
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = LLMError(f"HTTP {r.status_code}（可重试）")
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
            return r.json()["choices"][0]["message"]
        raise last or LLMError("请求失败")

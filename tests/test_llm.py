# -*- coding: utf-8 -*-
import pytest

from cail_race2.llm import LLMClient, LLMError, extract_json


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url, dict(json) if json else json,
                           dict(headers) if headers else headers))
        return self.responses.pop(0)


def test_extract_json_handles_fence_and_noise():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('好的，结果：{"a": 1} 完毕') == {"a": 1}
    assert extract_json('[{"x": 1}]') == [{"x": 1}]


def test_extract_json_raises_on_garbage():
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_extract_json_strips_reasoning_block():
    assert extract_json("<think>abc</think>{\"a\": 1}") == {"a": 1}
    assert extract_json("<thinking>x</thinking>{\"a\": 1}") == {"a": 1}


def test_chat_retries_with_temperature_one_on_400():
    sess = FakeSession([
        FakeResponse(400, text='{"error":{"message":"invalid temperature: only 1 is allowed for this model"}}'),
        FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]}),
    ])
    c = LLMClient(api_key="sk-x", session=sess)
    assert c.chat([{"role": "user", "content": "hi"}], temperature=0.0) == "{}"
    assert sess.calls[0][1]["temperature"] == 0.0
    assert sess.calls[1][1]["temperature"] == 1.0


def test_repr_does_not_leak_api_key():
    c = LLMClient(api_key="sk-SECRET-123")
    assert "SECRET" not in repr(c)


def test_missing_key_raises(monkeypatch):
    for k in ("CAIL_API_KEY", "DEEPSEEK_API_KEY", "KSXC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(LLMError):
        LLMClient()


def test_http_400_error_does_not_leak_key():
    sess = FakeSession([FakeResponse(400, text="bad request")])
    c = LLMClient(api_key="sk-SECRET-123", session=sess)
    with pytest.raises(LLMError) as ei:
        c.chat([{"role": "user", "content": "hi"}], max_retries=1)
    assert "SECRET" not in str(ei.value)


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("cail_race2.llm.time.sleep", lambda *_: None)
    sess = FakeSession([
        FakeResponse(429, text="rate limited"),
        FakeResponse(200, {"choices": [{"message": {"content": '{"ok": true}'}}]}),
    ])
    c = LLMClient(api_key="sk-x", session=sess)
    assert c.chat([{"role": "user", "content": "hi"}]) == '{"ok": true}'
    assert len(sess.calls) == 2


def test_extra_headers_are_sent():
    sess = FakeSession([FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]})])
    c = LLMClient(api_key="sk-x", base_url="https://gw/v1",
                  headers={"ksyun-code-type": "ksxc-cli"}, session=sess)
    c.chat([{"role": "user", "content": "hi"}])
    sent = sess.calls[0][2]
    assert sent["ksyun-code-type"] == "ksxc-cli"
    assert sent["Authorization"] == "Bearer sk-x"


def test_seed_is_sent_in_payload():
    sess = FakeSession([FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]})])
    c = LLMClient(api_key="sk-x", session=sess, seed=7)
    c.chat([{"role": "user", "content": "hi"}])
    assert sess.calls[0][1]["seed"] == 7

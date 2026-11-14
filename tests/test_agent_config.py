# -*- coding: utf-8 -*-
"""#7 Provider 选择：从 models.json 按名加载端点。"""
import json

import pytest

from agent.config import load_provider


def _models(tmp_path):
    p = tmp_path / "models.json"
    p.write_text(json.dumps({"providers": {"ksxc": {
        "baseUrl": "https://shared.kscc.api.ksyun.com/v1",
        "apiKey": "sk-secret-xyz", "headers": {"ksyun-code-type": "ksxc-cli"},
        "models": [{"id": "deepseek-v4.1-flash"}]}}}), encoding="utf-8")
    return str(p)


def test_load_provider_by_name(tmp_path):
    prov = load_provider("ksxc", _models(tmp_path))
    assert prov.base_url == "https://shared.kscc.api.ksyun.com/v1"
    assert prov.model == "deepseek-v4.1-flash"
    assert prov.headers == {"ksyun-code-type": "ksxc-cli"}


def test_provider_redacted_hides_key(tmp_path):
    prov = load_provider("ksxc", _models(tmp_path))
    assert "sk-secret-xyz" not in prov.redacted()


def test_missing_provider_raises(tmp_path):
    with pytest.raises(RuntimeError):
        load_provider("nope", _models(tmp_path))

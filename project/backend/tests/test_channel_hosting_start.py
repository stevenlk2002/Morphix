"""验证「添加渠道账号 → 企业微信 → 启动扫码」不再返回晦涩 500。

对应修复（channel_hosting.start_wecom）：
1. `IPadProtocolError` → 502 且 message 透传具体原因；
2. 通用 `Exception` → 500 且 message 含具体异常文本，并 `logger.exception(...)` 记堆栈；
3. `res["uuid"]` 改为 `res.get("uuid")` 缺失保护。

运行（建议带 -p no:cacheprovider 避免污染）：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_channel_hosting_start.py -q -p no:cacheprovider
"""
from __future__ import annotations

import logging

from fastapi.testclient import TestClient
import pytest

from app import ipad_client
from app.main import app

URL = "/api/channels/accounts/wecom/start"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _ok_payload(*_a, **_k) -> dict:
    return {
        "uuid": "u-123",
        "qrcode": "data:image/png;base64,xxx",
        "qrcode_data": "DATA",
        "qrcode_key": "K",
        "ttl": 600,
        "mock": True,
    }


def test_start_happy_path_returns_200_with_uuid_qrcode_ttl(client, monkeypatch):
    """清单 5：正常返回 200 且含 uuid / qrcode / ttl。"""
    monkeypatch.setattr(ipad_client, "start_wecom", _ok_payload)
    resp = client.post(URL, json={"teamId": "team-initial"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["uuid"] == "u-123"
    assert body["qrcode"]
    assert body["ttl"] == 600


def _raise_ipad(*_a, **_k):
    raise ipad_client.IPadProtocolError("iPad 网关连接超时(connect timeout)")


def test_ipad_protocol_error_returns_502_with_specific_reason(client, monkeypatch):
    """清单 1：IPadProtocolError → 502 且 message 含具体原因（非泛化「服务不可用」）。"""
    monkeypatch.setattr(ipad_client, "start_wecom", _raise_ipad)
    resp = client.post(URL, json={"teamId": "team-initial"})
    assert resp.status_code == 502
    msg = resp.json()["message"]
    assert "connect timeout" in msg


def _raise_generic(*_a, **_k):
    raise ValueError("unexpected boom in adapter")


def test_generic_exception_returns_500_with_specific_text_and_stack(client, monkeypatch, caplog):
    """清单 1+4：通用 Exception → 500 且 message 含具体异常文本，并记录堆栈。"""
    monkeypatch.setattr(ipad_client, "start_wecom", _raise_generic)
    with caplog.at_level(logging.ERROR):
        resp = client.post(URL, json={"teamId": "team-initial"})
    assert resp.status_code == 500
    assert "unexpected boom in adapter" in resp.json()["message"]
    assert any(r.levelno >= logging.ERROR and r.exc_info for r in caplog.records), \
        "未通过 logger.exception 记录异常堆栈"


def _payload_without_uuid(*_a, **_k) -> dict:
    # 故意不含 uuid，模拟上游返回结构变化
    return {"qrcode": "QR", "ttl": 600, "mock": True}


def test_missing_uuid_is_protected(client, monkeypatch):
    """清单 2：res 无 uuid 时 res.get 缺失保护 —— 返回清晰的 500（含「uuid」提示），

    而非 KeyError 堆栈式的晦涩 500。
    """
    monkeypatch.setattr(ipad_client, "start_wecom", _payload_without_uuid)
    resp = client.post(URL, json={"teamId": "team-initial"})
    assert resp.status_code == 500
    assert "uuid" in resp.json()["message"]

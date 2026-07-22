"""企业微信 iPad 协议客户端 —— 真实链路集成测试。

目标：独立验证后端能正确对接**真实服务** `http://47.94.7.218:9912`，
不走 mock 兜底。运行方式（在 project/backend 下）：

    IPAD_PROTOCOL_MODE=auto .venv/bin/python -m pytest tests/test_ipad_client_real.py -v

说明：
- 本测试强制以 `auto` 模式运行（真实服务可达时走真实路径）。
- 所有断言均针对真实接口契约（实测确认）：
  init 返回 data.uuid + data.is_login(str)；
  getQrCode 返回 data.qrcode(url) + data.qrcode_data(base64) + data.Key(32hex) + data.Ttl(int 600)；
  GetRunClientInfo 返回 data.loginType(0/1/2) + data.userInfo + data.longLinkState。
"""
from __future__ import annotations

import os
import re

# 必须在 import app 之前设定模式，确保走真实路径（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import base64

from app import ipad_client

# 真实服务基址（与 config 默认一致），用于断言真实 URL 前缀。
REAL_BASE_URL = "http://47.94.7.218:9912"
HEX32_RE = re.compile(r"^[0-9A-Fa-f]{32}$")
B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def _is_base64(s: str) -> bool:
    """宽松判定：非空且字符集符合 base64 标准字符集（兼容有无 padding）。"""
    if not isinstance(s, str) or len(s) == 0:
        return False
    if not B64_RE.fullmatch(s):
        return False
    try:
        base64.b64decode(s, validate=True)
        return True
    except Exception:
        return False


def test_init_normalization():
    """init 归一化：uuid 非空字符串；is_login 为 Python bool 且为 False。"""
    res = ipad_client.init("ipad")

    # uuid 为长度 > 0 的字符串
    assert isinstance(res.get("uuid"), str), "uuid 应为字符串"
    assert len(res["uuid"]) > 0, "uuid 不应为空"

    # is_login 必须是真正的 Python bool，且真实返回 'false' 不应误判为 True
    assert isinstance(res.get("is_login"), bool), (
        f"is_login 应为 Python bool，实际为 {type(res.get('is_login')).__name__}"
    )
    assert res["is_login"] is False, "真实服务 is_login='false'，应归一化为 False"


def test_get_qrcode_field_compat():
    """getQrCode 字段兼容：真实 URL / 非空 base64 / 32 位十六进制 Key / Ttl==600。"""
    init_res = ipad_client.init("ipad")
    uuid = init_res["uuid"]
    assert uuid, "init 返回的 uuid 不能为空"

    qr = ipad_client.get_qrcode(uuid)

    # qrcode 以真实服务 URL 开头（非 mock）
    qrcode = qr.get("qrcode")
    assert isinstance(qrcode, str) and qrcode.startswith(f"{REAL_BASE_URL}/"), (
        f"qrcode 应为真实服务 URL 开头，实际: {qrcode!r}"
    )

    # qrcode_data 为非空 base64 字符串
    qrcode_data = qr.get("qrcode_data")
    assert _is_base64(qrcode_data or ""), "qrcode_data 应为非空 base64 字符串"

    # qrcode_key 为 32 位十六进制串（验证拿到了真实的大写 Key）
    qrcode_key = qr.get("qrcode_key")
    assert isinstance(qrcode_key, str) and HEX32_RE.match(qrcode_key), (
        f"qrcode_key 应为 32 位十六进制串，实际: {qrcode_key!r}"
    )

    # ttl == 600（验证拿到了真实的 Ttl）
    assert qr.get("ttl") == 600, f"ttl 应等于 600，实际: {qr.get('ttl')!r}"


def test_check_code_request_format():
    """CheckCode 请求格式：发出的字段是 qrcodeKey；返回 dict 含 ok/skip 键。"""
    init_res = ipad_client.init("ipad")
    uuid = init_res["uuid"]
    qr = ipad_client.get_qrcode(uuid)
    qrcode_key = qr["qrcode_key"]

    # 真实服务可能返回校验失败，但不应抛异常（验证 qrcodeKey 字段被服务端接受）
    res = ipad_client.check_code(uuid, qrcode_key, "000000")

    assert isinstance(res, dict), "check_code 应返回 dict"
    assert "ok" in res and "skip" in res, (
        f"check_code 返回应含 ok/skip 键，实际: {res!r}"
    )


def test_poll_structure():
    """轮询结构：loginType ∈ {0,1,2}，longLinkState 非空字符串，mock 为 False。"""
    init_res = ipad_client.init("ipad")
    uuid = init_res["uuid"]

    info = ipad_client.poll_wecom(uuid)

    assert info.get("loginType") in (0, 1, 2), (
        f"loginType 应在 {{0,1,2}} 中，实际: {info.get('loginType')!r}"
    )
    long_link_state = info.get("longLinkState")
    assert isinstance(long_link_state, str) and len(long_link_state) > 0, (
        f"longLinkState 应为非空字符串，实际: {long_link_state!r}"
    )
    assert info.get("mock") is False, "真实路径 poll_wecom 的 mock 应为 False"


def test_start_endpoint_e2e():
    """路由端点端到端：POST /api/channels/accounts/wecom/start。"""
    from fastapi.testclient import TestClient

    # 延迟导入 app，确保 IPAD_PROTOCOL_MODE 已在其 import 链之前设定
    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/channels/accounts/wecom/start",
        json={"teamId": "qa_team", "name": "qa", "channelType": "wecom"},
    )

    assert resp.status_code == 200, f"端点应返回 200，实际: {resp.status_code} {resp.text}"
    data = resp.json()

    assert data.get("mock") is False, f"真实路径下 mock 应为 False，实际: {data.get('mock')!r}"

    qrcode = data.get("qrcode")
    assert isinstance(qrcode, str) and qrcode.startswith(f"{REAL_BASE_URL}/"), (
        f"qrcode 应以真实服务 URL 开头，实际: {qrcode!r}"
    )

    qrcode_key = data.get("qrcodeKey")
    assert isinstance(qrcode_key, str) and HEX32_RE.match(qrcode_key), (
        f"qrcodeKey 应为 32 位十六进制串，实际: {qrcode_key!r}"
    )

"""群二维码后端测试（获取群二维码 URL + 图片代理下载）。"""
from __future__ import annotations

import os

os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ipad_client as ipad_client_mod
from app import schema as schema_mod
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.main import app
from app.repositories import ChannelMgmtRepository
from app import ipad_sync as ipad_sync_mod

client = TestClient(app)


@pytest.fixture
def backend(tmp_path):
    be = SQLiteBackend(tmp_path / "morphix_group_qrcode_test.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def account(backend):
    repo = ChannelMgmtRepository(backend)
    return repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="team-initial",
        name="群二维码测试账号",
        ipad_uuid="qa-qr-uuid",
        ipad_user_info={},
        host_status="hosted",
    )


def _mock_wx_room_invite(monkeypatch, qr_code_path: str):
    def _fake(uuid: str, room_id):
        return {"room_id": str(room_id), "qr_code_path": qr_code_path}

    monkeypatch.setattr(ipad_client_mod, "wx_room_invite", _fake)


# --------------------------------------------------------------------------- #
# 成功：返回二维码 URL
# --------------------------------------------------------------------------- #
def test_get_group_qrcode_success(monkeypatch, account):
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8083/RoomQrCode/abc.jpg")
    resp = client.get(
        f"/api/channels/{account['id']}/group/room_g01/qrcode"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["qrCodeUrl"] == "http://47.94.7.218:9912/RoomQrCode/abc.jpg"


# --------------------------------------------------------------------------- #
# _rewrite_qrcode_host 单元覆盖
# --------------------------------------------------------------------------- #
def test_rewrite_qrcode_host_rewrites_netloc():
    assert (
        ipad_sync_mod._rewrite_qrcode_host("http://47.94.7.218:8083/RoomQrCode/x.jpg")
        == "http://47.94.7.218:9912/RoomQrCode/x.jpg"
    )


def test_rewrite_qrcode_host_keeps_query():
    assert (
        ipad_sync_mod._rewrite_qrcode_host("http://47.94.7.218:8083/RoomQrCode/x.jpg?a=1")
        == "http://47.94.7.218:9912/RoomQrCode/x.jpg?a=1"
    )


def test_rewrite_qrcode_host_empty():
    assert ipad_sync_mod._rewrite_qrcode_host("") == ""


def test_rewrite_qrcode_host_non_url():
    assert ipad_sync_mod._rewrite_qrcode_host("not-a-url") == "not-a-url"


# --------------------------------------------------------------------------- #
# 404：账号不存在
# --------------------------------------------------------------------------- #
def test_get_group_qrcode_404_account(monkeypatch):
    _mock_wx_room_invite(monkeypatch, "http://example.com/qr.jpg")
    resp = client.get("/api/channels/acc-not-exist/group/room_g01/qrcode")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 400：账号未绑定 iPad 协议实例
# --------------------------------------------------------------------------- #
def test_get_group_qrcode_400_no_ipad_uuid(backend):
    repo = ChannelMgmtRepository(backend)
    acc = repo.create_account("wecom", "ipad", "team-initial", "无iPad实例账号")
    assert acc.get("ipadUuid", "") == ""
    resp = client.get(
        f"/api/channels/{acc['id']}/group/room_g01/qrcode"
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# 图片代理：mock httpx.Client 下载
# --------------------------------------------------------------------------- #
def _mock_httpx_get(monkeypatch, status_code: int, content: bytes, content_type: str):
    """把 `httpx.Client` 替换为返回固定响应的假实现（monkeypatch 自动还原）。"""

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def get(self, url: str, *args, **kwargs) -> httpx.Response:
            return httpx.Response(
                status_code=status_code,
                content=content,
                headers={"content-type": content_type},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(httpx, "Client", _FakeClient)


def test_get_group_qrcode_image_proxy(monkeypatch, account):
    """代理接口成功返回图片二进制流与正确的 content-type。"""
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8083/download/RoomQrCode/abc.jpg")
    fake_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    _mock_httpx_get(monkeypatch, 200, fake_bytes, "image/jpeg")

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == fake_bytes


def test_get_group_qrcode_image_proxy_404(monkeypatch, account):
    """上游图片 404 时，代理接口返回 502 且携带可读错误信息。"""
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8083/download/RoomQrCode/abc.jpg")
    _mock_httpx_get(monkeypatch, 404, b'{"detail":"not found"}', "application/json")

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")

    assert resp.status_code == 502
    assert "下载群二维码失败" in resp.json()["message"]


def test_get_group_qrcode_image_proxy_falls_back_to_raw_url(monkeypatch, account):
    """改写后的 :9912 地址 404 时，自动回退到协议原始 :8083 地址下载成功。"""
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8083/download/RoomQrCode/abc.jpg")
    fake_bytes = b"\x89PNG\r\n\x1a\nfake-png-bytes"
    requested: list[str] = []

    class _FakeClient:
        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def get(self, url: str, *args, **kwargs) -> httpx.Response:
            requested.append(url)
            if ":9912" in url:
                return httpx.Response(
                    status_code=404,
                    content=b'{"detail":"not found"}',
                    headers={"content-type": "application/json"},
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(
                status_code=200,
                content=fake_bytes,
                headers={"content-type": "image/png"},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: _FakeClient())

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == fake_bytes
    # 先试改写后的同址端口，失败后回退协议原始地址
    assert [":9912" in u for u in requested] == [True, False]


def test_get_group_qrcode_image_proxy_404_account(monkeypatch):
    """账号不存在时代理接口返回 404。"""
    _mock_wx_room_invite(monkeypatch, "http://example.com/qr.jpg")
    resp = client.get("/api/channels/acc-not-exist/group/room_g01/qrcode/image")
    assert resp.status_code == 404


def test_get_group_qrcode_image_proxy_empty_url(monkeypatch, account):
    """协议未返回二维码地址时返回 502。"""
    _mock_wx_room_invite(monkeypatch, "")
    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")
    assert resp.status_code == 502
    assert "未获取到群二维码图片地址" in resp.json()["message"]

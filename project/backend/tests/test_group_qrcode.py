"""群二维码后端测试（获取群二维码 URL + 图片代理下载）。

修复后行为（2026-08-01 根因修复）：
- 不再对 QrCodePath 做 host/port 改写（旧代码将 :8083/:8060 改写为 :9912 导致 404）
- 直接使用协议返回的原始 URL 下载图片（协议静态文件服务 :8060 从后端可达）
- httpx 显式禁用代理（trust_env=False），防止 launchd 环境变量注入导致请求被拦截
- Content-Type 基于文件头魔数嗅探（协议服务器声称 JPEG 实际返回 PNG）

QA 回归后补充（缺陷 #1 越权修复）：
- 二维码链路新增群归属校验（`_resolve_group`），因此所有用例的 room_id
  必须真实存在于 `channel_groups`，否则一律 404「群不存在」。
"""
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


def _create_group(backend, account_id: str, room_id: str = "room_g01") -> str:
    """在 `channel_groups` 落一条属于 `account_id` 的群记录。

    群归属校验（`_resolve_group`）前置后，二维码链路要求群必须真实存在，
    因此测试必须显式建群，否则会在进入协议调用前被 404 拦截。
    """
    repo = ChannelMgmtRepository(backend)
    gid = f"{account_id}:{room_id}"
    repo.upsert_channel_group(
        {
            "id": gid,
            "account_id": account_id,
            "room_id": room_id,
            "group_type": "customer_group",
            "nickname": "二维码测试群",
            "total": 3,
            "room_url": "",
            "notice_content": "",
            "create_time": "2026-08-01T00:00:00Z",
            "update_time": "2026-08-01T00:00:00Z",
            "extra_json": "{}",
        }
    )
    return room_id


@pytest.fixture
def account(backend):
    repo = ChannelMgmtRepository(backend)
    acc = repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="team-initial",
        name="群二维码测试账号",
        ipad_uuid="qa-qr-uuid",
        ipad_user_info={},
        host_status="hosted",
    )
    _create_group(backend, acc["id"], "room_g01")
    return acc


def _mock_wx_room_invite(monkeypatch, qr_code_path: str, image_url: str = ""):
    """Mock wx_room_invite 返回指定字段。"""

    def _fake(uuid: str, room_id):
        return {
            "room_id": str(room_id),
            "qr_code_path": qr_code_path,
            "image_url": image_url,
        }

    monkeypatch.setattr(ipad_client_mod, "wx_room_invite", _fake)


# --------------------------------------------------------------------------- #
# 成功：返回二维码 URL（透传协议原始 URL，不做改写）
# --------------------------------------------------------------------------- #
def test_get_group_qrcode_success(monkeypatch, account):
    # 协议返回的 URL 直接透传，不再做 host/port 改写
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8060/download/RoomQrCode/abc.jpg")
    resp = client.get(
        f"/api/channels/{account['id']}/group/room_g01/qrcode"
    )
    assert resp.status_code == 200
    data = resp.json()
    # 直接返回协议原始 URL，不改写端口
    assert data["qrCodeUrl"] == "http://47.94.7.218:8060/download/RoomQrCode/abc.jpg"


# --------------------------------------------------------------------------- #
# Content-Type 嗅探：基于魔数而非上游响应头
# --------------------------------------------------------------------------- #
def test_sniff_content_type_png():
    """PNG 魔数 (89 50 4E 47) → image/png。"""
    png_header = b"\x89PNG\r\n\x1a\n" + b"fake-png-data"
    assert ipad_sync_mod._sniff_content_type(png_header) == "image/png"


def test_sniff_content_type_jpeg():
    """JPEG 魔数 (FF D8 FF E0) → image/jpeg。"""
    jpeg_header = b"\xff\xd8\xff\xe0" + b"fake-jpeg-data"
    assert ipad_sync_mod._sniff_content_type(jpeg_header) == "image/jpeg"


def test_sniff_content_type_fallback():
    """未知格式 → 默认 image/jpeg。"""
    assert ipad_sync_mod._sniff_content_type(b"\x00\x01\x02\x03") == "image/jpeg"


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
    # 群必须存在，否则会先被归属校验拦成 404，测不到「未绑定实例」这条分支
    _create_group(backend, acc["id"], "room_g01")
    resp = client.get(
        f"/api/channels/{acc['id']}/group/room_g01/qrcode"
    )
    assert resp.status_code == 400
    assert "未绑定" in resp.json()["message"]


# --------------------------------------------------------------------------- #
# 图片代理：mock httpx.Client 下载（单候选地址，无改写）
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
    """代理接口成功返回图片二进制流与正确的 content-type（基于魔数嗅探）。"""
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8060/download/RoomQrCode/abc.jpg")
    fake_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    _mock_httpx_get(monkeypatch, 200, fake_bytes, "image/jpeg")

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")

    assert resp.status_code == 200
    # Content-Type 由魔数嗅探决定（JPEG 头 → image/jpeg）
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == fake_bytes


def test_get_group_qrcode_image_proxy_png_sniffing(monkeypatch, account):
    """上游声称 JPEG 但实际是 PNG 时，嗅探应正确识别为 image/png。"""
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8060/download/RoomQrCode/abc.jpg")
    fake_bytes = b"\x89PNG\r\n\x1a\nfake-png-bytes"
    # 上游响应头声称 JPEG（这是协议服务器的真实行为）
    _mock_httpx_get(monkeypatch, 200, fake_bytes, "image/jpeg")

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")

    assert resp.status_code == 200
    # 应被嗅探为 PNG 而非信任上游的 JPEG 声称
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == fake_bytes


def test_get_group_qrcode_image_proxy_404(monkeypatch, account):
    """上游图片 404 时，代理接口返回 502 且携带可读错误信息。"""
    _mock_wx_room_invite(monkeypatch, "http://47.94.7.218:8060/download/RoomQrCode/abc.jpg")
    _mock_httpx_get(monkeypatch, 404, b'{"detail":"not found"}', "application/json")

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")

    assert resp.status_code == 502
    assert "下载群二维码失败" in resp.json()["message"]


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


# --------------------------------------------------------------------------- #
# 验证：不再有 host/port 改写逻辑
# --------------------------------------------------------------------------- #
def test_no_rewrite_behavior(monkeypatch, account):
    """确认不再做 host/port 改写——协议返回什么就返回什么。"""
    original_url = "http://192.168.1.100:9999/static/qr.png"
    _mock_wx_room_invite(monkeypatch, original_url)

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode")
    assert resp.status_code == 200
    assert resp.json()["qrCodeUrl"] == original_url


# --------------------------------------------------------------------------- #
# 缺陷 #1：群归属校验（越权取图）
# --------------------------------------------------------------------------- #
def test_get_group_qrcode_404_group_not_owned(monkeypatch, account):
    """请求不属于本账号（或压根不存在）的 room_id → 404，且不得调用协议。"""
    calls: list[str] = []

    def _spy(uuid: str, room_id):
        calls.append(str(room_id))
        return {"room_id": str(room_id), "qr_code_path": "http://leak/other.jpg", "image_url": ""}

    monkeypatch.setattr(ipad_client_mod, "wx_room_invite", _spy)

    resp = client.get(f"/api/channels/{account['id']}/group/999999999999999/qrcode")
    assert resp.status_code == 404
    assert "群不存在" in resp.json()["message"]
    assert calls == [], f"协议不应被调用，实际={calls}"


def test_get_group_qrcode_image_404_illegal_room_id(monkeypatch, account):
    """非法 room_id（会被 `_to_int_id` 静默降级为 0）必须被拦截且不回传任何字节。"""
    calls: list[str] = []

    def _spy(uuid: str, room_id):
        calls.append(str(room_id))
        return {"room_id": "0", "qr_code_path": "http://leak/other.jpg", "image_url": ""}

    monkeypatch.setattr(ipad_client_mod, "wx_room_invite", _spy)
    _mock_httpx_get(monkeypatch, 200, b"\x89PNG\r\n\x1a\nleaked", "image/png")

    resp = client.get(
        f"/api/channels/{account['id']}/group/abc-not-a-number/qrcode/image"
    )
    assert resp.status_code == 404
    assert calls == [], f"协议不应被调用，实际={calls}"
    # 关键：一个图片字节都不能泄漏
    assert b"\x89PNG" not in resp.content


def test_resolve_qrcode_urls_enforces_ownership(backend, monkeypatch, account):
    """同步层自身也必须拦截（防御纵深，不依赖路由层是否校验）。"""
    _mock_wx_room_invite(monkeypatch, "http://x/qr.jpg")
    with pytest.raises(ipad_sync_mod.IPadSyncError) as ei:
        ipad_sync_mod._resolve_qrcode_urls(account["id"], "abc-not-a-number")
    assert "群不存在" in str(ei.value)


# --------------------------------------------------------------------------- #
# 缺陷 #2：协议异常不得穿透成 HTTP 500
# --------------------------------------------------------------------------- #
def test_protocol_error_maps_to_502_not_500(monkeypatch, account):
    """`IPadProtocolError`（RuntimeError 子类）必须被转成 IPadSyncError → 502。"""

    def _boom(uuid: str, room_id):
        raise ipad_client_mod.IPadProtocolError(
            "iPad 协议业务错误 errcode=500: 实例未登录"
        )

    monkeypatch.setattr(ipad_client_mod, "wx_room_invite", _boom)

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode/image")
    assert resp.status_code == 502
    assert "WxRoomInvite" in resp.json()["message"]


def test_protocol_error_maps_to_400_on_url_endpoint(monkeypatch, account):
    """URL 端点同理：协议异常 → 400 可读错误，不得 500 崩栈。"""

    def _boom(uuid: str, room_id):
        raise ipad_client_mod.IPadProtocolError("connection refused")

    monkeypatch.setattr(ipad_client_mod, "wx_room_invite", _boom)

    resp = client.get(f"/api/channels/{account['id']}/group/room_g01/qrcode")
    assert resp.status_code == 400
    assert "WxRoomInvite" in resp.json()["message"]


# --------------------------------------------------------------------------- #
# 缺陷 #3：WebP 容器识别
# --------------------------------------------------------------------------- #
def test_sniff_content_type_webp():
    """WebP 是 RIFF 容器（RIFF....WEBP），不得被误判为 image/gif。"""
    webp = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"VP8 " + b"\x00" * 16
    assert ipad_sync_mod._sniff_content_type(webp) == "image/webp"


def test_sniff_content_type_gif():
    """GIF 仍应正确识别为 image/gif（不被 WebP 分支误吞）。"""
    assert ipad_sync_mod._sniff_content_type(b"GIF89a" + b"\x00" * 16) == "image/gif"

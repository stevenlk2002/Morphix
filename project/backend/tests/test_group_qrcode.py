"""群二维码后端测试（获取群二维码 URL）。"""
from __future__ import annotations

import os

os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest
from fastapi.testclient import TestClient

from app import ipad_client as ipad_client_mod
from app import schema as schema_mod
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.main import app
from app.repositories import ChannelMgmtRepository

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
    _mock_wx_room_invite(monkeypatch, "http://example.com/qr.jpg")
    resp = client.get(
        f"/api/channels/{account['id']}/group/room_g01/qrcode"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["qrCodeUrl"] == "http://example.com/qr.jpg"


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

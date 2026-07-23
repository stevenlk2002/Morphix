"""右侧合并区域 · 群管理后端测试（T04）。"""
from __future__ import annotations

import os

os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest
from fastapi.testclient import TestClient

from app import schema as schema_mod
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.main import app
from app.repositories import ChannelMgmtRepository

client = TestClient(app)


@pytest.fixture
def backend(tmp_path):
    be = SQLiteBackend(tmp_path / "morphix_group_mgmt_test.db")
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
        name="群管理测试账号",
        ipad_uuid="qa-group-uuid",
        ipad_user_info={},
        host_status="hosted",
    )


@pytest.fixture
def contact(backend, account):
    repo = ChannelMgmtRepository(backend)
    cid = f"{account['id']}:wxid_g01"
    repo.upsert_channel_contact({
        "id": cid, "account_id": account["id"],
        "channel": "企业微信", "channel_type": "wecom",
        "name": "群成员1", "nickname": "群成员1",
        "type": "customer", "status": "online",
        "remark": "", "description": "", "add_time": "", "source": "",
        "user_id": "wxid_g01", "label_ids": "[]", "raw_status": "", "extra_json": "{}",
    })
    return {"id": cid, "user_id": "wxid_g01"}


@pytest.fixture
def group(backend, account):
    repo = ChannelMgmtRepository(backend)
    repo.upsert_channel_group({
        "id": f"{account['id']}:room_g01",
        "account_id": account["id"],
        "room_id": "room_g01",
        "group_type": "customer_group",
        "nickname": "测试群",
        "total": 0,
        "room_url": "", "notice_content": "",
        "create_time": "", "update_time": "",
        "extra_json": "{}",
    })
    return {"id": f"{account['id']}:room_g01", "room_id": "room_g01"}


# --------------------------------------------------------------------------- #
# 群成员管理
# --------------------------------------------------------------------------- #
def test_add_group_members_success(account, contact, group):
    resp = client.post(
        f"/api/channels/{account['id']}/group/{group['room_id']}/members",
        json={"contactIds": [contact["id"]]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["added"] == 1
    assert data["total"] == 1


def test_add_group_members_404_account():
    resp = client.post(
        "/api/channels/acc-not-exist/group/room_g01/members",
        json={"contactIds": ["c1"]},
    )
    assert resp.status_code == 404


def test_add_group_members_400_empty(account, group):
    resp = client.post(
        f"/api/channels/{account['id']}/group/{group['room_id']}/members",
        json={"contactIds": []},
    )
    assert resp.status_code == 400


def test_add_group_members_400_unknown_group(account):
    resp = client.post(
        f"/api/channels/{account['id']}/group/room-not-exist/members",
        json={"contactIds": ["c1"]},
    )
    assert resp.status_code == 400


def test_remove_group_member_success(backend, account, contact, group):
    # 先添加
    client.post(
        f"/api/channels/{account['id']}/group/{group['room_id']}/members",
        json={"contactIds": [contact["id"]]},
    )
    # 再移除（按 contactId 传）
    resp = client.delete(
        f"/api/channels/{account['id']}/group/{group['room_id']}/members/{contact['id']}"
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] >= 1
    assert resp.json()["total"] == 0


# --------------------------------------------------------------------------- #
# 群公告
# --------------------------------------------------------------------------- #
def test_set_group_notice(account, group):
    resp = client.put(
        f"/api/channels/{account['id']}/group/{group['room_id']}/notice",
        json={"notice": "新版群公告"},
    )
    assert resp.status_code == 200
    assert resp.json()["noticeContent"] == "新版群公告"


# --------------------------------------------------------------------------- #
# 转让群主
# --------------------------------------------------------------------------- #
def test_transfer_group_owner(account, group):
    resp = client.post(
        f"/api/channels/{account['id']}/group/{group['room_id']}/transfer",
        json={"newOwnerUserId": "wxid_g01"},
    )
    assert resp.status_code == 200
    assert resp.json()["ownerUserId"] == "wxid_g01"


# --------------------------------------------------------------------------- #
# 解散群
# --------------------------------------------------------------------------- #
def test_dismiss_group(account, group):
    resp = client.delete(
        f"/api/channels/{account['id']}/group/{group['room_id']}"
    )
    assert resp.status_code == 200
    assert resp.json()["dismissed"] is True

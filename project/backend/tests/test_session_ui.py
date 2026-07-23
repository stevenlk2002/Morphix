"""渠道会话管理页 UI 改造 —— 后端专项测试。

覆盖本期新增后端端点：
- POST /api/channels/{account_id}/groups（建群，mock-first）
- POST /api/channels/{account_id}/sessions/read-local（一键已读本地）

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_session_ui.py -v
"""
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
    """隔离的临时 SQLite 库，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_session_ui_test.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def account(backend):
    """注入一个已托管 iPad 的测试账号。"""
    repo = ChannelMgmtRepository(backend)
    return repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="team-initial",
        name="UI测试账号",
        ipad_uuid="ui-test-uuid",
        ipad_user_info={},
        host_status="hosted",
    )


@pytest.fixture
def contact(backend, account):
    """注入一个含 user_id 的测试联系人。"""
    repo = ChannelMgmtRepository(backend)
    cid = f"{account['id']}:wxid_qa01"
    repo.upsert_channel_contact(
        {
            "id": cid,
            "account_id": account["id"],
            "channel": "企业微信",
            "channel_type": "wecom",
            "name": "QA好友",
            "nickname": "QA好友",
            "type": "customer",
            "status": "online",
            "remark": "",
            "description": "",
            "add_time": "",
            "source": "",
            "user_id": "wxid_qa01",
            "label_ids": "[]",
            "raw_status": "",
            "extra_json": "{}",
        }
    )
    return {"id": cid, "user_id": "wxid_qa01"}


@pytest.fixture
def unread_session(backend, account):
    """注入一条含未读的会话。"""
    sid = f"{account['id']}:sess_unread"
    backend.execute(
        "INSERT INTO channel_sessions("
        "id, account_id, contact_id, name, channel, channel_type, last_message, "
        "last_time, unread_count, read_status, hosted_status, hosted_bot_id, owner, "
        "online_status, session_type, external_tag, add_time, hosting_chain, "
        "remote_session_id, msg_type, begin_msg_seq) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sid, account["id"], None, "未读会话", "企业微信", "wecom",
            "", "", 5, "unread", "unhosted", None, "",
            "online", "外部联系人", "外部", "", "-",
            "sess_unread", 0, "",
        ),
    )
    return {"id": sid}


# --------------------------------------------------------------------------- #
# 建群接口
# --------------------------------------------------------------------------- #
def test_create_group_404_unknown_account():
    resp = client.post(
        "/api/channels/acc-not-exist/groups",
        json={"memberIds": ["c1"]},
    )
    assert resp.status_code == 404
    assert resp.json()["message"] == "账号不存在"


def test_create_group_400_empty_members(account):
    resp = client.post(
        f"/api/channels/{account['id']}/groups",
        json={"memberIds": []},
    )
    assert resp.status_code == 400
    assert "memberIds" in resp.json()["message"]


def test_create_group_success(account, contact):
    """auto 模式下真实协议失败会降级 mock，前端仍能拿到 GroupDTO。"""
    resp = client.post(
        f"/api/channels/{account['id']}/groups",
        json={"memberIds": [contact["id"]], "roomName": "QA群"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accountId"] == account["id"]
    assert data["groupType"] == "customer_group"
    assert data["name"] == "QA群"
    assert data["total"] == 1
    # 同时应写入 channel_sessions，支撑直接聊天
    sessions = client.get("/api/channels/sessions", params={"accountId": account["id"]}).json()
    assert any(s["remoteSessionId"] == data["roomId"] for s in sessions)


# --------------------------------------------------------------------------- #
# 一键已读（本地）接口
# --------------------------------------------------------------------------- #
def test_mark_read_local_404_unknown_account():
    resp = client.post(
        "/api/channels/acc-not-exist/sessions/read-local",
        json={},
    )
    assert resp.status_code == 404
    assert resp.json()["message"] == "账号不存在"


def test_mark_read_local_all(backend, account, unread_session):
    resp = client.post(
        f"/api/channels/{account['id']}/sessions/read-local",
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] >= 1
    # 未读已清零
    row = backend.query_one(
        "SELECT unread_count, read_status FROM channel_sessions WHERE id = ?",
        (unread_session["id"],),
    )
    assert row["unread_count"] == 0
    assert row["read_status"] == "read"


def test_mark_read_local_by_session_ids(backend, account, unread_session):
    resp = client.post(
        f"/api/channels/{account['id']}/sessions/read-local",
        json={"sessionIds": [unread_session["id"]]},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1
    row = backend.query_one(
        "SELECT unread_count, read_status FROM channel_sessions WHERE id = ?",
        (unread_session["id"],),
    )
    assert row["unread_count"] == 0
    assert row["read_status"] == "read"

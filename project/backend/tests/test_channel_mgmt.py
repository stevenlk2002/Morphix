"""渠道会话（Channel Sessions）模块接口测试。

使用与 test_api.py 一致的 ``TestClient(app)`` 直接对接共享开发库。
种子数据由 ``MORPHIX_DEV=1`` 启动时写入，以下断言对种子态与少量写入态均稳健。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# --------------------------------------------------------------------------- #
# 团队 / 账号
# --------------------------------------------------------------------------- #
def test_channels_teams_list():
    resp = client.get("/api/channels/teams")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 1
    assert any(t["id"] == "team-initial" for t in data)


def test_channels_accounts_list():
    resp = client.get("/api/channels/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 1
    assert any(a["id"] == "acc-zhulu" for a in data)
    # 富字段（JOIN channel_seats / teams）应存在
    acc = next(a for a in data if a["id"] == "acc-zhulu")
    assert "teamName" in acc and "onlineSessions" in acc


def test_channels_create_account():
    payload = {
        "channelType": "wechat",
        "protocol": "ipad",
        "teamId": "team-initial",
        "name": "接口测试账号",
    }
    resp = client.post("/api/channels/accounts", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["channelType"] == "wechat"
    assert body["teamId"] == "team-initial"


# --------------------------------------------------------------------------- #
# 联系人
# --------------------------------------------------------------------------- #
def test_channels_contacts_list():
    resp = client.get("/api/channels/contacts", params={"accountId": "acc-zhulu"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 1


def test_channels_contact_detail():
    resp = client.get("/api/channels/contacts/c-didi")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact"]["id"] == "c-didi"
    # 聚合：客户资料 / 沟通记录 / 自定义属性
    assert body["profile"] is not None
    assert isinstance(body["communications"], list)
    assert isinstance(body["attributes"], list)


# --------------------------------------------------------------------------- #
# 会话
# --------------------------------------------------------------------------- #
def test_channels_sessions_list():
    resp = client.get("/api/channels/sessions", params={"accountId": "acc-zhulu"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 1
    assert any(s["id"] == "ses-fushou" for s in data)


def test_channels_session_messages():
    resp = client.get("/api/channels/sessions/ses-fushou/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 2
    assert data[0]["conversationId"] == "ses-fushou"


def test_channels_session_hosting_toggle():
    resp = client.post(
        "/api/channels/sessions/ses-zhizu/hosting",
        json={"hosted": True, "botId": "zhulu"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hostedStatus"] == "hosted"
    assert body["hostedBotId"] == "zhulu"


# --------------------------------------------------------------------------- #
# 托管会话 / 托管机器人
# --------------------------------------------------------------------------- #
def test_channels_hosting_sessions_list():
    resp = client.get("/api/channels/hosting-sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 1
    assert any(h["id"] == "hs-min" for h in data)


def test_channels_hosting_bots_list():
    resp = client.get("/api/channels/hosting-bots")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) == 3


def test_channels_batch_update_hosting():
    resp = client.post(
        "/api/channels/hosting-sessions/batch-update",
        json={"ids": ["hs-lili", "hs-cloud"], "hostedStatus": "hosted", "hostingChain": "yefengqiu"},
    )
    assert resp.status_code == 200
    assert resp.json().get("updated", 0) >= 1


# --------------------------------------------------------------------------- #
# 托管规则
# --------------------------------------------------------------------------- #
def test_channels_hosting_rules_get_put():
    get_resp = client.get("/api/channels/hosting-rules")
    assert get_resp.status_code == 200
    put_resp = client.put(
        "/api/channels/hosting-rules",
        json={"autoResumeSeconds": 600, "autoCancelEnabled": True},
    )
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["autoResumeSeconds"] == 600
    assert body["autoCancelEnabled"] is True


# --------------------------------------------------------------------------- #
# 微信主体
# --------------------------------------------------------------------------- #
def test_channels_wechat_subjects_crud():
    create_resp = client.post(
        "/api/channels/wechat-subjects",
        json={"fullName": "测试主体-接口", "shortName": "测主", "corpId": "wwapitest0001"},
    )
    assert create_resp.status_code == 200
    subj = create_resp.json()
    assert subj["corpId"] == "wwapitest0001"
    subj_id = subj["id"]

    list_resp = client.get("/api/channels/wechat-subjects")
    assert list_resp.status_code == 200
    assert any(s["id"] == subj_id for s in list_resp.json())

    update_resp = client.put(
        f"/api/channels/wechat-subjects/{subj_id}",
        json={"shortName": "测主改"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["shortName"] == "测主改"

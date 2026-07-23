"""账号卡片增强（T01-T03）接口与逻辑测试。

覆盖（对应需求验证点 1/2/3）：
- 后端 schema 迁移：channel_accounts 新增 avatar / default_single_bot_id /
  default_group_bot_id 三列（旧库启动后自动补列）。
- GET /api/channels/accounts 返回新字段 avatar / defaultSingleBotId /
  defaultGroupBotId / defaultSingleBotName / defaultGroupBotName。
- GET /api/channels/accounts/available-bots 仅返回 status='online' 的机器人，
  形状为 {id,name}[]。
- PUT /api/channels/accounts/{id}/default-bots：成功返回更新后 AccountDTO；
  账号不存在 → 404；机器人不存在/未上线 → 400；空值/null 可清空。
- POST /api/channels/accounts/wecom/poll：命名优先级
  nickname>realname>name>start默认名>兜底，且 avatar 按 avatar>headImgUrl>
  headimgurl 解析并落库。
- 模块级 helper：_resolve_avatar_url / assert_online_bot。

说明：沿用仓库既有风格，直接 TestClient(app) 对接共享开发库（启动即跑迁移+种子）。
测试产生的机器人/账号在 finally 中清理，避免污染种子态。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_backend
from app.main import app
from app.repositories import (
    BotRepository,
    _resolve_avatar_url,
    assert_online_bot,
)

client = TestClient(app)


# --------------------------------------------------------------------------- #
# 1. Schema 迁移
# --------------------------------------------------------------------------- #
def test_channel_accounts_migration_columns():
    """channel_accounts 应包含本期新增的三列。"""
    backend = get_backend()
    cols = {r["name"] for r in backend.query("PRAGMA table_info(channel_accounts)")}
    assert "avatar" in cols
    assert "default_single_bot_id" in cols
    assert "default_group_bot_id" in cols


# --------------------------------------------------------------------------- #
# 2. GET /accounts 字段契约
# --------------------------------------------------------------------------- #
def test_accounts_list_has_new_fields():
    resp = client.get("/api/channels/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) >= 1
    acc = data[0]
    for f in (
        "avatar",
        "defaultSingleBotId",
        "defaultGroupBotId",
        "defaultSingleBotName",
        "defaultGroupBotName",
    ):
        assert f in acc, f"AccountDTO 缺少字段 {f}"


# --------------------------------------------------------------------------- #
# 3. GET /available-bots 仅返回 online
# --------------------------------------------------------------------------- #
def test_available_bots_only_online():
    resp = client.get("/api/channels/accounts/available-bots")
    assert resp.status_code == 200
    bots = resp.json()
    assert isinstance(bots, list)

    backend = get_backend()
    all_bots = {
        b["id"]: b["status"] for b in backend.query("SELECT id, status FROM bots")
    }
    online_ids = {bid for bid, st in all_bots.items() if st == "online"}
    returned_ids = {b["id"] for b in bots}

    # 返回集合 == 全部 online 机器人（不多不少）
    assert returned_ids == online_ids
    # 形状：{id, name}，且每个都在 online 集合中
    for b in bots:
        assert set(b.keys()) == {"id", "name"}
        assert all_bots[b["id"]] == "online"


# --------------------------------------------------------------------------- #
# 4. PUT /default-bots
# --------------------------------------------------------------------------- #
def _create_bot(name: str) -> str:
    r = client.post(
        "/api/bots",
        json={
            "name": name,
            "project": "QA",
            "workflow": "测试流程",
            "tone": "严谨",
            "trainingPrompt": "只回答测试问题",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _delete_bot(bot_id: str) -> None:
    get_backend().execute("DELETE FROM bots WHERE id = ?", (bot_id,))


def _create_account() -> str:
    r = client.post(
        "/api/channels/accounts",
        json={
            "channelType": "wecom",
            "protocol": "ipad",
            "teamId": "team-initial",
            "name": "QA账号卡测试",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_set_default_bots_flow():
    online_bot = _create_bot("QA在线机器人")
    client.post(f"/api/bots/{online_bot}/train")
    offline_bot = _create_bot("QA离线机器人")  # 默认 status='training'，未上线
    acc_id = _create_account()
    try:
        # 成功：设置单聊机器人，群聊留空
        resp = client.put(
            f"/api/channels/accounts/{acc_id}/default-bots",
            json={"singleBotId": online_bot, "groupBotId": None},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["defaultSingleBotId"] == online_bot
        assert body["defaultSingleBotName"] == "QA在线机器人"
        assert body["defaultGroupBotId"] == ""
        assert body["defaultGroupBotName"] is None

        # 404：账号不存在
        resp404 = client.put(
            "/api/channels/accounts/acc-not-exist-xyz/default-bots",
            json={"singleBotId": online_bot},
        )
        assert resp404.status_code == 404
        assert resp404.json().get("detail") == "账号不存在"

        # 400：机器人未上线（status='training'）
        resp400 = client.put(
            f"/api/channels/accounts/{acc_id}/default-bots",
            json={"singleBotId": offline_bot},
        )
        assert resp400.status_code == 400
        assert "message" in resp400.json()

        # 400：机器人不存在
        resp400b = client.put(
            f"/api/channels/accounts/{acc_id}/default-bots",
            json={"singleBotId": "no-such-bot-id"},
        )
        assert resp400b.status_code == 400

        # 清空：传 null 两个都清空
        resp_clear = client.put(
            f"/api/channels/accounts/{acc_id}/default-bots",
            json={"singleBotId": None, "groupBotId": None},
        )
        assert resp_clear.status_code == 200, resp_clear.text
        cleared = resp_clear.json()
        assert cleared["defaultSingleBotId"] == ""
        assert cleared["defaultGroupBotId"] == ""
        assert cleared["defaultSingleBotName"] is None
        assert cleared["defaultGroupBotName"] is None
    finally:
        get_backend().execute("DELETE FROM channel_accounts WHERE id = ?", (acc_id,))
        _delete_bot(online_bot)
        _delete_bot(offline_bot)


# --------------------------------------------------------------------------- #
# 5. POST /wecom/poll 命名优先级 + avatar 落库
# --------------------------------------------------------------------------- #
def test_poll_wecom_naming_and_avatar(monkeypatch):
    """loginType==2 时：nickname 优先于 realname/name；avatar 解析并落库。"""
    from app.routers import channel_hosting

    test_uuid = "qa-poll-uuid-abc123"

    def fake_poll(uuid):
        return {
            "loginType": 2,
            "userInfo": {
                "realname": "张三",
                "name": "zhangsan",
                "nickname": "张三昵称",
                "headImgUrl": "http://img/avatar.png",
            },
            "longLinkState": 1,
            "mock": False,
        }

    monkeypatch.setattr(channel_hosting.ipad_client, "poll_wecom", fake_poll)
    monkeypatch.setattr(channel_hosting.ipad_sync, "trigger_sync", lambda acc_id: False)
    monkeypatch.setattr(
        channel_hosting.ipad_sync, "register_callback", lambda acc_id: {"registered": False}
    )
    channel_hosting.ipad_client.MockState[test_uuid] = {
        "team_id": "team-initial",
        "channel_type": "wecom",
        "name": "默认名",
    }

    try:
        resp = client.post(
            "/api/channels/accounts/wecom/poll", json={"uuid": test_uuid}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["loginType"] == 2
        acc = body["account"]
        # 命名优先级：nickname > realname > name
        assert acc["name"] == "张三昵称"
        # avatar 解析（headImgUrl 命中）
        assert acc["avatar"] == "http://img/avatar.png"
    finally:
        channel_hosting.ipad_client.MockState.pop(test_uuid, None)
        # 清理落库账号
        backend = get_backend()
        rows = backend.query(
            "SELECT id FROM channel_accounts WHERE account_name = ? AND ipad_uuid = ?",
            ("张三昵称", test_uuid),
        )
        for r in rows:
            backend.execute("DELETE FROM channel_accounts WHERE id = ?", (r["id"],))


# --------------------------------------------------------------------------- #
# 6. PUT /channels/accounts/{id}/status 上下线切换
# --------------------------------------------------------------------------- #
def test_update_account_status():
    acc_id = _create_account()
    try:
        # 初始 online
        assert get_backend().query(
            "SELECT status FROM channel_accounts WHERE id = ?", (acc_id,)
        )[0]["status"] == "online"

        # 下线
        resp = client.put(f"/api/channels/accounts/{acc_id}/status", json={"status": "offline"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "offline"
        assert body["online"] is False

        # 上线
        resp2 = client.put(f"/api/channels/accounts/{acc_id}/status", json={"status": "online"})
        assert resp2.status_code == 200, resp2.text
        body2 = resp2.json()
        assert body2["status"] == "online"
        assert body2["online"] is True

        # 404
        resp404 = client.put("/api/channels/accounts/acc-not-exist/status", json={"status": "offline"})
        assert resp404.status_code == 404

        # 400 非法状态
        resp400 = client.put(f"/api/channels/accounts/{acc_id}/status", json={"status": "deleted"})
        assert resp400.status_code == 400
    finally:
        get_backend().execute("DELETE FROM channel_accounts WHERE id = ?", (acc_id,))


# --------------------------------------------------------------------------- #
# 7. 模块级 helper 单测
# --------------------------------------------------------------------------- #
def test_resolve_avatar_url_priority():
    assert _resolve_avatar_url(None) == ""
    assert _resolve_avatar_url({}) == ""
    assert _resolve_avatar_url({"headImgUrl": "http://x/a.png"}) == "http://x/a.png"
    assert _resolve_avatar_url({"headimgurl": "http://x/b.png"}) == "http://x/b.png"
    # avatar 优先于 headImgUrl
    assert (
        _resolve_avatar_url(
            {"avatar": "http://x/av.png", "headImgUrl": "http://x/h.png"}
        )
        == "http://x/av.png"
    )
    # 纯空白视为空
    assert _resolve_avatar_url({"avatar": "   "}) == ""
    # 非 dict 返回空
    assert _resolve_avatar_url("not-a-dict") == ""


def test_assert_online_bot():
    repo = BotRepository(get_backend())
    # 空值放行
    assert assert_online_bot(repo, None) is None
    assert assert_online_bot(repo, "") is None
    # 不存在 -> ValueError
    with pytest.raises(ValueError):
        assert_online_bot(repo, "definitely-not-a-real-bot")
    # 创建并训练为 online -> 通过并返回 bot
    bid = _create_bot("QA校验在线机器人")
    client.post(f"/api/bots/{bid}/train")
    try:
        bot = assert_online_bot(repo, bid)
        assert bot is not None
        assert bot["id"] == bid
    finally:
        _delete_bot(bid)

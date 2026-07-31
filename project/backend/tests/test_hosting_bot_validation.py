"""「托管开关前置校验 + 托管机器人头像」改动验证 —— 测试套件。

覆盖本轮改动：
1. `POST /api/channels/sessions/{id}/hosting` 前置校验（后端防御）：
   - hosted=True 且 botId 缺失 / 空串 / 纯空白 → 400「请先选择机器人」。
   - hosted=True 且 botId 不在 `HOSTING_BOTS` 中 → 400「机器人不存在」。
   - hosted=True 且 botId 合法 → 200，hostedStatus='hosted'。
   - hosted=False → 200（关闭托管无需 botId），hostedStatus='unhosted'。
2. `assert_hosting_bot` / `normalize_hosting_bot_id` 纯函数边界。
3. `GET /api/channels/hosting-bots` 返回项包含 `avatar` 字段（会话卡片头像）。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest \
        tests/test_hosting_bot_validation.py -v -p no:cacheprovider
"""
from __future__ import annotations

import os

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest
from fastapi.testclient import TestClient

from app import schema as schema_mod
import app.database as _db_mod
from app.database import SQLiteBackend, set_backend
from app.main import app
from app.repositories import (
    HOSTING_BOTS,
    HOSTING_BOT_REQUIRED_MSG,
    HOSTING_BOT_UNKNOWN_MSG,
    ChannelMgmtRepository,
    assert_hosting_bot,
    normalize_hosting_bot_id,
)


ACCOUNT_ID = "acc-hosting-qa"
SESSION_ID = f"{ACCOUNT_ID}:ses-hosting"
VALID_BOT_ID = "yefengqiu"
HOSTING_URL = f"/api/channels/sessions/{SESSION_ID}/hosting"


# --------------------------------------------------------------------------- #
# 测试夹具：隔离的临时 SQLite 库（不污染开发库）
# --------------------------------------------------------------------------- #
@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 后端，注入为全局后端，用例结束后还原。"""
    be = SQLiteBackend(tmp_path / "morphix_hosting_validation.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def repo(backend) -> ChannelMgmtRepository:
    """基于隔离后端的渠道会话管理仓储。"""
    return ChannelMgmtRepository(backend)


@pytest.fixture
def session_id(repo) -> str:
    """预置一条未托管会话，返回其 id。"""
    repo.upsert_channel_session(
        {
            "id": SESSION_ID,
            "account_id": ACCOUNT_ID,
            "contact_id": None,
            "name": "托管校验会话",
            "channel": "企业微信",
            "channel_type": "wecom",
            "remote_session_id": "u-hosting",
            "hosted_status": "unhosted",
            "hosted_bot_id": None,
            "external_tag": "外部",
        }
    )
    return SESSION_ID


@pytest.fixture
def client(backend) -> TestClient:
    """TestClient（路由内每次请求都取全局后端，故与隔离库绑定生效）。"""
    return TestClient(app)


# --------------------------------------------------------------------------- #
# 1. 纯函数边界：normalize_hosting_bot_id / assert_hosting_bot
# --------------------------------------------------------------------------- #
class TestHostingBotHelpers:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("\t\n", None),
            (" yefengqiu ", "yefengqiu"),
            ("zhulu", "zhulu"),
        ],
    )
    def test_normalize_hosting_bot_id(self, raw, expected):
        """空串 / 纯空白统一归一化为 None，其余去首尾空白。"""
        assert normalize_hosting_bot_id(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_assert_raises_when_hosted_without_bot(self, raw):
        """开启托管但未选机器人 → ValueError('请先选择机器人')。"""
        with pytest.raises(ValueError) as exc:
            assert_hosting_bot(True, raw)
        assert str(exc.value) == HOSTING_BOT_REQUIRED_MSG

    def test_assert_raises_when_bot_unknown(self):
        """开启托管但机器人不存在 → ValueError('机器人不存在')。"""
        with pytest.raises(ValueError) as exc:
            assert_hosting_bot(True, "not-a-bot")
        assert str(exc.value) == HOSTING_BOT_UNKNOWN_MSG

    def test_assert_returns_normalized_id_when_valid(self):
        """合法机器人 → 返回去空白后的 id。"""
        assert assert_hosting_bot(True, f"  {VALID_BOT_ID} ") == VALID_BOT_ID

    @pytest.mark.parametrize("raw, expected", [(None, None), ("", None), ("zhulu", "zhulu")])
    def test_assert_skips_validation_when_unhosted(self, raw, expected):
        """关闭托管不校验机器人（关闭托管无需 botId）。"""
        assert assert_hosting_bot(False, raw) == expected


# --------------------------------------------------------------------------- #
# 2. 接口级校验：POST /api/channels/sessions/{id}/hosting
# --------------------------------------------------------------------------- #
class TestSessionHostingApiValidation:
    def test_hosted_true_with_empty_bot_id_returns_400(self, client, session_id):
        """hosted=true + botId='' → 400「请先选择机器人」。"""
        resp = client.post(HOSTING_URL, json={"hosted": True, "botId": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == HOSTING_BOT_REQUIRED_MSG

    def test_hosted_true_without_bot_id_returns_400(self, client, session_id):
        """hosted=true 且完全不传 botId → 400。"""
        resp = client.post(HOSTING_URL, json={"hosted": True})
        assert resp.status_code == 400
        assert resp.json()["detail"] == HOSTING_BOT_REQUIRED_MSG

    def test_hosted_true_with_null_bot_id_returns_400(self, client, session_id):
        """hosted=true + botId=null → 400。"""
        resp = client.post(HOSTING_URL, json={"hosted": True, "botId": None})
        assert resp.status_code == 400
        assert resp.json()["detail"] == HOSTING_BOT_REQUIRED_MSG

    def test_hosted_true_with_whitespace_bot_id_returns_400(self, client, session_id):
        """hosted=true + botId='   '（纯空白）→ 400。"""
        resp = client.post(HOSTING_URL, json={"hosted": True, "botId": "   "})
        assert resp.status_code == 400
        assert resp.json()["detail"] == HOSTING_BOT_REQUIRED_MSG

    def test_hosted_true_with_unknown_bot_id_returns_400(self, client, session_id):
        """hosted=true + 不存在的 botId → 400「机器人不存在」。"""
        resp = client.post(HOSTING_URL, json={"hosted": True, "botId": "ghost-bot"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == HOSTING_BOT_UNKNOWN_MSG

    def test_hosted_true_with_valid_bot_id_returns_200(self, client, session_id):
        """hosted=true + 合法 botId → 200，会话进入已托管态。"""
        resp = client.post(HOSTING_URL, json={"hosted": True, "botId": VALID_BOT_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["hostedStatus"] == "hosted"
        assert body["hostedBotId"] == VALID_BOT_ID

    def test_hosted_true_trims_bot_id(self, client, session_id):
        """botId 首尾空白被去除后落库。"""
        resp = client.post(HOSTING_URL, json={"hosted": True, "botId": f" {VALID_BOT_ID} "})
        assert resp.status_code == 200
        assert resp.json()["hostedBotId"] == VALID_BOT_ID

    def test_hosted_false_without_bot_id_returns_200(self, client, session_id):
        """hosted=false 且不传 botId → 200（关闭托管无需机器人）。"""
        resp = client.post(HOSTING_URL, json={"hosted": False})
        assert resp.status_code == 200
        body = resp.json()
        assert body["hostedStatus"] == "unhosted"
        assert body["hostedBotId"] in (None, "")

    def test_hosted_false_keeps_selected_bot(self, client, session_id):
        """hosted=false + botId → 200，仅关闭托管并保留已选机器人。"""
        resp = client.post(HOSTING_URL, json={"hosted": False, "botId": "zhulu"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["hostedStatus"] == "unhosted"
        assert body["hostedBotId"] == "zhulu"

    def test_failed_validation_does_not_change_session(self, client, session_id, repo):
        """校验失败时不得写库：会话仍保持未托管。"""
        client.post(HOSTING_URL, json={"hosted": True, "botId": ""})
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["hostedStatus"] == "unhosted"

    def test_toggle_on_then_off_flow(self, client, session_id):
        """完整流程：选机器人开启托管 → 关闭托管（保留机器人）→ 再次开启。"""
        on = client.post(HOSTING_URL, json={"hosted": True, "botId": VALID_BOT_ID})
        assert on.status_code == 200 and on.json()["hostedStatus"] == "hosted"

        off = client.post(HOSTING_URL, json={"hosted": False, "botId": VALID_BOT_ID})
        assert off.status_code == 200 and off.json()["hostedStatus"] == "unhosted"

        again = client.post(HOSTING_URL, json={"hosted": True, "botId": VALID_BOT_ID})
        assert again.status_code == 200
        assert again.json()["hostedBotId"] == VALID_BOT_ID


# --------------------------------------------------------------------------- #
# 3. 仓储层防御（Router 之外的第二道防线）
# --------------------------------------------------------------------------- #
class TestRepositoryHostingValidation:
    def test_repository_raises_without_bot(self, repo, session_id):
        """仓储层直接调用同样拦截空机器人。"""
        with pytest.raises(ValueError) as exc:
            repo.set_session_hosting(session_id, True, None)
        assert str(exc.value) == HOSTING_BOT_REQUIRED_MSG

    def test_repository_allows_unhosting_without_bot(self, repo, session_id):
        """仓储层关闭托管无需机器人。"""
        result = repo.set_session_hosting(session_id, False, None)
        assert result is not None
        assert result["hostedStatus"] == "unhosted"


# --------------------------------------------------------------------------- #
# 4. 托管机器人头像字段（会话卡片渲染依赖）
# --------------------------------------------------------------------------- #
class TestHostingBotsAvatar:
    def test_static_config_has_avatar(self):
        """静态配置每条都带非空 avatar。"""
        assert len(HOSTING_BOTS) == 3
        assert all(bot.get("avatar") for bot in HOSTING_BOTS)

    def test_api_returns_avatar_field(self, client):
        """GET /api/channels/hosting-bots 每项含 id / name / avatar。"""
        resp = client.get("/api/channels/hosting-bots")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) and len(data) == 3
        for bot in data:
            assert bot["id"] and bot["name"] and bot["avatar"]

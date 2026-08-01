"""「企业微信应用会话正确显示名字和头像」—— 测试套件（wecom_app_display T05）。

覆盖架构文档 T01–T04 的全部改动点：

1. **协议层**（`app.ipad_client`，mock `_post`）
   - `get_corp_wx_app`：`wxAppList` 解析、17 位 ID 全程字符串、`imgId → avatar`、
     `desc → description`、脏条目丢弃、信封兼容、404 抛 `IPadProtocolError`。
   - `get_user_info_by_vids`：请求体 `vids` 必须是**整型数组**、响应 `data` 是
     **顶层 list**、去重、按 100 分批。
2. **存储层**（`app.schema` / `app.repositories`）
   - `channel_apps` 建表 + 索引幂等（重复 `migrate_schema` 不报错）。
   - `upsert_channel_app` / `get_app_by_session_id` **双键匹配**（appId ∪ appOpenId）。
   - 17 位 ID 往返零精度损失。
3. **查询层**（`list_sessions` 收敛式过滤）
   - 名称未解析（`name == remote_session_id` 且三表皆未命中）→ **隐藏**（零回归）。
   - `channel_apps` 命中 → 自动浮现，且带出 `name` / `avatar` / `appType`。
   - `channel_contacts`（vid 补拉）命中 → 自动浮现（查询层零改动路径）。
   - 搜索命中应用名。
4. **DTO 层**（`row_to_session`）
   - 新增 `msgType` / `entityKind` / `readonly` / `appType` 四个语义字段。
5. **消息头像**（`_resolve_sender_avatar`）
   - 应用消息按**会话维度**解析（`sender_id == remote_session_id` 场景）。
   - 应用分支是终态：未命中返回空串，不回落联系人。
6. **同步/发送**（`app.ipad_sync`）
   - `_resolve_target`：`msg_type ∈ {3,103,107}` 拒发；`msg_type == 6` **放行**。
   - `_upsert_session`：应用会话 `contact_id` 恒为 `None`（修 PRD F4）。
   - `_sync_corp_apps`：`getCorpWxApp` 404 时降级返回 0，不阻断其余同步路。
   - `_backfill_unknown_vids`：仅对 `msg_type ∈ {0,6}` 且无联系人的 vid 补拉。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest \
        tests/test_wecom_app_display.py -q -p no:cacheprovider
"""
from __future__ import annotations

import os

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest

from app import ipad_client, ipad_sync
from app import schema as schema_mod
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.repositories import (
    APP_MSG_TYPES,
    VID_MSG_TYPES,
    ChannelMgmtRepository,
    is_readonly_session,
    resolve_entity_kind,
    row_to_app,
    row_to_session,
)

ACCOUNT_ID = "acc-wecom-app"

# 对拍实测样本（架构文档 §1.2）：17 位 appId 已超 Number.MAX_SAFE_INTEGER。
LONG_APP_ID = "5629499770789533"
LONGER_APP_ID = "12345678901234567"
SHORT_OPEN_ID = "10223"
TEAM_VID = "1688852792312821"


# --------------------------------------------------------------------------- #
# 测试夹具
# --------------------------------------------------------------------------- #
@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_wecom_app.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def repo(backend):
    """基于隔离后端的渠道会话管理仓储。"""
    return ChannelMgmtRepository(backend)


def _patch_post(monkeypatch, payload):
    """将 `ipad_client._post` 替换为直接返回给定 payload。"""
    monkeypatch.setattr(ipad_client, "_post", lambda path, p=None: payload)


def _make_app(
    repo: ChannelMgmtRepository,
    *,
    app_id: str,
    app_open_id: str = "",
    name: str = "企业微信团队",
    avatar: str = "http://cdn/app.png",
    app_type: int = 1,
) -> None:
    """写入一条 `channel_apps` 记录。"""
    repo.upsert_channel_app(
        {
            "account_id": ACCOUNT_ID,
            "app_id": app_id,
            "app_open_id": app_open_id,
            "corpid": "1970325134",
            "name": name,
            "avatar": avatar,
            "app_type": app_type,
            "description": "应用说明",
            "home_info": "",
            "last_mod_time": 1700000000,
            "extra_json": {"groupId": "998877665544332211"},
        }
    )


def _make_session(
    repo: ChannelMgmtRepository,
    remote_session_id: str,
    *,
    name: str | None = None,
    msg_type: int = 0,
    contact_id: str | None = None,
) -> str:
    """写入一条 `channel_sessions` 记录，返回会话 id。

    主键严格遵循生产约定 `{account_id}:{remote_session_id}` —— `_resolve_sender_avatar`
    会从 `conversation_id` 冒号后解析 `remote_session_id`，若测试自造前缀不一致，
    应用/群分支会静默落空，测出假阴性。

    `name` 缺省时刻意写成 `remote_session_id`，模拟「协议只给了裸 sessionid、
    名称尚未解析」的真实状态 —— 这是收敛式过滤要隐藏的目标形态。
    """
    sess_id = f"{ACCOUNT_ID}:{remote_session_id}"
    repo.upsert_channel_session(
        {
            "id": sess_id,
            "account_id": ACCOUNT_ID,
            "contact_id": contact_id,
            "name": remote_session_id if name is None else name,
            "channel": "企业微信",
            "channel_type": "wecom",
            "remote_session_id": remote_session_id,
            "msg_type": msg_type,
        }
    )
    return sess_id


def _make_contact(
    repo: ChannelMgmtRepository,
    user_id: str,
    *,
    nickname: str = "联系人",
    avatar: str = "",
    ctype: str = "customer",
) -> str:
    """写入一条 `channel_contacts` 记录，返回 contact_id。"""
    cid = f"{ACCOUNT_ID}:{user_id}"
    repo.upsert_channel_contact(
        {
            "id": cid,
            "account_id": ACCOUNT_ID,
            "channel": "企业微信",
            "channel_type": "wecom",
            "name": nickname,
            "nickname": nickname,
            "type": ctype,
            "status": "online",
            "remark": "",
            "description": "",
            "add_time": "",
            "source": "",
            "user_id": user_id,
            "label_ids": "[]",
            "raw_status": "",
            "extra_json": "{}",
            "avatar": avatar,
        }
    )
    return cid


# --------------------------------------------------------------------------- #
# 1. 协议层：getCorpWxApp
# --------------------------------------------------------------------------- #
class TestGetCorpWxApp:
    def test_parses_wx_app_list(self, monkeypatch):
        """标准信封：`{"data": {"wxAppList": [...]}}` 应被正确解析。"""
        _patch_post(
            monkeypatch,
            {
                "data": {
                    "wxAppList": [
                        {
                            "appId": 5629499770789533,
                            "appOpenId": 10223,
                            "corpid": 1970325134,
                            "name": "AI数字员工",
                            "imgId": "http://wework.qpic.cn/aidigital.png",
                            "appType": 2,
                            "desc": "智能助手",
                            "homeInfo": "https://home",
                            "lastModTime": 1700000000,
                        }
                    ]
                },
                "errcode": 0,
            },
        )
        apps = ipad_client.get_corp_wx_app("uuid")
        assert len(apps) == 1
        app = apps[0]
        # 17 位以内也一律字符串化，避免下游任何一处走 int 丢精度（§8.2）
        assert app["appId"] == "5629499770789533"
        assert isinstance(app["appId"], str)
        assert app["appOpenId"] == "10223"
        assert app["corpid"] == "1970325134"
        assert app["name"] == "AI数字员工"
        # imgId → avatar，desc → description（desc 是 SQL 保留字，§3.1）
        assert app["avatar"] == "http://wework.qpic.cn/aidigital.png"
        assert app["description"] == "智能助手"
        assert app["appType"] == 2
        assert app["lastModTime"] == 1700000000

    def test_long_id_no_precision_loss(self, monkeypatch):
        """17 位 appId 必须原样字符串透出，不得被 float/int 折损。"""
        _patch_post(
            monkeypatch,
            {"data": {"wxAppList": [{"appId": LONGER_APP_ID, "name": "长ID应用"}]}},
        )
        apps = ipad_client.get_corp_wx_app("uuid")
        assert apps[0]["appId"] == LONGER_APP_ID

    def test_bare_envelope_and_alias_keys(self, monkeypatch):
        """裸信封 + 别名键（`appList` / `app_id`）也应兼容。"""
        _patch_post(monkeypatch, {"appList": [{"app_id": "777", "name": "别名应用"}]})
        apps = ipad_client.get_corp_wx_app("uuid")
        assert len(apps) == 1 and apps[0]["appId"] == "777"

    def test_drops_entries_without_any_key(self, monkeypatch):
        """双键（appId / appOpenId）皆空的脏条目应被丢弃。"""
        _patch_post(
            monkeypatch,
            {
                "data": {
                    "wxAppList": [
                        {"name": "无ID脏数据"},
                        {"appOpenId": SHORT_OPEN_ID, "name": "仅OpenId"},
                    ]
                }
            },
        )
        apps = ipad_client.get_corp_wx_app("uuid")
        assert [a["name"] for a in apps] == ["仅OpenId"]

    def test_empty_list_returns_empty(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {}})
        assert ipad_client.get_corp_wx_app("uuid") == []

    def test_unknown_keys_go_to_extra_and_stringified(self, monkeypatch):
        """未知键收进 `extra`，其中的 Long ID 同样字符串化。"""
        _patch_post(
            monkeypatch,
            {
                "data": {
                    "wxAppList": [
                        {"appId": "1", "name": "X", "groupId": 998877665544332211, "flag": 3}
                    ]
                }
            },
        )
        extra = ipad_client.get_corp_wx_app("uuid")[0]["extra"]
        assert extra["groupId"] == "998877665544332211"
        assert extra["flag"] == 3

    def test_protocol_error_propagates(self, monkeypatch):
        """生产实例当前返回 HTTP 404 → `_post` 抛错，本函数不吞（由调用方降级）。"""

        def _boom(path, payload=None):
            raise ipad_client.IPadProtocolError("HTTP 404 Not Found")

        monkeypatch.setattr(ipad_client, "_post", _boom)
        with pytest.raises(ipad_client.IPadProtocolError):
            ipad_client.get_corp_wx_app("uuid")


# --------------------------------------------------------------------------- #
# 2. 协议层：GetUserInfoByVids
# --------------------------------------------------------------------------- #
class TestGetUserInfoByVids:
    def test_top_level_list_payload(self, monkeypatch):
        """对拍结论：响应体 `data` 是**顶层 list**，不是 `{"list": [...]}`。"""
        _patch_post(
            monkeypatch,
            {
                "data": [
                    {
                        "vid": 1688852792312821,
                        "name": "企业微信团队",
                        "avatar": "http://cdn/team.png",
                        "corpid": 1970325134,
                    }
                ],
                "errcode": 0,
            },
        )
        users = ipad_client.get_user_info_by_vids("uuid", [TEAM_VID])
        assert len(users) == 1
        assert users[0]["user_id"] == TEAM_VID
        assert users[0]["nickname"] == "企业微信团队"
        assert users[0]["avatar"] == "http://cdn/team.png"

    def test_request_vids_are_integers(self, monkeypatch):
        """对拍结论：请求体 `vids` 必须是整型数组，字符串数组服务端不识别。"""
        captured: dict = {}

        def _capture(path, payload=None):
            captured["path"] = path
            captured["payload"] = payload
            return {"data": []}

        monkeypatch.setattr(ipad_client, "_post", _capture)
        ipad_client.get_user_info_by_vids("uuid", [TEAM_VID, LONG_APP_ID])
        assert captured["path"] == "wxwork/GetUserInfoByVids"
        assert captured["payload"]["vids"] == [1688852792312821, 5629499770789533]
        assert all(isinstance(v, int) for v in captured["payload"]["vids"])

    def test_dedupe_and_skip_non_digits(self, monkeypatch):
        calls: list[list[int]] = []

        def _capture(path, payload=None):
            calls.append(payload["vids"])
            return {"data": []}

        monkeypatch.setattr(ipad_client, "_post", _capture)
        ipad_client.get_user_info_by_vids("uuid", [TEAM_VID, TEAM_VID, "abc", "", None])
        assert calls == [[1688852792312821]]

    def test_batches_by_limit(self, monkeypatch):
        """超过 `VIDS_BATCH_LIMIT`（100）应自动分批，不得单次超限。"""
        calls: list[int] = []

        def _capture(path, payload=None):
            calls.append(len(payload["vids"]))
            return {"data": []}

        monkeypatch.setattr(ipad_client, "_post", _capture)
        vids = [str(1000000000000000 + i) for i in range(250)]
        ipad_client.get_user_info_by_vids("uuid", vids)
        assert calls == [100, 100, 50]
        assert max(calls) <= ipad_client.VIDS_BATCH_LIMIT

    def test_empty_input_short_circuits(self, monkeypatch):
        def _boom(path, payload=None):  # pragma: no cover - 不应被调用
            raise AssertionError("空入参不应发起请求")

        monkeypatch.setattr(ipad_client, "_post", _boom)
        assert ipad_client.get_user_info_by_vids("uuid", []) == []


# --------------------------------------------------------------------------- #
# 3. 语义常量与判定函数
# --------------------------------------------------------------------------- #
class TestMsgTypeSemantics:
    def test_constant_membership(self):
        """对拍结论：裸数字会话实际是 {107, 103, 0, 6}，非 PRD 假设的仅 3。"""
        assert APP_MSG_TYPES == frozenset({3, 103, 107})
        assert VID_MSG_TYPES == frozenset({0, 6})
        # 两族互斥，msg_type=6（AI数字员工）实测有真实 outbound，不得并入只读族
        assert APP_MSG_TYPES.isdisjoint(VID_MSG_TYPES)
        assert 6 not in APP_MSG_TYPES

    @pytest.mark.parametrize(
        "msg_type,expected",
        [
            (0, "person"),
            (1, "group"),
            (3, "app"),
            (6, "service"),
            (103, "app"),
            (107, "app"),
            (999, "person"),
            (None, "person"),
            ("103", "app"),
        ],
    )
    def test_resolve_entity_kind(self, msg_type, expected):
        assert resolve_entity_kind(msg_type) == expected

    @pytest.mark.parametrize(
        "msg_type,expected",
        [(0, False), (1, False), (3, True), (6, False), (103, True), (107, True), (None, False)],
    )
    def test_is_readonly_session(self, msg_type, expected):
        assert is_readonly_session(msg_type) is expected


# --------------------------------------------------------------------------- #
# 4. 存储层：channel_apps 建表幂等 + 双键匹配
# --------------------------------------------------------------------------- #
class TestChannelAppsStorage:
    def test_migrate_schema_is_idempotent(self, backend):
        """重复执行 `migrate_schema` 不得抛错（§8.5 建表/迁移双写一致）。"""
        schema_mod.migrate_schema(backend)
        schema_mod.migrate_schema(backend)
        row = backend.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='channel_apps'"
        )
        assert row is not None

    def test_indexes_created(self, backend):
        names = {
            r["name"]
            for r in backend.query(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='channel_apps'"
            )
        }
        # (account_id, app_id) 由唯一索引覆盖；同列的普通索引已作为冗余索引移除（K5）。
        assert "uk_channel_apps_account_appid" in names
        assert "idx_channel_apps_account_openid" in names
        assert "idx_channel_apps_account_appid" not in names

    def test_redundant_index_dropped_on_migrate(self, backend):
        """存量库里遗留的冗余索引应在 `migrate_schema` 时被清理掉（K5）。"""
        backend.execute(
            "CREATE INDEX IF NOT EXISTS idx_channel_apps_account_appid "
            "ON channel_apps(account_id, app_id)"
        )
        schema_mod.migrate_schema(backend)
        names = {
            r["name"]
            for r in backend.query(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='channel_apps'"
            )
        }
        assert "idx_channel_apps_account_appid" not in names
        # 唯一索引必须仍在 —— 否则该列对将彻底失去索引覆盖。
        assert "uk_channel_apps_account_appid" in names

    def test_dual_key_match_by_app_id(self, repo):
        """长 appId 会话 id 应命中。"""
        _make_app(repo, app_id=LONG_APP_ID, app_open_id=SHORT_OPEN_ID)
        row = repo.get_app_by_session_id(ACCOUNT_ID, LONG_APP_ID)
        assert row is not None and row["name"] == "企业微信团队"

    def test_dual_key_match_by_app_open_id(self, repo):
        """5 位 appOpenId 会话 id 同样应命中 —— 单键必漏（对拍结论 2B）。"""
        _make_app(repo, app_id=LONG_APP_ID, app_open_id=SHORT_OPEN_ID)
        row = repo.get_app_by_session_id(ACCOUNT_ID, SHORT_OPEN_ID)
        assert row is not None and row["app_id"] == LONG_APP_ID

    def test_dual_key_miss_returns_none(self, repo):
        _make_app(repo, app_id=LONG_APP_ID)
        assert repo.get_app_by_session_id(ACCOUNT_ID, "nobody") is None
        assert repo.get_app_by_session_id("", LONG_APP_ID) is None

    def test_account_isolation(self, repo):
        """跨账号不得命中。"""
        _make_app(repo, app_id=LONG_APP_ID)
        assert repo.get_app_by_session_id("other-acc", LONG_APP_ID) is None

    def test_long_id_round_trip(self, repo):
        """17 位 ID 落库 → 读回零精度损失。"""
        _make_app(repo, app_id=LONGER_APP_ID, name="长ID应用")
        row = repo.get_app_by_session_id(ACCOUNT_ID, LONGER_APP_ID)
        assert row is not None and str(row["app_id"]) == LONGER_APP_ID

    def test_upsert_is_idempotent_on_natural_key(self, repo):
        """同一 `(account_id, app_id)` 重复 upsert 只保留一条。"""
        _make_app(repo, app_id=LONG_APP_ID, name="旧名")
        _make_app(repo, app_id=LONG_APP_ID, name="新名")
        apps = repo.list_apps(ACCOUNT_ID)
        assert len(apps) == 1 and apps[0]["name"] == "新名"

    def test_upsert_falls_back_to_open_id_as_key(self, repo):
        """`app_id` 缺失时用 `app_open_id` 兜底构造主键，保证可被双键命中。"""
        _make_app(repo, app_id="", app_open_id=SHORT_OPEN_ID, name="仅OpenId")
        row = repo.get_app_by_session_id(ACCOUNT_ID, SHORT_OPEN_ID)
        assert row is not None and row["name"] == "仅OpenId"

    def test_upsert_ignores_dirty_entry(self, repo):
        """双键皆空 → 不落库。"""
        repo.upsert_channel_app({"account_id": ACCOUNT_ID, "name": "脏数据"})
        assert repo.list_apps(ACCOUNT_ID) == []

    def test_row_to_app_ids_are_strings(self, repo):
        _make_app(repo, app_id=LONGER_APP_ID, app_open_id=SHORT_OPEN_ID)
        dto = repo.list_apps(ACCOUNT_ID)[0]
        assert dto["appId"] == LONGER_APP_ID and isinstance(dto["appId"], str)
        assert dto["appOpenId"] == SHORT_OPEN_ID and isinstance(dto["appOpenId"], str)
        assert dto["extra"]["groupId"] == "998877665544332211"

    def test_row_to_app_handles_missing_optional_columns(self):
        """`row_to_app` 对缺列的行也应容错（不抛 KeyError）。"""
        dto = row_to_app({"id": "x", "account_id": ACCOUNT_ID})
        assert dto["appId"] == "" and dto["appType"] == 0


# --------------------------------------------------------------------------- #
# 5. 查询层：收敛式过滤（本需求核心，零视觉回归的保证）
# --------------------------------------------------------------------------- #
class TestConvergentFiltering:
    def test_unresolved_app_session_hidden(self, repo):
        """名称未解析的应用会话（name == remote_session_id）→ 隐藏。

        这正是 `getCorpWxApp` 404 期间的形态：与改动前 `WHERE msg_type != 3`
        的可见结果完全一致 —— **零视觉回归**。
        """
        _make_session(repo, LONG_APP_ID, msg_type=107)
        assert repo.list_sessions(account_id=ACCOUNT_ID) == []

    @pytest.mark.parametrize("msg_type", sorted(APP_MSG_TYPES | VID_MSG_TYPES))
    def test_unresolved_any_family_hidden(self, repo, msg_type):
        """收敛式过滤不挑 msg_type：任何未解析的裸数字会话都隐藏。"""
        _make_session(repo, f"90000{msg_type}", msg_type=msg_type)
        assert repo.list_sessions(account_id=ACCOUNT_ID) == []

    def test_app_session_surfaces_when_app_synced(self, repo):
        """`channel_apps` 命中 → 会话自动浮现，带出名称 / 头像 / appType。"""
        _make_app(
            repo,
            app_id=LONG_APP_ID,
            app_open_id=SHORT_OPEN_ID,
            name="AI数字员工",
            avatar="http://cdn/ai.png",
            app_type=2,
        )
        _make_session(repo, LONG_APP_ID, msg_type=107)
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        sess = sessions[0]
        assert sess["name"] == "AI数字员工"
        assert sess["avatar"] == "http://cdn/ai.png"
        assert sess["appType"] == 2
        assert sess["entityKind"] == "app"
        assert sess["readonly"] is True
        assert sess["msgType"] == 107

    def test_app_session_surfaces_via_open_id(self, repo):
        """会话 id 为 5 位 appOpenId 时也应通过双键 JOIN 浮现。"""
        _make_app(repo, app_id=LONG_APP_ID, app_open_id=SHORT_OPEN_ID, name="企业微信团队")
        _make_session(repo, SHORT_OPEN_ID, msg_type=103)
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1 and sessions[0]["name"] == "企业微信团队"

    def test_vid_session_surfaces_via_contact(self, repo):
        """vid 补拉落 `channel_contacts` 后，现有 JOIN 直接命中（查询层零改动）。"""
        _make_contact(repo, TEAM_VID, nickname="企业微信团队", avatar="http://cdn/team.png")
        _make_session(repo, TEAM_VID, msg_type=0)
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["name"] == "企业微信团队"
        assert sessions[0]["avatar"] == "http://cdn/team.png"
        assert sessions[0]["entityKind"] == "person"
        assert sessions[0]["readonly"] is False

    def test_named_session_always_visible(self, repo):
        """名称已由其它路径写入（name != remote_session_id）→ 保持可见。"""
        _make_session(repo, "u-raw", name="张三", msg_type=0)
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1 and sessions[0]["name"] == "张三"

    def test_group_session_still_visible(self, repo):
        """回归：群会话不受收敛式过滤影响。"""
        repo.upsert_channel_group(
            {
                "id": f"{ACCOUNT_ID}:r1",
                "account_id": ACCOUNT_ID,
                "room_id": "r1",
                "nickname": "客户群A",
                "room_url": "http://cdn/room.png",
            }
        )
        _make_session(repo, "r1", msg_type=1)
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["name"] == "客户群A"
        assert sessions[0]["avatar"] == "http://cdn/room.png"
        assert sessions[0]["entityKind"] == "group"

    def test_search_matches_app_name(self, repo):
        """搜索应能命中应用名（`ca.name LIKE ?`）。"""
        _make_app(repo, app_id=LONG_APP_ID, name="AI数字员工")
        _make_session(repo, LONG_APP_ID, msg_type=107)
        assert len(repo.list_sessions(account_id=ACCOUNT_ID, search="数字")) == 1
        assert repo.list_sessions(account_id=ACCOUNT_ID, search="不存在的关键词") == []

    def test_empty_remote_session_id_not_hijacked_by_app(self, repo):
        """BUG-1 回归：`remote_session_id=''` 的真人会话不得被 `app_open_id=''` 冒名。

        三路 JOIN 里 `ca.app_open_id = cs.remote_session_id` 在两侧同为空串时
        `'' = ''` 恒真，会把无关应用的 name / avatar 盖到真人会话上；而
        `entityKind` / `readonly` 仍由 `cs.msg_type` 派生（person / False），
        前端不显示「应用」徽标 —— 用户看到「一个叫某应用的真人好友」。
        修复：三路 JOIN 一律 `NULLIF(cs.remote_session_id, '')`。
        """
        _make_app(
            repo,
            app_id=LONG_APP_ID,
            app_open_id="",  # ← 与真人会话的空串 remote_session_id 撞车的关键条件
            name="AI数字员工",
            avatar="http://cdn/ai.png",
            app_type=2,
        )
        # 演示种子数据形态：remote_session_id 为空串，但名称已由同步层写入。
        _make_session(repo, "", name="张三", msg_type=0)

        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        sess = sessions[0]
        assert sess["name"] == "张三", "真人会话名被应用冒名覆盖"
        assert sess["avatar"] == "", "真人会话头像被应用冒名覆盖"
        # 语义字段本就正确，正因如此前端无从察觉被冒名 —— 一并钉住防回归。
        assert sess["entityKind"] == "person"
        assert sess["readonly"] is False
        assert sess["appType"] == 0

    def test_empty_remote_session_id_not_hijacked_by_contact_or_group(self, repo):
        """BUG-1 同类收口：`user_id=''` 的联系人 / `room_id=''` 的群同样不得冒名。"""
        _make_contact(repo, "", nickname="空ID联系人", avatar="http://cdn/ghost.png")
        repo.upsert_channel_group(
            {
                "id": f"{ACCOUNT_ID}:empty-room",
                "account_id": ACCOUNT_ID,
                "room_id": "",
                "nickname": "空ID群",
                "room_url": "http://cdn/ghost-room.png",
            }
        )
        _make_session(repo, "", name="张三", msg_type=0)

        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["name"] == "张三"
        assert sessions[0]["avatar"] == ""

    def test_mixed_list_only_resolved_shown(self, repo):
        """混合场景：仅名称可解析的会话进入列表，其余静默隐藏。"""
        _make_app(repo, app_id=LONG_APP_ID, name="AI数字员工")
        _make_session(repo, LONG_APP_ID, msg_type=107)
        _make_session(repo, "9000001", msg_type=103)
        _make_session(repo, "9000002", msg_type=6)
        names = [s["name"] for s in repo.list_sessions(account_id=ACCOUNT_ID)]
        assert names == ["AI数字员工"]


# --------------------------------------------------------------------------- #
# 6. DTO 层：row_to_session 新增语义字段
# --------------------------------------------------------------------------- #
class TestRowToSessionSemanticFields:
    def _row(self, **over) -> dict:
        row = {
            "id": f"{ACCOUNT_ID}:s1",
            "account_id": ACCOUNT_ID,
            "contact_id": None,
            "remote_session_id": LONG_APP_ID,
            "name": "AI数字员工",
            "channel": "企业微信",
            "channel_type": "wecom",
            "last_message": "",
            "last_time": "",
            "unread_count": 0,
            "read_status": "unread",
            "hosted_status": "unhosted",
            "hosted_bot_id": None,
            "owner": "",
            "online_status": "online",
            "session_type": "应用",
            "external_tag": "内部",
            "add_time": "",
            "hosting_chain": "-",
            "msg_type": 107,
            "app_type": 2,
        }
        row.update(over)
        return row

    def test_app_row_fields(self):
        dto = row_to_session(self._row())
        assert dto["msgType"] == 107
        assert dto["entityKind"] == "app"
        assert dto["readonly"] is True
        assert dto["appType"] == 2

    def test_person_row_fields(self):
        dto = row_to_session(self._row(msg_type=0, app_type=None, session_type="好友"))
        assert dto["entityKind"] == "person"
        assert dto["readonly"] is False
        assert dto["appType"] == 0

    def test_service_row_is_not_readonly(self):
        """msg_type=6（开放平台 / AI数字员工）实测可发消息，不得置只读。"""
        dto = row_to_session(self._row(msg_type=6, app_type=None))
        assert dto["entityKind"] == "service"
        assert dto["readonly"] is False

    def test_missing_columns_tolerated(self):
        """老数据行缺 `msg_type` / `app_type` 列时不得抛 KeyError。"""
        row = self._row()
        row.pop("msg_type")
        row.pop("app_type")
        dto = row_to_session(row)
        assert dto["entityKind"] == "person" and dto["readonly"] is False


# --------------------------------------------------------------------------- #
# 7. 消息气泡头像：应用分支按会话维度解析
# --------------------------------------------------------------------------- #
class TestResolveSenderAvatarForApp:
    def test_app_avatar_by_session_dimension(self, repo):
        """应用消息 `sender_id == remote_session_id`，须按会话维度取应用头像。"""
        _make_app(repo, app_id=LONG_APP_ID, avatar="http://cdn/ai.png")
        conv = _make_session(repo, LONG_APP_ID, msg_type=107)
        avatar = repo._resolve_sender_avatar(
            ACCOUNT_ID, "inbound", LONG_APP_ID, conv
        )
        assert avatar == "http://cdn/ai.png"

    def test_app_avatar_via_open_id_session(self, repo):
        _make_app(repo, app_id=LONG_APP_ID, app_open_id=SHORT_OPEN_ID, avatar="http://cdn/a.png")
        conv = _make_session(repo, SHORT_OPEN_ID, msg_type=3)
        assert repo._resolve_sender_avatar(ACCOUNT_ID, "inbound", SHORT_OPEN_ID, conv) == "http://cdn/a.png"

    def test_app_branch_is_terminal_on_miss(self, repo):
        """应用分支为终态：未命中返回空串，**不得**回落联系人（ID 空间不重叠）。"""
        _make_contact(repo, LONG_APP_ID, nickname="误命中", avatar="http://cdn/wrong.png")
        conv = _make_session(repo, LONG_APP_ID, msg_type=107)
        assert repo._resolve_sender_avatar(ACCOUNT_ID, "inbound", LONG_APP_ID, conv) == ""

    def test_non_app_session_falls_back_to_contact(self, repo):
        """回归：非应用会话仍走联系人头像分支。"""
        _make_contact(repo, "u1", nickname="张三", avatar="http://cdn/u1.png")
        conv = _make_session(repo, "u1", name="张三", msg_type=0)
        assert repo._resolve_sender_avatar(ACCOUNT_ID, "inbound", "u1", conv) == "http://cdn/u1.png"

    def test_outbound_still_uses_account_avatar(self, repo, backend):
        """回归：outbound 分支优先级最高，不受应用分支影响。"""
        # channel_accounts 的 channel / account_name / status / bound_bot 均为 NOT NULL 且无默认值
        backend.execute(
            "INSERT OR REPLACE INTO channel_accounts"
            "(id, channel, account_name, status, bound_bot, avatar) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ACCOUNT_ID, "wxwork", "本账号", "online", "", "http://cdn/me.png"),
        )
        conv = _make_session(repo, LONG_APP_ID, msg_type=107)
        assert repo._resolve_sender_avatar(ACCOUNT_ID, "outbound", LONG_APP_ID, conv) == "http://cdn/me.png"


# --------------------------------------------------------------------------- #
# 8. 发送目标解析：只读拦截边界
# --------------------------------------------------------------------------- #
class _FakeRepo:
    """`_resolve_target` 用的最小仓储替身（与 test_ipad_sync 保持同一形态）。"""

    def __init__(self, contacts=None, groups=None, sessions=None):
        self._contacts = {c["id"]: c for c in (contacts or [])}
        self._groups = {g["id"]: g for g in (groups or [])}
        self._group_room = {g["room_id"]: g for g in (groups or [])}
        self._sessions = {s["id"]: s for s in (sessions or [])}

    def get_contact_by_id(self, cid):
        return self._contacts.get(cid)

    def get_group_by_room_id(self, account_id, room_id):
        return self._group_room.get(room_id)

    def get_group_by_id(self, gid):
        return self._groups.get(gid)

    def get_session_by_id(self, sid):
        return self._sessions.get(sid)


class TestResolveTargetReadonly:
    @pytest.mark.parametrize("msg_type", sorted(APP_MSG_TYPES))
    def test_app_family_rejected(self, msg_type):
        """应用族 {3, 103, 107} 一律拒发（防御性兜底，前端已置灰）。"""
        repo = _FakeRepo(
            sessions=[
                {
                    "id": "acc:s",
                    "msg_type": msg_type,
                    "remote_session_id": LONG_APP_ID,
                    "contact_id": None,
                }
            ]
        )
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync._resolve_target(repo, "acc", "session", "acc:s")

    def test_msg_type_6_is_sendable(self):
        """⚠️ 对拍结论：msg_type=6 实测有 111 条真实 outbound，**必须放行**。"""
        repo = _FakeRepo(
            contacts=[{"id": "acc:c6", "user_id": "u6"}],
            sessions=[
                {
                    "id": "acc:s6",
                    "msg_type": 6,
                    "remote_session_id": "u6",
                    "contact_id": "acc:c6",
                }
            ],
        )
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "session", "acc:s6")
        assert uid == "u6" and is_room is False

    def test_msg_type_0_is_sendable(self):
        repo = _FakeRepo(
            contacts=[{"id": "acc:c0", "user_id": "u0"}],
            sessions=[
                {
                    "id": "acc:s0",
                    "msg_type": 0,
                    "remote_session_id": "u0",
                    "contact_id": "acc:c0",
                }
            ],
        )
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "session", "acc:s0")
        assert uid == "u0" and is_room is False


# --------------------------------------------------------------------------- #
# 9. 同步层：应用同步 / 会话规范化 / vid 补拉
# --------------------------------------------------------------------------- #
class TestSyncCorpApps:
    def test_saves_apps(self, repo, monkeypatch):
        monkeypatch.setattr(
            ipad_client,
            "get_corp_wx_app",
            lambda uuid: [
                {
                    "appId": LONG_APP_ID,
                    "appOpenId": SHORT_OPEN_ID,
                    "corpid": "1970325134",
                    "name": "AI数字员工",
                    "avatar": "http://cdn/ai.png",
                    "appType": 2,
                    "description": "",
                    "homeInfo": "",
                    "lastModTime": 1,
                    "extra": {},
                }
            ],
        )
        saved = ipad_sync._sync_corp_apps(repo, "uuid", ACCOUNT_ID)
        assert saved == 1
        assert repo.get_app_by_session_id(ACCOUNT_ID, SHORT_OPEN_ID) is not None

    def test_degrades_on_protocol_error(self, repo, monkeypatch):
        """§9-U1：getCorpWxApp 当前 404，必须降级返回 0，不抛、不阻断其余同步路。"""

        def _boom(uuid):
            raise ipad_client.IPadProtocolError("HTTP 404 Not Found")

        monkeypatch.setattr(ipad_client, "get_corp_wx_app", _boom)
        assert ipad_sync._sync_corp_apps(repo, "uuid", ACCOUNT_ID) == 0
        assert repo.list_apps(ACCOUNT_ID) == []

    def test_skips_entries_without_keys(self, repo, monkeypatch):
        monkeypatch.setattr(
            ipad_client, "get_corp_wx_app", lambda uuid: [{"name": "无ID"}]
        )
        assert ipad_sync._sync_corp_apps(repo, "uuid", ACCOUNT_ID) == 0


class TestUpsertSessionAppBranch:
    def test_app_session_contact_id_is_none(self, repo):
        """修 PRD F4：应用会话**绝不能**伪造 `contact_id`，否则跨语义误命中 + 污染统计。"""
        _make_app(repo, app_id=LONG_APP_ID, name="AI数字员工")
        ipad_sync._upsert_session(
            repo,
            ACCOUNT_ID,
            "企业微信",
            "wecom",
            {"sessionid": LONG_APP_ID, "msgtype": 107},
        )
        row = repo.get_session_by_id(f"{ACCOUNT_ID}:{LONG_APP_ID}")
        assert row is not None
        assert row["contact_id"] in (None, "")
        assert row["name"] == "AI数字员工"
        assert row["session_type"] == "应用"

    def test_app_session_name_stays_raw_when_app_missing(self, repo):
        """应用未同步（404 期间）→ 名称保持 sessionid，由收敛式过滤隐藏。"""
        ipad_sync._upsert_session(
            repo,
            ACCOUNT_ID,
            "企业微信",
            "wecom",
            {"sessionid": LONG_APP_ID, "msgtype": 103},
        )
        row = repo.get_session_by_id(f"{ACCOUNT_ID}:{LONG_APP_ID}")
        assert row["name"] == LONG_APP_ID
        assert row["contact_id"] in (None, "")
        # 关键：不会以裸数字暴露给用户
        assert repo.list_sessions(account_id=ACCOUNT_ID) == []

    def test_vid_session_keeps_contact_id(self, repo):
        """回归：vid 族（0 / 6）仍按 `{account_id}:{sessionid}` 关联联系人。"""
        _make_contact(repo, TEAM_VID, nickname="企业微信团队")
        ipad_sync._upsert_session(
            repo,
            ACCOUNT_ID,
            "企业微信",
            "wecom",
            {"sessionid": TEAM_VID, "msgtype": 0},
        )
        row = repo.get_session_by_id(f"{ACCOUNT_ID}:{TEAM_VID}")
        assert row["contact_id"] == f"{ACCOUNT_ID}:{TEAM_VID}"
        assert row["name"] == "企业微信团队"


class TestBackfillUnknownVids:
    def test_backfills_and_surfaces_session(self, repo, monkeypatch):
        monkeypatch.setattr(
            ipad_client,
            "get_user_info_by_vids",
            lambda uuid, vids: [
                {
                    "user_id": TEAM_VID,
                    "name": "企业微信团队",
                    "nickname": "企业微信团队",
                    "avatar": "http://cdn/team.png",
                    "corpid": "1970325134",
                    "acctid": "",
                    "raw": {},
                }
            ],
        )
        items = [{"sessionid": TEAM_VID, "msgtype": 0}]
        saved = ipad_sync._backfill_unknown_vids(
            repo, "uuid", ACCOUNT_ID, "企业微信", "wecom", items
        )
        assert saved == 1
        # 补拉后再规范化会话 → 名称与头像自动浮现（查询层零改动）
        ipad_sync._upsert_session(repo, ACCOUNT_ID, "企业微信", "wecom", items[0])
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["name"] == "企业微信团队"
        assert sessions[0]["avatar"] == "http://cdn/team.png"

    def test_skips_app_family(self, repo, monkeypatch):
        """应用族不走 vid 补拉（ID 空间不同，调用只会浪费配额）。"""

        def _boom(uuid, vids):  # pragma: no cover - 不应被调用
            raise AssertionError("应用族不应触发 GetUserInfoByVids")

        monkeypatch.setattr(ipad_client, "get_user_info_by_vids", _boom)
        items = [{"sessionid": LONG_APP_ID, "msgtype": 107}]
        assert (
            ipad_sync._backfill_unknown_vids(
                repo, "uuid", ACCOUNT_ID, "企业微信", "wecom", items
            )
            == 0
        )

    def test_skips_already_known_contacts(self, repo, monkeypatch):
        def _boom(uuid, vids):  # pragma: no cover - 不应被调用
            raise AssertionError("已有联系人不应重复补拉")

        monkeypatch.setattr(ipad_client, "get_user_info_by_vids", _boom)
        _make_contact(repo, TEAM_VID, nickname="企业微信团队")
        items = [{"sessionid": TEAM_VID, "msgtype": 0}]
        assert (
            ipad_sync._backfill_unknown_vids(
                repo, "uuid", ACCOUNT_ID, "企业微信", "wecom", items
            )
            == 0
        )

    def test_degrades_on_protocol_error(self, repo, monkeypatch):
        def _boom(uuid, vids):
            raise ipad_client.IPadProtocolError("HTTP 500")

        monkeypatch.setattr(ipad_client, "get_user_info_by_vids", _boom)
        items = [{"sessionid": TEAM_VID, "msgtype": 6}]
        assert (
            ipad_sync._backfill_unknown_vids(
                repo, "uuid", ACCOUNT_ID, "企业微信", "wecom", items
            )
            == 0
        )

    def test_skips_nameless_hits(self, repo, monkeypatch):
        """协议命中但无名称 → 不落库（落了也只是空名，不如交给收敛式过滤隐藏）。"""
        monkeypatch.setattr(
            ipad_client,
            "get_user_info_by_vids",
            lambda uuid, vids: [{"user_id": TEAM_VID, "name": "", "nickname": ""}],
        )
        items = [{"sessionid": TEAM_VID, "msgtype": 0}]
        assert (
            ipad_sync._backfill_unknown_vids(
                repo, "uuid", ACCOUNT_ID, "企业微信", "wecom", items
            )
            == 0
        )

    def test_contact_type_is_service_no_stat_pollution(self, repo, monkeypatch):
        """补拉身份落 `type='service'`，不污染 customer / inner 统计口径。"""
        monkeypatch.setattr(
            ipad_client,
            "get_user_info_by_vids",
            lambda uuid, vids: [
                {"user_id": TEAM_VID, "name": "企业微信团队", "nickname": "企业微信团队"}
            ],
        )
        ipad_sync._backfill_unknown_vids(
            repo, "uuid", ACCOUNT_ID, "企业微信", "wecom", [{"sessionid": TEAM_VID, "msgtype": 0}]
        )
        row = repo.get_contact_by_id(f"{ACCOUNT_ID}:{TEAM_VID}")
        assert row is not None
        assert (row.get("type") or row.get("contactType")) == "service"
        assert (row.get("source") or "") == "vid_backfill"

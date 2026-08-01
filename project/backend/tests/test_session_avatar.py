"""「渠道会话管理头像显示」改动验证 —— 测试套件。

覆盖本轮改动：
1. `list_sessions` 返回的会话字典必须包含 `avatar` 字段：
   - 单聊会话：avatar 取自关联联系人的真实头像 URL（cc.avatar）。
   - 群聊会话：avatar 为空时 fallback 到群 `room_url`（cg.room_url）。
   - 无关联对象：avatar 兜底为空串 ''。
2. `row_to_group` 返回的群字典必须包含 `avatar` 字段，且
   当 avatar 列为空但 room_url 有值时 fallback 到 room_url。

⚠️ wecom_app_display 变更说明：`list_sessions` 的硬编码 `WHERE cs.msg_type != 3`
已被**收敛式过滤**取代（「名称解析得出才展示」）。因此应用会话不再按 msg_type
一刀切排除，而是「名称未解析才隐藏」—— 对应断言已同步更新，语义等价于改动前
（getCorpWxApp 未上线期间可见结果完全一致，零视觉回归）。
详见 `tests/test_wecom_app_display.py::TestConvergentFiltering`。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_session_avatar.py -q -p no:cacheprovider
"""
from __future__ import annotations

import os

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest

from app import schema as schema_mod
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.repositories import (
    ChannelMgmtRepository,
    row_to_session,
    row_to_group,
)


# --------------------------------------------------------------------------- #
# 测试夹具
# --------------------------------------------------------------------------- #
@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_session_avatar.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def repo(backend):
    """基于隔离后端的渠道会话管理仓储。"""
    return ChannelMgmtRepository(backend)


# --------------------------------------------------------------------------- #
# 1. 行 -> DTO 映射单测（纯函数，无需 DB）
# --------------------------------------------------------------------------- #
class TestRowToSessionAvatar:
    def _full_row(self, **over) -> dict:
        row = {
            "id": "acc:ses1",
            "account_id": "acc",
            "contact_id": None,
            "remote_session_id": "u1",
            "name": "会话1",
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
            "session_type": "好友",
            "external_tag": "外部",
            "add_time": "",
            "hosting_chain": "-",
        }
        row.update(over)
        return row

    def test_avatar_present_in_dict(self):
        row = self._full_row(avatar="http://cdn/session.png")
        assert row_to_session(row)["avatar"] == "http://cdn/session.png"

    def test_avatar_defaults_to_empty_string_when_absent(self):
        row = self._full_row()  # 无 avatar 键
        assert row_to_session(row)["avatar"] == ""


class TestRowToGroupAvatar:
    def _full_row(self, **over) -> dict:
        row = {
            "id": "acc:r1",
            "account_id": "acc",
            "room_id": "r1",
            "group_type": "customer_group",
            "nickname": "群1",
            "total": 3,
            "room_url": "http://cdn/group.png",
            "notice_content": "",
            "create_time": "",
            "update_time": "",
        }
        row.update(over)
        return row

    def test_avatar_present_takes_precedence_over_room_url(self):
        row = self._full_row(avatar="http://cdn/real.png")
        assert row_to_group(row)["avatar"] == "http://cdn/real.png"

    def test_avatar_absent_falls_back_to_room_url(self):
        row = self._full_row()  # 无 avatar 键
        assert row_to_group(row)["avatar"] == "http://cdn/group.png"

    def test_avatar_empty_string_falls_back_to_room_url(self):
        row = self._full_row(avatar="")
        assert row_to_group(row)["avatar"] == "http://cdn/group.png"

    def test_both_empty_yields_empty_string(self):
        row = self._full_row(avatar="", room_url="")
        assert row_to_group(row)["avatar"] == ""


# --------------------------------------------------------------------------- #
# 2. list_sessions 集成测（内存 SQLite backend + 真实 upsert 方法）
# --------------------------------------------------------------------------- #
ACCOUNT_ID = "acc-qa"


def _make_contact(repo: ChannelMgmtRepository, user_id: str, avatar: str, name: str = "联系人") -> str:
    cid = f"{ACCOUNT_ID}:{user_id}"
    repo.upsert_channel_contact(
        {
            "id": cid,
            "account_id": ACCOUNT_ID,
            "channel": "企业微信",
            "channel_type": "wecom",
            "name": name,
            "nickname": name,
            "type": "customer",
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


def _make_session(
    repo: ChannelMgmtRepository,
    sid: str,
    *,
    contact_id: str | None = None,
    remote_session_id: str,
    name: str = "会话",
    msg_type: int = 0,
) -> str:
    sess_id = f"{ACCOUNT_ID}:{sid}"
    repo.upsert_channel_session(
        {
            "id": sess_id,
            "account_id": ACCOUNT_ID,
            "contact_id": contact_id,
            "name": name,
            "channel": "企业微信",
            "channel_type": "wecom",
            "remote_session_id": remote_session_id,
            "msg_type": msg_type,
        }
    )
    return sess_id


def _make_group(repo: ChannelMgmtRepository, room_id: str, room_url: str) -> str:
    gid = f"{ACCOUNT_ID}:{room_id}"
    repo.upsert_channel_group(
        {
            "id": gid,
            "account_id": ACCOUNT_ID,
            "room_id": room_id,
            "nickname": f"群{room_id}",
            "room_url": room_url,
        }
    )
    return gid


class TestListSessionsAvatar:
    def test_single_chat_avatar_from_contact(self, repo):
        """单聊会话：avatar 应取关联联系人的真实头像 URL。"""
        cid = _make_contact(repo, "u1", "http://cdn/contact-u1.png")
        _make_session(
            repo, "ses1", contact_id=cid, remote_session_id="u1", name="联系人"
        )
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        sess = sessions[0]
        assert sess["avatar"] == "http://cdn/contact-u1.png"
        # 顺便确认 JOIN 也带出了真实昵称（非 raw sessionid）
        assert sess["name"] == "联系人"

    def test_group_chat_avatar_falls_back_to_room_url(self, repo):
        """群聊会话：无联系人头像时 avatar 应 fallback 到群 room_url。"""
        _make_group(repo, "r1", "http://cdn/group-r1.png")
        # 群会话：remote_session_id 对应群 room_id，contact_id 置空
        _make_session(repo, "gses1", contact_id=None, remote_session_id="r1")
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["avatar"] == "http://cdn/group-r1.png"

    def test_no_linked_object_avatar_is_empty(self, repo):
        """无关联联系人/群的会话：avatar 兜底为空串。"""
        _make_session(repo, "orphan", contact_id=None, remote_session_id="nobody")
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["avatar"] == ""

    def test_unresolved_app_session_excluded(self, repo):
        """应用类会话（msg_type=3）名称未解析时应被过滤，不进入列表。

        「未解析」的判据是 `name == remote_session_id`（协议只给了裸 sessionid）。
        这与改动前 `WHERE cs.msg_type != 3` 在 getCorpWxApp 未上线期间的可见结果
        完全一致 —— 零视觉回归。
        """
        _make_session(
            repo,
            "app",
            contact_id=None,
            remote_session_id="app-room",
            name="app-room",
            msg_type=3,
        )
        assert repo.list_sessions(account_id=ACCOUNT_ID) == []

    def test_resolved_app_session_surfaces(self, repo):
        """应用信息同步到位后（channel_apps 命中），应用会话应自动浮现。"""
        repo.upsert_channel_app(
            {
                "account_id": ACCOUNT_ID,
                "app_id": "app-room",
                "app_open_id": "10223",
                "name": "企业微信团队",
                "avatar": "http://cdn/app-room.png",
                "app_type": 1,
            }
        )
        _make_session(
            repo,
            "app",
            contact_id=None,
            remote_session_id="app-room",
            name="app-room",
            msg_type=3,
        )
        sessions = repo.list_sessions(account_id=ACCOUNT_ID)
        assert len(sessions) == 1
        assert sessions[0]["name"] == "企业微信团队"
        assert sessions[0]["avatar"] == "http://cdn/app-room.png"
        assert sessions[0]["entityKind"] == "app"
        assert sessions[0]["readonly"] is True


class TestListGroupsAvatarRegression:
    def test_list_groups_returns_avatar_field(self, repo):
        """回归：list_groups 经 row_to_group 映射，群字典应含 avatar（fallback room_url）。"""
        _make_group(repo, "r2", "http://cdn/group-r2.png")
        groups = repo.list_groups(account_id=ACCOUNT_ID)
        assert len(groups) == 1
        assert groups[0]["avatar"] == "http://cdn/group-r2.png"

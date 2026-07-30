"""回归测试：poll_wecom 在 loginType==2 时按 ipad_uuid 幂等落库。

复现并守卫本次 Bug：清空渠道账号后用真实微信扫码，前端因高频轮询在
loginType==2 期间并发多次调用 /poll，旧实现无条件 INSERT，导致落库出
多个完全相同账号。修复后：同一 uuid 仅创建一次账号。

用例：
1. 顺序 4 次 poll(loginType==2) -> 仅 1 个账号。
2. 并发 8 个线程同时 poll(loginType==2) -> 仅 1 个账号，且 trigger_sync 仅触发一次。
3. poll(loginType!=2) 不创建账号。
4. get_account_by_ipad_uuid 对空串 / 未知 uuid 返回 None。
5. 数据库存在 ipad_uuid 部分唯一索引作为兜底。

全部用例使用 unittest.mock 打桩，不触发任何真实网络请求；每个用例使用独立临时 SQLite 库。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_poll_idempotent.py -v -p no:cacheprovider
"""
from __future__ import annotations

import os
import threading

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次），避免任何真实网络。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

from unittest.mock import MagicMock, patch

import pytest

from app import ipad_client, ipad_sync
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
import app.schema as schema_mod
from app.repositories import ChannelMgmtRepository
from app.routers import channel_hosting
from app.schemas import WecomHostPollRequest


UUID = "dup-uuid-0001"
USER_INFO = {"nickname": "通天草-林璇", "userId": 16881234567890}


@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_test.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


def _patch_poll(monkeypatch, login_type: int = 2):
    """打桩 ipad_client.poll_wecom 返回指定 loginType。"""

    def fake_poll(uuid: str) -> dict:
        return {"loginType": login_type, "userInfo": dict(USER_INFO), "mock": False}

    monkeypatch.setattr(ipad_client, "poll_wecom", fake_poll)


def _stub_sync(monkeypatch) -> MagicMock:
    """打桩 trigger_sync / register_callback（避免真实网络），返回可断言的 mock。"""
    trigger = MagicMock(return_value=True)
    register = MagicMock(return_value={"registered": False})
    monkeypatch.setattr(ipad_sync, "trigger_sync", trigger)
    monkeypatch.setattr(ipad_sync, "register_callback", register)
    return trigger


def _count_accounts(be) -> int:
    return int(be.query_one("SELECT COUNT(*) AS c FROM channel_accounts")["c"])


# --------------------------------------------------------------------------- #
# 用例 1：顺序 4 次 poll(loginType==2) -> 仅 1 个账号
# --------------------------------------------------------------------------- #
def test_sequential_polls_create_single_account(backend, monkeypatch):
    _patch_poll(monkeypatch, login_type=2)
    trigger = _stub_sync(monkeypatch)
    ipad_client.MockState[UUID] = {"team_id": "team-x", "channel_type": "wecom"}

    for _ in range(4):
        res = channel_hosting.poll_wecom(WecomHostPollRequest(uuid=UUID))
        assert res["account"]["ipadUuid"] == UUID

    assert _count_accounts(backend) == 1
    trigger.assert_called_once()


# --------------------------------------------------------------------------- #
# 用例 2：并发 8 个线程同时 poll(loginType==2) -> 仅 1 个账号
# --------------------------------------------------------------------------- #
def test_concurrent_polls_create_single_account(backend, monkeypatch):
    _patch_poll(monkeypatch, login_type=2)
    trigger = _stub_sync(monkeypatch)
    ipad_client.MockState[UUID] = {"team_id": "team-x", "channel_type": "wecom"}

    results: list[dict] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait()
            res = channel_hosting.poll_wecom(WecomHostPollRequest(uuid=UUID))
            results.append(res)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"并发 poll 抛异常：{errors}"
    assert _count_accounts(backend) == 1, "并发 poll 产生重复账号"
    # 所有并发 poll 返回的是同一个账号（幂等）
    ids = {r["account"]["id"] for r in results}
    assert ids == {next(iter(ids))}
    trigger.assert_called_once()


# --------------------------------------------------------------------------- #
# 用例 3：poll(loginType!=2) 不创建账号
# --------------------------------------------------------------------------- #
def test_poll_without_logged_in_creates_no_account(backend, monkeypatch):
    _patch_poll(monkeypatch, login_type=1)
    _stub_sync(monkeypatch)
    ipad_client.MockState[UUID] = {"team_id": "team-x", "channel_type": "wecom"}

    res = channel_hosting.poll_wecom(WecomHostPollRequest(uuid=UUID))
    assert "account" not in res
    assert _count_accounts(backend) == 0


# --------------------------------------------------------------------------- #
# 用例 4：get_account_by_ipad_uuid 边界
# --------------------------------------------------------------------------- #
def test_get_account_by_ipad_uuid_edges(backend):
    repo = ChannelMgmtRepository(backend)
    acc = repo.create_account_with_ipad(
        channel_type="wecom", protocol="ipad", team_id="", name="x",
        ipad_uuid=UUID, ipad_user_info=USER_INFO,
    )
    assert repo.get_account_by_ipad_uuid(UUID)["id"] == acc["id"]
    assert repo.get_account_by_ipad_uuid("") is None
    assert repo.get_account_by_ipad_uuid("unknown-uuid") is None


# --------------------------------------------------------------------------- #
# 用例 5：ipad_uuid 部分唯一索引存在（防御纵深）
# --------------------------------------------------------------------------- #
def test_ipad_uuid_unique_index_exists(backend):
    row = backend.query_one(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name='uq_channel_accounts_ipad_uuid'"
    )
    assert row is not None, "ipad_uuid 唯一索引未创建"

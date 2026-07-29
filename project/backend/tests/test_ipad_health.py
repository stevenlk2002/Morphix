"""「企业微信 iPad 协议：自动登录 + 健康巡检」后端逻辑单元测试。

覆盖 ipad_health / repositories.ChannelMgmtRepository 的关键路径：
1. vid 落库（userId int -> vid str）。
2. _healthy 边界判定。
3. 探活健康：CONNECTED+loginType=3 -> 标记 online/hosted。
4. 无 vid 不自动重连：持续异常、 vid 为空 -> offline/error，且 init 从未调用。
5. 有 vid 自动重连成功：达阈值 -> init+automatic_login -> online/hosted、写新 uuid、触发同步。
6. mock 模式跳过真实探测：_mode()=='mock' -> 标记 online/hosted，且不调 get_run_client_info。
7. get_health_snapshot 连续失败计数正确。

全部用例使用 unittest.mock 打桩，不触发任何真实网络请求；每个用例使用独立临时 SQLite 库。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_ipad_health.py -v -p no:cacheprovider
"""
from __future__ import annotations

import os

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次），避免任何真实网络。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

from unittest.mock import patch

import pytest

from app import ipad_client, ipad_health, ipad_sync
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.repositories import ChannelMgmtRepository, row_to_account
import app.schema as schema_mod


# --------------------------------------------------------------------------- #
# 测试夹具
# --------------------------------------------------------------------------- #
@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_test.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture(autouse=True)
def _reset_failures():
    """清理进程内连续失败计数，避免用例之间相互干扰。"""
    ipad_health._failures.clear()
    yield
    ipad_health._failures.clear()


# --------------------------------------------------------------------------- #
# 辅助函数
# --------------------------------------------------------------------------- #
def _seed_account(
    be,
    *,
    vid: str = "",
    initial_status: str = "online",
    initial_host: str = "hosted",
) -> dict:
    """落库一个 ipad 协议账号，并返回用于 mock `list_ipad_hosted_accounts` 的 dict。

    返回 dict 的 id 与真实库行一致，从而 `_tick` 中的 `_mark` 写库可被查库断言。
    """
    repo = ChannelMgmtRepository(be)
    user_info = {"userId": vid} if vid else {}
    acc = repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="",
        name="健康巡检测试账号",
        ipad_uuid="seed-uuid-1",
        ipad_user_info=user_info,
    )
    acc_id = acc["id"]
    if initial_status != "online" or initial_host != "hosted":
        repo.update_account_health(acc_id, initial_status, initial_host)
    return {
        "id": acc_id,
        "name": "健康巡检测试账号",
        "ipadUuid": "seed-uuid-1",
        "vid": vid,
        "hostStatus": initial_host,
        "status": initial_status,
    }


def _get_account_row(be, acc_id: str) -> dict:
    return be.query_one("SELECT * FROM channel_accounts WHERE id = ?", (acc_id,))


# --------------------------------------------------------------------------- #
# 用例 1：vid 落库（userId int -> str(vid)）
# --------------------------------------------------------------------------- #
def test_create_account_with_ipad_extracts_vid_from_userId(backend):
    repo = ChannelMgmtRepository(backend)
    acc = repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="",
        name="测试",
        ipad_uuid="u-abc",
        ipad_user_info={"userId": 16881234567890, "nickname": "测试"},
    )
    # 1) 返回 DTO 含正确 vid（str 化）
    assert acc["vid"] == "16881234567890"
    # 2) 查库 -> row_to_account 得到 vid == str(userId)
    row = _get_account_row(backend, acc["id"])
    assert row_to_account(row)["vid"] == "16881234567890"
    assert row["vid"] == "16881234567890"


# --------------------------------------------------------------------------- #
# 用例 2：_healthy 边界判定
# --------------------------------------------------------------------------- #
def test_healthy_boundaries():
    assert ipad_health._healthy("CONNECTED", 3) is True
    assert ipad_health._healthy("CONNECTED", 2) is False
    assert ipad_health._healthy("CLOSED", 3) is False
    assert ipad_health._healthy("RECONNECTING", 3) is False


# --------------------------------------------------------------------------- #
# 用例 3：探活健康 -> online/hosted
# --------------------------------------------------------------------------- #
def test_tick_marks_healthy_account_online(backend):
    rec = _seed_account(backend, initial_status="offline", initial_host="pending")
    with (
        patch("app.ipad_client._mode", return_value="real"),
        patch(
            "app.ipad_client.get_run_client_info",
            return_value={"longLinkState": "CONNECTED", "loginType": 3},
        ),
        patch(
            "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
            return_value=[rec],
        ),
    ):
        ipad_health._tick(3)

    row = _get_account_row(backend, rec["id"])
    assert row["status"] == "online"
    assert row["host_status"] == "hosted"


# --------------------------------------------------------------------------- #
# 用例 4：无 vid 不自动重连 -> offline/error 且 init 从未被调用
# --------------------------------------------------------------------------- #
def test_tick_no_vid_skips_auto_recover(backend):
    rec = _seed_account(backend, vid="", initial_status="offline", initial_host="pending")
    with (
        patch("app.ipad_client._mode", return_value="real"),
        patch(
            "app.ipad_client.get_run_client_info",
            side_effect=ipad_client.IPadProtocolError("实例掉线"),
        ),
        patch("app.ipad_client.init") as mock_init,
        patch("app.ipad_client.automatic_login") as mock_login,
        patch("app.ipad_sync.trigger_sync") as mock_trigger,
        patch("app.ipad_sync.register_callback"),
        patch(
            "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
            return_value=[rec],
        ),
    ):
        for _ in range(3):
            ipad_health._tick(3)

    row = _get_account_row(backend, rec["id"])
    assert row["status"] == "offline"
    assert row["host_status"] == "error"
    # 无 vid -> 自动重连被跳过，init 绝不应被调用
    mock_init.assert_not_called()
    mock_login.assert_not_called()
    # 也绝不应触发同步
    mock_trigger.assert_not_called()


# --------------------------------------------------------------------------- #
# 用例 5：有 vid 自动重连成功
# --------------------------------------------------------------------------- #
def test_tick_with_vid_auto_recovers_successfully(backend):
    rec = _seed_account(
        backend, vid="16881234567890", initial_status="offline", initial_host="pending"
    )
    with (
        patch("app.ipad_client._mode", return_value="real"),
        patch(
            "app.ipad_client.get_run_client_info",
            side_effect=ipad_client.IPadProtocolError("实例掉线"),
        ),
        patch("app.ipad_client.init", return_value={"uuid": "new-uuid"}),
        patch(
            "app.ipad_client.automatic_login",
            return_value={"ok": True, "errmsg": "登陆成功"},
        ),
        patch("app.ipad_sync.trigger_sync") as mock_trigger,
        patch("app.ipad_sync.register_callback") as mock_register,
        patch(
            "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
            return_value=[rec],
        ),
    ):
        for _ in range(3):
            ipad_health._tick(3)

    row = _get_account_row(backend, rec["id"])
    assert row["status"] == "online"
    assert row["host_status"] == "hosted"
    # 自动重连写入了新 uuid
    assert row["ipad_uuid"] == "new-uuid"
    # 触发了同步与回调注册
    mock_trigger.assert_called_once_with(rec["id"])
    mock_register.assert_called_once_with(rec["id"])


# --------------------------------------------------------------------------- #
# 用例 6：mock 模式跳过真实探测
# --------------------------------------------------------------------------- #
def test_tick_mock_mode_skips_real_probe(backend):
    rec = _seed_account(backend, initial_status="offline", initial_host="pending")
    with (
        patch("app.ipad_client._mode", return_value="mock"),
        patch("app.ipad_client.get_run_client_info") as mock_info,
        patch(
            "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
            return_value=[rec],
        ),
    ):
        ipad_health._tick(3)

    row = _get_account_row(backend, rec["id"])
    assert row["status"] == "online"
    assert row["host_status"] == "hosted"
    # mock 模式不应发起任何真实探测调用
    mock_info.assert_not_called()


# --------------------------------------------------------------------------- #
# 用例 7：get_health_snapshot 连续失败计数
# --------------------------------------------------------------------------- #
def test_health_snapshot_reports_consecutive_failures(backend):
    rec = _seed_account(backend, initial_status="offline", initial_host="pending")
    with (
        patch("app.ipad_client._mode", return_value="real"),
        patch(
            "app.ipad_client.get_run_client_info",
            side_effect=ipad_client.IPadProtocolError("实例掉线"),
        ),
        patch(
            "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
            return_value=[rec],
        ),
    ):
        ipad_health._tick(3)  # 1 次探测失败

    snap = ipad_health.get_health_snapshot()
    assert len(snap) == 1
    assert snap[0]["id"] == rec["id"]
    assert snap[0]["consecutiveFailures"] == 1
    assert snap[0]["status"] == "offline"
    assert snap[0]["hostStatus"] == "pending"

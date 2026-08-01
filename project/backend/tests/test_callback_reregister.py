"""回调地址重注册 —— 测试套件（Bug：入向消息永久断裂，重启/隧道恢复后不自愈）。

根因：`SetCallbackUrl` 此前仅在两条路径触发——
1. 托管账号「首次创建」（channel_hosting poll 中 created==True）；
2. 健康巡检连续失败达阈值后的 `_recover()` 自动重连成功。

后端由 launchd KeepAlive 托管会频繁重启，而账号长连接一直 CONNECTED，
永远走不到 (2)；(1) 也只在重新扫码时发生。叠加内网穿透隧道掉线，协议侧
回调地址失效后再也不会被重新注册 → 对方回复的消息永久收不到。

修复：健康巡检在账号健康分支调用 `_ensure_callback()`，按
`{uuid|url|callbackType}` 身份键 + 重注册周期幂等地确保回调已注册；
失败则每轮重试，隧道恢复后自动补注册。

覆盖：
1. 账号健康且已配公网地址 → 首轮巡检即注册（后端重启自愈）；
2. 同一身份键在周期内不重复注册（不刷爆协议服务）；
3. 上次注册失败（隧道断）→ 每轮重试，隧道恢复后成功（自愈）；
4. 公网地址变更（换隧道域名）→ 强制重新注册；
5. 未配置 IPAD_CALLBACK_PUBLIC_URL → 完全跳过，不产生任何调用；
6. 回调注册失败不影响账号健康状态（不得误标 offline）；
7. 自动重连成功后清除注册记忆，强制下轮重注册（uuid 已轮换）；
8. 健康快照暴露 callbackRegistered，便于前端/运维定位入向断裂；
9. `ensure_callback_now()` 运维入口强制立即重注册。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest \
        tests/test_callback_reregister.py -q
"""
from __future__ import annotations

import os

# 必须在 import app 之前设定：settings 在导入时读取一次，避免任何真实网络。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

from dataclasses import replace
from unittest.mock import patch

import pytest

from app import ipad_client, ipad_health
import app.database as _db_mod
from app.database import SQLiteBackend, set_backend
from app.repositories import ChannelMgmtRepository
import app.schema as schema_mod

PUBLIC_URL = "https://tunnel-a.example.com/wxwork/callback"
PUBLIC_URL_B = "https://tunnel-b.example.com/wxwork/callback"


@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_test_cbreg.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture(autouse=True)
def _reset_state():
    """清理进程内失败计数与回调注册记忆，隔离用例。"""
    ipad_health._failures.clear()
    ipad_health._callback_state.clear()
    yield
    ipad_health._failures.clear()
    ipad_health._callback_state.clear()


@pytest.fixture
def account(backend):
    """已托管、在线的 iPad 账号，返回巡检快照形态的 dict。"""
    repo = ChannelMgmtRepository(backend)
    acc = repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="",
        name="回调重注册测试账号",
        ipad_uuid="uuid-cbreg-1",
        ipad_user_info={"userId": "1688850473951280"},
        host_status="hosted",
    )
    return {
        "id": acc["id"],
        "name": "回调重注册测试账号",
        "ipadUuid": "uuid-cbreg-1",
        "vid": "1688850473951280",
        "status": "online",
        "hostStatus": "hosted",
    }


def _settings_with(url: str, interval: int = 600):
    """构造带指定回调地址与重注册周期的 settings 副本。"""
    from app.config import settings as real

    return replace(
        real,
        ipad_callback_public_url=url,
        ipad_callback_type="HTTP",
        ipad_callback_reregister_interval_sec=interval,
    )


def _healthy_tick(rec: dict, url: str, register_result: dict, *, interval: int = 600):
    """在「长连接健康 + 指定回调地址」条件下跑一轮巡检，返回 register mock。"""
    cfg = _settings_with(url, interval)
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
        patch("app.ipad_health.settings", cfg),
        patch("app.ipad_sync.register_callback", return_value=register_result) as reg,
    ):
        yield_reg = reg
        ipad_health._tick(3)
    return yield_reg


class TestEnsureOnHealthy:
    """账号健康时必须确保回调已注册（后端重启自愈）。"""

    def test_registers_on_first_healthy_tick(self, backend, account):
        reg = _healthy_tick(
            account, PUBLIC_URL, {"ok": True, "registered": True, "url": PUBLIC_URL}
        )
        reg.assert_called_once_with(account["id"])
        state = ipad_health._callback_state[account["id"]]
        assert state["ok"] is True
        assert state["key"] == f"uuid-cbreg-1|{PUBLIC_URL}|HTTP"

    def test_does_not_reregister_within_interval(self, backend, account):
        ok = {"ok": True, "registered": True, "url": PUBLIC_URL}
        _healthy_tick(account, PUBLIC_URL, ok)
        reg2 = _healthy_tick(account, PUBLIC_URL, ok)
        # 第二轮巡检在周期内 → 不应再次调用 SetCallbackUrl
        reg2.assert_not_called()

    def test_reregisters_after_interval_elapsed(self, backend, account):
        ok = {"ok": True, "registered": True, "url": PUBLIC_URL}
        _healthy_tick(account, PUBLIC_URL, ok)
        # 把上次成功时间推到很久以前，模拟超过重注册周期
        ipad_health._callback_state[account["id"]]["at"] = -10_000.0
        reg2 = _healthy_tick(account, PUBLIC_URL, ok)
        reg2.assert_called_once_with(account["id"])

    def test_interval_zero_disables_periodic_refresh(self, backend, account):
        ok = {"ok": True, "registered": True, "url": PUBLIC_URL}
        _healthy_tick(account, PUBLIC_URL, ok, interval=0)
        ipad_health._callback_state[account["id"]]["at"] = -10_000.0
        reg2 = _healthy_tick(account, PUBLIC_URL, ok, interval=0)
        reg2.assert_not_called()


class TestTunnelRecovery:
    """隧道断开期间注册失败，恢复后必须自动补注册（核心自愈能力）。"""

    def test_retries_every_tick_while_failing(self, backend, account):
        failed = {"ok": False, "registered": False, "message": "Hostname not verified"}
        reg1 = _healthy_tick(account, PUBLIC_URL, failed)
        reg1.assert_called_once()
        assert ipad_health._callback_state[account["id"]]["ok"] is False
        # 失败态 → 下一轮仍应重试，而不是被缓存挡掉
        reg2 = _healthy_tick(account, PUBLIC_URL, failed)
        reg2.assert_called_once()

    def test_succeeds_after_tunnel_back(self, backend, account):
        failed = {"ok": False, "registered": False, "message": "connect timeout"}
        _healthy_tick(account, PUBLIC_URL, failed)
        reg2 = _healthy_tick(
            account, PUBLIC_URL, {"ok": True, "registered": True, "url": PUBLIC_URL}
        )
        reg2.assert_called_once()
        assert ipad_health._callback_state[account["id"]]["ok"] is True

    def test_url_change_forces_reregister(self, backend, account):
        ok_a = {"ok": True, "registered": True, "url": PUBLIC_URL}
        _healthy_tick(account, PUBLIC_URL, ok_a)
        ok_b = {"ok": True, "registered": True, "url": PUBLIC_URL_B}
        reg2 = _healthy_tick(account, PUBLIC_URL_B, ok_b)
        reg2.assert_called_once_with(account["id"])
        assert ipad_health._callback_state[account["id"]]["key"].endswith(
            f"{PUBLIC_URL_B}|HTTP"
        )

    def test_register_exception_is_swallowed_and_retried(self, backend, account):
        cfg = _settings_with(PUBLIC_URL)
        with (
            patch("app.ipad_client._mode", return_value="real"),
            patch(
                "app.ipad_client.get_run_client_info",
                return_value={"longLinkState": "CONNECTED", "loginType": 3},
            ),
            patch(
                "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
                return_value=[account],
            ),
            patch("app.ipad_health.settings", cfg),
            patch("app.ipad_sync.register_callback", side_effect=RuntimeError("boom")),
        ):
            ipad_health._tick(3)  # 不得抛出
        assert ipad_health._callback_state[account["id"]]["ok"] is False


class TestNoPublicUrl:
    """未配置公网回调地址时必须完全跳过（降级为仅手动同步）。"""

    def test_skips_entirely(self, backend, account):
        reg = _healthy_tick(account, "", {"ok": True, "registered": True})
        reg.assert_not_called()
        assert account["id"] not in ipad_health._callback_state


class TestHealthUnaffected:
    """回调注册失败 ≠ 账号掉线，不得影响健康状态。"""

    def test_account_stays_online_when_register_fails(self, backend, account):
        _healthy_tick(
            account, PUBLIC_URL, {"ok": False, "registered": False, "message": "timeout"}
        )
        row = backend.query_one(
            "SELECT status, host_status FROM channel_accounts WHERE id = ?", (account["id"],)
        )
        assert row["status"] == "online" and row["host_status"] == "hosted"
        assert ipad_health._failures.get(account["id"], 0) == 0


class TestRecoverForgetsState:
    """自动重连（uuid 轮换）后必须清除注册记忆，强制重新注册。"""

    def test_recover_clears_callback_state(self, backend, account):
        ipad_health._callback_state[account["id"]] = {
            "key": f"uuid-cbreg-1|{PUBLIC_URL}|HTTP", "at": 0.0, "ok": True, "message": ""
        }
        with (
            patch("app.ipad_client.init", return_value={"uuid": "uuid-new"}),
            patch("app.ipad_client.automatic_login", return_value={"ok": True}),
            patch("app.ipad_sync.trigger_sync"),
            patch("app.ipad_sync.register_callback", return_value={"registered": True}),
        ):
            assert ipad_health._recover(account) is True
        assert account["id"] not in ipad_health._callback_state


class TestSnapshotObservability:
    """健康快照需暴露回调注册状态，便于定位入向断裂。"""

    def test_snapshot_exposes_callback_registered(self, backend, account):
        cfg = _settings_with(PUBLIC_URL)
        _healthy_tick(account, PUBLIC_URL, {"ok": True, "registered": True, "url": PUBLIC_URL})
        with (
            patch(
                "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
                return_value=[account],
            ),
            patch("app.ipad_health.settings", cfg),
        ):
            snap = ipad_health.get_health_snapshot()
        assert len(snap) == 1
        assert snap[0]["callbackRegistered"] is True
        assert snap[0]["callbackConfiguredUrl"] == PUBLIC_URL

    def test_snapshot_reports_unregistered_reason(self, backend, account):
        cfg = _settings_with(PUBLIC_URL)
        _healthy_tick(
            account, PUBLIC_URL, {"ok": False, "registered": False, "message": "tunnel down"}
        )
        with (
            patch(
                "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
                return_value=[account],
            ),
            patch("app.ipad_health.settings", cfg),
        ):
            snap = ipad_health.get_health_snapshot()
        assert snap[0]["callbackRegistered"] is False
        assert snap[0]["callbackMessage"] == "tunnel down"


class TestEnsureCallbackNow:
    """运维入口：立即强制重注册（隧道恢复后手动一键补注册）。"""

    def test_forces_register_regardless_of_cache(self, backend, account):
        ok = {"ok": True, "registered": True, "url": PUBLIC_URL}
        _healthy_tick(account, PUBLIC_URL, ok)
        cfg = _settings_with(PUBLIC_URL)
        with (
            patch("app.ipad_health.settings", cfg),
            patch("app.ipad_sync.register_callback", return_value=ok) as reg,
        ):
            res = ipad_health.ensure_callback_now(account["id"])
        reg.assert_called_once_with(account["id"])
        assert res["registered"] is True and res["url"] == PUBLIC_URL

    def test_unknown_account_returns_not_ok(self, backend):
        res = ipad_health.ensure_callback_now("acc_not_exists")
        assert res["ok"] is False and res["registered"] is False


class TestRouteExposed:
    """运维端点已挂载，可用于隧道恢复后一键补注册。"""

    def test_register_callback_route(self, backend, account):
        from fastapi.testclient import TestClient
        from app.main import app

        ok = {"ok": True, "registered": True, "url": PUBLIC_URL, "message": ""}
        with (
            patch("app.ipad_health.ensure_callback_now", return_value=ok) as ensure,
            TestClient(app) as client,
        ):
            r = client.post(
                f"/api/channels/accounts/wecom/{account['id']}/callback/register"
            )
        assert r.status_code == 200
        assert r.json()["registered"] is True
        ensure.assert_called_once_with(account["id"])


class TestUnhealthyPathUnchanged:
    """长连接不健康时不做回调注册（先修长连接，避免无谓调用）。"""

    def test_no_register_when_link_down(self, backend, account):
        cfg = _settings_with(PUBLIC_URL)
        with (
            patch("app.ipad_client._mode", return_value="real"),
            patch(
                "app.ipad_client.get_run_client_info",
                side_effect=ipad_client.IPadProtocolError("实例掉线"),
            ),
            patch(
                "app.repositories.ChannelMgmtRepository.list_ipad_hosted_accounts",
                return_value=[account],
            ),
            patch("app.ipad_health.settings", cfg),
            patch("app.ipad_sync.register_callback") as reg,
        ):
            ipad_health._tick(3)
        reg.assert_not_called()

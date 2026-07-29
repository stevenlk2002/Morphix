"""iPad 协议账号健康巡检 + 自动重连。

在应用启动（main.lifespan）时调用 start_health_check() 拉起守护线程，周期性
（默认 60s）对每个 protocol='ipad' 且已持有 uuid 的托管账号执行：
- GetRunClientInfo 探测长连接状态；
- CONNECTED 且已登录（loginType==3） → 标记 online/hosted；
- 非 CONNECTED / 调用异常（实例掉线、uuid 失效） → 累加失败计数，达到阈值
  （默认 3）后标记 offline/error，并尝试自动重连：init(vid) 取得新 uuid →
  automaticLogin，成功则持久化新 uuid 并恢复 online/hosted，并重触发全量同步 +
  回调注册；失败（无 vid 或实例已死）则保持 offline，等待用户在前端手动重新扫码。

说明：uuid 由第三方 iPad 协议服务颁发与回收，本服务无法令其永久有效；自动重连
仅在「第三方实例仍在线、仅本服务重启/网络抖动」场景生效，实例彻底掉线时需用户
重新扫码（前端 hostStatus=='error' 会提示重扫）。
"""
from __future__ import annotations

import logging
import threading
import time

from . import ipad_client, ipad_sync
from .config import settings
from .database import get_backend
from .repositories import ChannelMgmtRepository

logger = logging.getLogger(__name__)

# 每账号连续失败计数（进程内）
_failures: dict[str, int] = {}
_lock = threading.Lock()
_running = False


def _healthy(long_link_state: str, login_type: int) -> bool:
    """CONNECTED 且已登录（loginType==3）视为健康。"""
    return long_link_state == "CONNECTED" and login_type == 3


def _mark(rec: dict, status: str, host_status: str) -> None:
    ChannelMgmtRepository(get_backend()).update_account_health(rec["id"], status, host_status)


def _recover(rec: dict) -> bool:
    """尝试 init(vid) + automaticLogin 自动重连；成功返回 True。"""
    vid = rec.get("vid", "")
    if not vid:
        logger.info("账号 %s 无 vid，无法自动重连，需手动重扫", rec["id"])
        return False
    try:
        init_res = ipad_client.init(vid=vid)
        new_uuid = init_res.get("uuid") or ""
        if not new_uuid:
            logger.warning("账号 %s init(vid) 未返回 uuid", rec["id"])
            return False
        repo = ChannelMgmtRepository(get_backend())
        repo.update_account_ipad_uuid(rec["id"], new_uuid)
        login = ipad_client.automatic_login(new_uuid)
        if not login.get("ok"):
            logger.warning("账号 %s 自动登录失败: %s", rec["id"], login.get("errmsg"))
            return False
        repo.update_account_health(rec["id"], "online", "hosted")
        try:
            ipad_sync.trigger_sync(rec["id"])
        except Exception:  # noqa: BLE001
            logger.exception("恢复后自动同步失败 account=%s", rec["id"])
        try:
            ipad_sync.register_callback(rec["id"])
        except Exception:  # noqa: BLE001
            logger.exception("恢复后注册回调失败 account=%s", rec["id"])
        logger.info("账号 %s 自动重连成功（新 uuid=%s）", rec["id"], new_uuid)
        return True
    except ipad_client.IPadProtocolError as exc:
        logger.warning("账号 %s 自动重连异常：%s", rec["id"], exc)
        return False


def _tick(fail_threshold: int) -> None:
    mode = ipad_client._mode()
    repo = ChannelMgmtRepository(get_backend())
    accounts = repo.list_ipad_hosted_accounts()
    for rec in accounts:
        uuid = rec.get("ipadUuid", "")
        if not uuid:
            continue
        if mode == "mock":
            # mock 模式无真实实例，保持 online/hosted（演示用），不计失败
            if rec.get("status") != "online" or rec.get("hostStatus") != "hosted":
                _mark(rec, "online", "hosted")
            continue
        try:
            info = ipad_client.get_run_client_info(uuid)
            lls = (info.get("longLinkState") or "").upper()
            lt = int(info.get("loginType", 1) or 1)
            if _healthy(lls, lt):
                with _lock:
                    _failures[rec["id"]] = 0
                if rec.get("status") != "online" or rec.get("hostStatus") != "hosted":
                    _mark(rec, "online", "hosted")
                continue
            raise ipad_client.IPadProtocolError(f"长连接未就绪: {lls}/loginType={lt}")
        except ipad_client.IPadProtocolError:
            with _lock:
                _failures[rec["id"]] = _failures.get(rec["id"], 0) + 1
                fails = _failures[rec["id"]]
            if fails >= fail_threshold:
                _mark(rec, "offline", "error")
                logger.warning("账号 %s 连续 %d 次探测失败，尝试自动重连", rec["id"], fails)
                if _recover(rec):
                    with _lock:
                        _failures[rec["id"]] = 0


def _loop(interval_sec: int, fail_threshold: int) -> None:
    logger.info("iPad 健康巡检线程启动：间隔=%ds 失败阈值=%d", interval_sec, fail_threshold)
    while True:
        try:
            _tick(fail_threshold)
        except Exception:  # noqa: BLE001
            logger.exception("iPad 健康巡检异常")
        time.sleep(interval_sec)


def start_health_check() -> None:
    """启动健康巡检守护线程（幂等：重复调用无效）。"""
    global _running
    if _running:
        return
    _running = True
    t = threading.Thread(
        target=_loop,
        args=(settings.ipad_health_check_interval_sec, settings.ipad_health_check_fail_threshold),
        daemon=True,
    )
    t.start()


def get_health_snapshot() -> list[dict]:
    """返回当前各账号健康快照（调试 / 前端实时读取）。"""
    repo = ChannelMgmtRepository(get_backend())
    accounts = repo.list_ipad_hosted_accounts()
    snap = []
    for rec in accounts:
        with _lock:
            fails = _failures.get(rec["id"], 0)
        snap.append({
            "id": rec["id"],
            "name": rec["name"],
            "ipadUuid": rec.get("ipadUuid", ""),
            "status": rec.get("status", ""),
            "hostStatus": rec.get("hostStatus", ""),
            "consecutiveFailures": fails,
        })
    return snap

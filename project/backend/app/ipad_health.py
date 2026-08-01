"""iPad 协议账号健康巡检 + 自动重连。

在应用启动（main.lifespan）时调用 start_health_check() 拉起守护线程，周期性
（默认 60s）对每个 protocol='ipad' 且已持有 uuid 的托管账号执行：
- GetRunClientInfo 探测长连接状态；
- CONNECTED 且已登录（loginType==3） → 标记 online/hosted；
- 非 CONNECTED / 调用异常（实例掉线、uuid 失效） → 累加失败计数，达到阈值
  （默认 3）后标记 offline/error，并尝试自动重连：init(vid) 取得新 uuid →
  automaticLogin，成功则持久化新 uuid 并恢复 online/hosted，并重触发全量同步 +
  回调注册；失败（无 vid 或实例已死）则保持 offline，等待用户在前端手动重新扫码。
- 账号健康时，额外「确保实时回调已注册」（_ensure_callback）：首次巡检、回调地址
  变更或超过重注册周期时重发 SetCallbackUrl。

说明：uuid 由第三方 iPad 协议服务颁发与回收，本服务无法令其永久有效；自动重连
仅在「第三方实例仍在线、仅本服务重启/网络抖动」场景生效，实例彻底掉线时需用户
重新扫码（前端 hostStatus=='error' 会提示重扫）。

入向消息断裂修复（回调重注册）：
`SetCallbackUrl` 此前仅在「托管首次创建」与「掉线自动重连成功」两条路径触发。
后端重启（launchd KeepAlive 会频繁重启）或内网穿透隧道掉线再恢复后，协议侧回调
地址可能已失效/被丢弃，而账号本身一直 CONNECTED，永远走不到重连分支 →
入向消息永久性收不到，必须人工重扫码。本模块因此在健康分支补上周期性
「确保注册」，使隧道恢复后入向链路可自愈。
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
# 每账号回调注册状态（进程内）：account_id -> {"key", "at", "ok", "message"}
# key = f"{uuid}|{public_url}|{callback_type}"，任一变化都必须重新注册。
_callback_state: dict[str, dict] = {}
_lock = threading.Lock()
_running = False


def _callback_key(uuid: str, url: str, callback_type: str) -> str:
    """回调注册身份键：uuid / 公网地址 / 回调类型任一变化都需重新注册。"""
    return f"{uuid}|{url}|{callback_type}"


def _healthy(long_link_state: str, login_type: int) -> bool:
    """CONNECTED 且已登录（loginType==3）视为健康。"""
    return long_link_state == "CONNECTED" and login_type == 3


def _mark(rec: dict, status: str, host_status: str) -> None:
    ChannelMgmtRepository(get_backend()).update_account_health(rec["id"], status, host_status)


def _needs_callback_register(account_id: str, key: str, now: float) -> bool:
    """判断是否需要（重新）向协议服务注册回调地址。

    触发条件（任一满足）：
    1. 本进程尚未成功注册过该账号（后端重启后必然命中，覆盖 launchd 频繁重启场景）；
    2. 注册身份键变化（uuid 轮换 / IPAD_CALLBACK_PUBLIC_URL 改成新隧道域名）；
    3. 上次注册失败（隧道断开时协议侧校验失败）→ 每个巡检周期重试，隧道恢复即自愈；
    4. 距上次成功注册已超过重注册周期（默认 600s）→ 周期性刷新，防协议侧静默失效。

    Args:
        account_id: 渠道账号 id。
        key: `_callback_key()` 生成的注册身份键。
        now: 当前单调时间戳（秒）。

    Returns:
        需要注册返回 True。
    """
    with _lock:
        state = _callback_state.get(account_id)
    if state is None or state.get("key") != key or not state.get("ok"):
        return True
    interval = settings.ipad_callback_reregister_interval_sec
    if interval <= 0:
        return False
    return (now - float(state.get("at", 0.0))) >= interval


def _ensure_callback(rec: dict) -> None:
    """账号健康时确保实时回调已注册（幂等、失败不影响账号健康状态）。

    未配置 IPAD_CALLBACK_PUBLIC_URL 时直接跳过（降级为「仅手动同步」，PRD §5 #5）。
    注册失败仅记录状态与日志：回调注册失败不等于账号掉线，不得触发 offline 标记。

    Args:
        rec: `list_ipad_hosted_accounts()` 返回的账号快照（含 id / ipadUuid）。
    """
    public_url = (settings.ipad_callback_public_url or "").strip()
    if not public_url:
        return
    account_id = rec["id"]
    uuid = rec.get("ipadUuid", "")
    callback_type = (settings.ipad_callback_type or "HTTP").upper()
    key = _callback_key(uuid, public_url, callback_type)
    now = time.monotonic()
    if not _needs_callback_register(account_id, key, now):
        return
    try:
        res = ipad_sync.register_callback(account_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("确保回调注册异常 account=%s", account_id)
        res = {"registered": False, "message": str(exc)}
    ok = bool(res.get("registered"))
    with _lock:
        _callback_state[account_id] = {
            "key": key,
            "at": now,
            "ok": ok,
            "message": str(res.get("message") or ""),
            "url": public_url,
        }
    if ok:
        logger.info("回调地址已注册/刷新 account=%s url=%s", account_id, public_url)
    else:
        logger.warning(
            "回调地址注册失败 account=%s url=%s reason=%s（隧道恢复后下轮巡检自动重试）",
            account_id, public_url, res.get("message"),
        )


def _forget_callback(account_id: str) -> None:
    """清除进程内回调注册记忆，使下轮巡检强制重新注册。"""
    with _lock:
        _callback_state.pop(account_id, None)


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
        # uuid 已轮换，进程内注册记忆失效，强制下轮重新注册。
        _forget_callback(rec["id"])
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
                # 长连接健康 ≠ 回调可用：后端重启 / 隧道掉线恢复后需补注册回调，
                # 否则入向消息永久断裂（本次 Bug 根因之一）。
                _ensure_callback(rec)
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
            cb = dict(_callback_state.get(rec["id"]) or {})
        snap.append({
            "id": rec["id"],
            "name": rec["name"],
            "ipadUuid": rec.get("ipadUuid", ""),
            "status": rec.get("status", ""),
            "hostStatus": rec.get("hostStatus", ""),
            "consecutiveFailures": fails,
            # 入向链路可观测性：回调是否已成功注册到协议服务。
            # callbackRegistered=False 时入向消息不会到达（多为隧道断开）。
            "callbackConfiguredUrl": (settings.ipad_callback_public_url or "").strip(),
            "callbackRegistered": bool(cb.get("ok")),
            "callbackMessage": cb.get("message", ""),
        })
    return snap


def ensure_callback_now(account_id: str) -> dict:
    """立即为指定账号强制重注册回调（运维/自测入口，绕过周期与缓存）。

    Args:
        account_id: 渠道账号 id。

    Returns:
        `ipad_sync.register_callback` 的原始结果字典。
    """
    _forget_callback(account_id)
    repo = ChannelMgmtRepository(get_backend())
    rec = repo.get_account_by_id(account_id)
    if not rec:
        return {"ok": False, "registered": False, "message": "账号不存在"}
    _ensure_callback(rec)
    with _lock:
        state = dict(_callback_state.get(account_id) or {})
    return {
        "ok": bool(state.get("ok")),
        "registered": bool(state.get("ok")),
        "url": state.get("url", ""),
        "message": state.get("message", ""),
    }

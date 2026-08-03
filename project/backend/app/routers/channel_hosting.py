"""企业微信 iPad 协议托管接入路由。

完整路径前缀：`/api/channels/accounts/wecom/...`
（`api_router` 自带 `/api` 前缀，本路由 `prefix="/channels/accounts/wecom"`）。

三个端点（契约见 docs/system_design.md 第 3.2 节）：
- `POST /start`  发起扫码，返回 `uuid / qrcode / qrcodeData / qrcodeKey / ttl / mock`
- `POST /verify` 校验验证码（mock 下标记 `MockState[uuid].verified=True`）
- `POST /poll`   轮询登录态；当 `loginType==2` 时自动 `create_account_with_ipad` 落库，
                 并在响应附带 `account`

错误处理：参数缺失 → 400；iPad 真实服务异常且无法 mock → 502。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import threading

from .. import ipad_client, ipad_sync
from ..database import get_backend
from ..repositories import ChannelMgmtRepository, _resolve_avatar_url
from ..schemas import (
    WecomHostPollRequest,
    WecomHostStartRequest,
    WecomHostVerifyRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels/accounts/wecom", tags=["channel-hosting"])

# 落库串行锁：保护「loginType==2 时按 uuid 查重 + 创建账号」临界区。
# 前端每 2s 轮询一次，loginType==2 会持续多轮返回，且单次 poll 内存在
# userInfo 重试（最多 ~3s），多个轮询请求可能并发在途。若不加锁，并发的
# 查重与创建之间可能产生竞态，导致重复 INSERT（本次 Bug：清空渠道后扫码
# 出现 4 个完全相同账号）。该锁保证整进程内同一 uuid 仅创建一次账号；
# 数据库层另有 ipad_uuid 唯一索引兜底（多 worker / 并发请求场景）。
_CREATE_LOCK = threading.Lock()


def _extract_wecom_display_name(user_info: Any | None) -> str:
    """从 iPad 协议 userInfo 提取真实企业微信显示名（按协议字段优先级）。

    真实服务可能在 `nickname` / `realname` / `name` / `username` / `wxid` /
    `userId` / `acctId` / `unionId` 等字段返回账号名，这里统一按优先级取舍，
    避免落库成 `企业微信-{uuid[:6]}` 这类编号兜底名（见任务 Issue #1）。
    """
    if not isinstance(user_info, dict):
        return ""
    for key in (
        "nickname",
        "realname",
        "name",
        "username",
        "wxid",
        "userId",
        "acctId",
        "unionId",
    ):
        val = user_info.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


@router.post("/start")
def start_wecom(payload: WecomHostStartRequest) -> dict:
    """发起企业微信托管扫码。

    错误处理：
    - `IPadProtocolError`：iPad 真实服务异常（real 模式下抛出），返回 502，
      message 携带原始错误细节，便于前端透传原因。
    - 其他 `Exception`：如 KeyError / ValueError / httpx 网络异常等未预期异常，
      捕获后返回 500（不再裸抛 500 给前端），message 含具体异常信息，
      并用 `logger.exception` 记录完整堆栈便于排查。
    - `res` 缺乏 `uuid`：视为协议返回异常，返回 500 提示「缺少 uuid」。
    """
    team_id = payload.teamId or ""
    name = payload.name
    channel_type = payload.channelType or "wecom"
    try:
        res = ipad_client.start_wecom(team_id, name, channel_type)
    except ipad_client.IPadProtocolError as exc:
        logger.exception("企业微信托管扫码失败：iPad 协议服务异常")
        return JSONResponse(
            status_code=502,
            content={"message": f"iPad 协议服务不可用：{exc}"},
        )
    except Exception as exc:
        logger.exception("企业微信托管扫码失败：未预期异常")
        return JSONResponse(
            status_code=500,
            content={"message": f"启动扫码失败：{exc}"},
        )
    uuid = res.get("uuid")
    if not uuid:
        logger.error("企业微信托管扫码返回异常：缺少 uuid（res=%s）", res)
        return JSONResponse(
            status_code=500,
            content={"message": "iPad 协议返回异常：缺少 uuid"},
        )
    return {
        "uuid": uuid,
        "qrcode": res.get("qrcode"),
        "qrcodeData": res.get("qrcode_data"),
        "qrcodeKey": res.get("qrcode_key"),
        "ttl": res.get("ttl"),
        "mock": res.get("mock", False),
    }


@router.post("/verify")
def verify_wecom(payload: WecomHostVerifyRequest) -> dict:
    """校验 6 位验证码；mock 下标记 verified。"""
    if not payload.uuid or not payload.qrcodeKey or not payload.code:
        return JSONResponse(status_code=400, content={"message": "缺少必要参数"})
    try:
        res = ipad_client.verify_wecom(payload.uuid, payload.qrcodeKey, payload.code)
    except ipad_client.IPadProtocolError:
        return JSONResponse(status_code=502, content={"message": "iPad 协议服务不可用"})
    return {"ok": bool(res.get("ok")), "skip": bool(res.get("skip", False))}


@router.post("/poll")
def poll_wecom(payload: WecomHostPollRequest) -> dict:
    """轮询登录态；loginType==2 时自动落库并返回 account。"""
    if not payload.uuid:
        return JSONResponse(status_code=400, content={"message": "缺少 uuid 参数"})
    try:
        info = ipad_client.poll_wecom(payload.uuid)
    except ipad_client.IPadProtocolError:
        return JSONResponse(status_code=502, content={"message": "iPad 协议服务不可用"})

    result: dict[str, Any] = {
        "loginType": info.get("loginType"),
        "userInfo": info.get("userInfo"),
        "longLinkState": info.get("longLinkState"),
        "mock": info.get("mock", False),
    }

    if info.get("loginType") == 2:
        # 从 MockState 取回 start 时缓存的上下文（真实模式亦已缓存）
        state = ipad_client.MockState.get(payload.uuid, {})
        team_id = state.get("team_id", "")
        channel_type = state.get("channel_type", "wecom")
        user_info = info.get("userInfo") or {}
        if not isinstance(user_info, dict) or not user_info:
            # 抢在 userInfo 就绪前 poll 到的竞态：轮询 retry 最多 5 次，每次 600ms
            # 真实服务常在 loginType==2 后短暂延迟才填充 userInfo
            for _ in range(5):
                try:
                    retry = ipad_client.get_run_client_info(payload.uuid)
                    candidate = retry.get("userInfo") or {}
                    if isinstance(candidate, dict) and candidate:
                        user_info = candidate
                        break
                except Exception:
                    pass
                time.sleep(0.6)
        if isinstance(user_info, dict):
            nickname = (
                user_info.get("nickname")
                or user_info.get("realname")
                or user_info.get("name")
            )
        else:
            nickname = None
        # 命名优先级：真实昵称 > start 默认名 > 兜底「企业微信-{uuid[:6]}」
        name = nickname or state.get("name") or f"企业微信-{payload.uuid[:6]}"
        # 头像解析（avatar > headImgUrl > headimgurl；空串表示无）
        avatar = _resolve_avatar_url(user_info)
        repo = ChannelMgmtRepository(get_backend())

        # —— 幂等保护（双重防线） ——
        # 防线 1：ipad_uuid 进程内锁 + 查重（拦截同一 uuid 的并发轮询）
        # 防线 2：企微自然唯一键 (corpId, userId) 查重（拦截不同 uuid 的重复扫码）
        #
        # 用户可能多点验证码 → 前端发两次 /start → 协议生成两个不同 uuid
        # → 各自 poll 落库 → ipad_uuid 不同，防线 1 拦不住。
        # 用 userInfo 中的 corpId + userId 作为业务唯一键做第二道去重。
        corp_id = (user_info.get("corpId") or "") if isinstance(user_info, dict) else ""
        user_id = (user_info.get("userId") or "") if isinstance(user_info, dict) else ""

        with _CREATE_LOCK:
            # 防线 1：按 ipad_uuid 查
            existing = repo.get_account_by_ipad_uuid(payload.uuid)
            if existing is None and corp_id and user_id:
                # 防线 2：按企微身份查（不同 uuid 但同一人）
                existing = repo.get_account_by_wecomm_identity(corp_id, user_id)
                if existing is not None:
                    logger.info(
                        "企微身份去重命中：corpId=%s userId=%s 已有账号 %s"
                        "（当前 uuid=%s 与已有 uuid=%s 不同，更新为新 uuid）",
                        corp_id, user_id, existing["id"],
                        payload.uuid, existing.get("ipadUuid", ""),
                    )
                    # 更新为新 uuid（协议侧 uuid 可能已轮换）
                    repo.update_account_ipad_uuid(existing["id"], payload.uuid)
            if existing is None:
                account = repo.create_account_with_ipad(
                    channel_type=channel_type,
                    protocol="ipad",
                    team_id=team_id,
                    name=name,
                    ipad_uuid=payload.uuid,
                    ipad_user_info=user_info,
                    host_status="hosted",
                    avatar=avatar,
                    wecomm_corp_id=corp_id,
                    wecomm_user_id=user_id,
                )
                created = True
            else:
                account = existing
                created = False
        result["account"] = account

        # 仅在「本次新创建」时触发同步与实时回调；已存在账号此前已触发过，
        # 避免每次轮询都重复触发（trigger_sync 自身也有「已在同步中」去重）。
        if created:
            # 决策 #11：托管成功后后台线程自动全量同步（不阻塞请求；异常吞掉记日志）
            try:
                if not ipad_sync.trigger_sync(account["id"]):
                    logger.info("账号 %s 已在同步中，跳过自动触发", account["id"])
            except Exception:  # noqa: BLE001
                logger.exception("自动触发 iPad 全量同步失败 account=%s", account["id"])

            # P2-4：若配置了公网回调地址，托管成功后 best-effort 注册实时回调
            try:
                reg = ipad_sync.register_callback(account["id"])
                if reg.get("registered"):
                    logger.info("账号 %s 已注册实时回调 %s", account["id"], reg.get("url"))
            except Exception:  # noqa: BLE001
                logger.exception("注册实时回调失败 account=%s", account["id"])

    return result


@router.get("/health")
def wecom_health() -> dict:
    """返回各 iPad 托管账号的实时健康快照（供前端实时读取）。"""
    from .. import ipad_health

    return {"accounts": ipad_health.get_health_snapshot()}


@router.post("/{account_id}/callback/register")
def wecom_register_callback(account_id: str) -> dict:
    """立即为账号重注册实时回调地址（入向消息恢复入口）。

    使用场景：内网穿透隧道恢复后无需等待巡检周期，手动一键补注册。
    健康巡检也会在账号在线时周期性自动执行同样的动作。

    Args:
        account_id: 渠道账号 id。

    Returns:
        `{ok, registered, url, message}`。
    """
    from .. import ipad_health

    return ipad_health.ensure_callback_now(account_id)

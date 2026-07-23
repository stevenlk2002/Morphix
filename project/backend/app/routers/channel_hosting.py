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
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

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
    """发起企业微信托管扫码。"""
    team_id = payload.teamId or ""
    name = payload.name
    channel_type = payload.channelType or "wecom"
    try:
        res = ipad_client.start_wecom(team_id, name, channel_type)
    except ipad_client.IPadProtocolError:
        return JSONResponse(status_code=502, content={"message": "iPad 协议服务不可用"})
    return {
        "uuid": res["uuid"],
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
            # 抢在 userInfo 就绪前 poll 到的竞态：再取一次真实客户端信息
            try:
                retry = ipad_client.get_run_client_info(payload.uuid)
                user_info = retry.get("userInfo") or {}
            except Exception:
                user_info = {}
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
        account = repo.create_account_with_ipad(
            channel_type=channel_type,
            protocol="ipad",
            team_id=team_id,
            name=name,
            ipad_uuid=payload.uuid,
            ipad_user_info=user_info,
            host_status="hosted",
            avatar=avatar,
        )
        result["account"] = account

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

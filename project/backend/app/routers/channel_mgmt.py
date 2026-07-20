"""渠道会话管理域路由。

统一前缀 `/channels`（复数），由 `api_router`（`/api`）挂载，
完整路径以 `/api/channels/...` 开头。遗留 `/api/channel-accounts` 保持不变。

覆盖：teams / accounts / contacts / sessions / hosting-sessions /
hosting-rules / wechat-subjects / hosting-bots。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..database import get_backend
from ..repositories import ChannelMgmtRepository, CustomerRepository
from ..schemas import (
    ChannelAccountUpsertRequest,
    CustomerProfileUpdateRequest,
    HostingBatchUpdateRequest,
    HostingRuleRequest,
    SessionHostingRequest,
    TeamCreateRequest,
    WechatSubjectCreateRequest,
    WechatSubjectUpdateRequest,
)

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/teams")
def list_teams():
    """团队列表（ACC/SES 顶部团队信息条）。"""
    return ChannelMgmtRepository(get_backend()).list_teams()


@router.post("/teams")
def create_team(payload: TeamCreateRequest):
    """新建团队（P2：前端暂未接入，后端预留）。"""
    return ChannelMgmtRepository(get_backend()).create_team(
        payload.name, payload.seatsLeft or 0, payload.energyValue or 0
    )


@router.get("/accounts")
def list_accounts():
    """渠道账号列表（扩展 DTO：含 team/protocol/sessionsCount）。"""
    return ChannelMgmtRepository(get_backend()).list_accounts_enriched()


@router.post("/accounts")
def create_account(payload: ChannelAccountUpsertRequest):
    """添加渠道账号（添加向导完成落库）。"""
    return ChannelMgmtRepository(get_backend()).create_account(
        payload.channelType, payload.protocol or "", payload.teamId or "", payload.name
    )


@router.get("/contacts")
def list_contacts(
    accountId: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    """联系人列表（筛选：账号 / 类型 / 状态 / 关键字）。"""
    return ChannelMgmtRepository(get_backend()).list_contacts(accountId, type, status, search)


@router.get("/contacts/{contact_id}")
def get_contact_detail(contact_id: str):
    """联系人详情（聚合 profile / 沟通记录 / 自定义属性）。"""
    return ChannelMgmtRepository(get_backend()).get_contact_detail(contact_id)


@router.put("/contacts/{contact_id}/profile")
def update_contact_profile(contact_id: str, payload: CustomerProfileUpdateRequest):
    """更新客户档案（基本信息+备注+AI总结开关）。"""
    fields = payload.model_dump(exclude_none=True)
    result = CustomerRepository(get_backend()).update_customer_profile(contact_id, fields)
    if result is None:
        return JSONResponse(status_code=404, content={"detail": "客户档案不存在"})
    return result


@router.get("/sessions")
def list_sessions(
    accountId: Optional[str] = None,
    read: Optional[str] = None,
    hosted: Optional[str] = None,
    online: Optional[str] = None,
    search: Optional[str] = None,
):
    """会话列表（IM 收件箱，筛选：账号 / 阅读 / 托管 / 在线 / 关键字）。"""
    return ChannelMgmtRepository(get_backend()).list_sessions(accountId, read, hosted, online, search)


@router.get("/sessions/{session_id}/messages")
def list_session_messages(session_id: str):
    """会话消息（聊天面板，复用 messages 表）。"""
    return ChannelMgmtRepository(get_backend()).list_session_messages(session_id)


@router.post("/sessions/{session_id}/hosting")
def set_session_hosting(session_id: str, payload: SessionHostingRequest):
    """开启/关闭会话机器人托管 + 选择机器人。"""
    return ChannelMgmtRepository(get_backend()).set_session_hosting(
        session_id, payload.hosted, payload.botId
    )


@router.get("/hosting-sessions")
def list_hosting_sessions(
    accountId: Optional[str] = None,
    botId: Optional[str] = None,
    sessionType: Optional[str] = None,
    nickname: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """托管批量列表（筛选：账号 / 昵称 / 添加时间）。"""
    return ChannelMgmtRepository(get_backend()).list_hosting_sessions(
        accountId, botId, sessionType, nickname, start, end
    )


@router.post("/hosting-sessions/batch-update")
def batch_update_hosting(payload: HostingBatchUpdateRequest):
    """批量编辑托管状态 / 托管链。返回影响行数。"""
    updated = ChannelMgmtRepository(get_backend()).batch_update_hosting(
        payload.ids, payload.hostedStatus, payload.hostingChain
    )
    return {"updated": updated}


@router.get("/hosting-rules")
def get_hosting_rules(accountId: Optional[str] = None):
    """托管规则（按账号或全局）。"""
    return ChannelMgmtRepository(get_backend()).get_hosting_rules(accountId)


@router.put("/hosting-rules")
def upsert_hosting_rules(payload: HostingRuleRequest):
    """保存托管规则。"""
    return ChannelMgmtRepository(get_backend()).upsert_hosting_rules(
        payload.accountId, payload.autoResumeSeconds, payload.autoCancelEnabled
    )


@router.get("/wechat-subjects")
def list_wechat_subjects():
    """企微接入主体列表。"""
    return ChannelMgmtRepository(get_backend()).list_wechat_subjects()


@router.post("/wechat-subjects")
def create_wechat_subject(payload: WechatSubjectCreateRequest):
    """新增企微接入主体。"""
    return ChannelMgmtRepository(get_backend()).create_wechat_subject(
        payload.fullName, payload.shortName, payload.corpId, payload.configJson or "{}"
    )


@router.put("/wechat-subjects/{subject_id}")
def update_wechat_subject(subject_id: str, payload: WechatSubjectUpdateRequest):
    """更新企微接入主体配置（部分更新，未提供字段沿用原值）。"""
    repo = ChannelMgmtRepository(get_backend())
    existing = repo.get_wechat_subject(subject_id)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": "主体不存在"})
    return repo.update_wechat_subject(
        subject_id,
        payload.fullName if payload.fullName is not None else existing["fullName"],
        payload.shortName if payload.shortName is not None else existing["shortName"],
        payload.corpId if payload.corpId is not None else existing["corpId"],
        payload.configJson if payload.configJson is not None else existing["configJson"],
    )


@router.get("/hosting-bots")
def list_hosting_bots():
    """托管可选机器人（静态配置）。"""
    return ChannelMgmtRepository(get_backend()).list_hosting_bots()

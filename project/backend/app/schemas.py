"""请求/响应 Pydantic 模型。"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class HandoffRequest(BaseModel):
    operator: str = "运营人员"
    reason: str = "manual_takeover"


class SopCreateRequest(BaseModel):
    name: str
    trigger: str


class BotCreateRequest(BaseModel):
    name: str
    project: str = "GlowLab"
    workflow: str = "销售接待主流程"
    tone: str = "亲切专业"
    trainingPrompt: str = ""


class ChannelAccountCreateRequest(BaseModel):
    channel: str
    accountName: str
    boundBot: str
    dailyQuota: int = 200


# ---- 渠道会话管理域请求模型 ----
class ChannelAccountUpsertRequest(BaseModel):
    channelType: str = "wecom"
    protocol: Optional[str] = ""
    teamId: Optional[str] = ""
    name: Optional[str] = None


# ---- 企业微信 iPad 协议托管接入（T01）请求模型 ----
class WecomHostStartRequest(BaseModel):
    """发起托管扫码：teamId 必填（缺省空串），name / channelType 可选。"""
    teamId: str = ""
    name: Optional[str] = None
    channelType: str = "wecom"


class WecomHostVerifyRequest(BaseModel):
    """校验 6 位验证码。"""
    uuid: str
    qrcodeKey: str
    code: str


class WecomHostPollRequest(BaseModel):
    """轮询登录态。"""
    uuid: str


class HostingRuleRequest(BaseModel):
    accountId: Optional[str] = None
    autoResumeSeconds: Optional[int] = None
    autoCancelEnabled: bool = False


class HostingBatchUpdateRequest(BaseModel):
    ids: list[str] = []
    hostedStatus: Optional[str] = None
    hostingChain: Optional[str] = None


class SessionHostingRequest(BaseModel):
    hosted: bool = False
    botId: Optional[str] = None


class WechatSubjectCreateRequest(BaseModel):
    fullName: str
    shortName: str
    corpId: str
    configJson: Optional[str] = "{}"


class WechatSubjectUpdateRequest(BaseModel):
    """部分更新：未提供的字段沿用数据库中已有值。"""

    fullName: Optional[str] = None
    shortName: Optional[str] = None
    corpId: Optional[str] = None
    configJson: Optional[str] = None


class TeamCreateRequest(BaseModel):
    name: str
    seatsLeft: Optional[int] = 0
    energyValue: Optional[int] = 0



class TagCreateRequest(BaseModel):
    name: str
    color: str = "blue"
    rule: str = ""


class WorkflowNodeUpdateRequest(BaseModel):
    label: str
    nodeType: str = "action"
    config: dict = {}


class KnowledgeCreateRequest(BaseModel):
    question: str
    answer: str
    tags: list[str] = []
    source: str = "手动录入"
    kind: str = "common"
    creator: str = "system"


class KnowledgeUpdateRequest(BaseModel):
    question: str
    answer: str
    tags: list[str] = []
    source: str = "手动录入"
    kind: Optional[str] = None
    creator: Optional[str] = None


class MaterialCreateRequest(BaseModel):
    name: str
    type: str
    size: int
    category: str = "未分类"
    url: Optional[str] = None
    source: str = "上传"


class TrainingRecordCreate(BaseModel):
    title: Optional[str] = None


class TrainingMessageCreate(BaseModel):
    role: str
    content: str
    recordRef: Optional[str] = ""


class TrainingFeedbackUpdate(BaseModel):
    feedback: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    ids: list[str] = []


class OrchestrationWorkflowSave(BaseModel):
    """编排工作流保存请求（前端 WorkflowPersisted 结构）。"""
    botId: str
    version: int = 1
    lastEdited: str
    nodes: list = []
    edges: list = []


class OrchestrationWorkflowResponse(BaseModel):
    """编排工作流查询响应。"""
    botId: str
    version: int
    lastEdited: str
    nodes: list
    edges: list
    updatedAt: str


class MessageLogNode(BaseModel):
    """托管消息日志的单个编排节点执行追踪。"""
    name: str
    icon: str
    runtime: str
    input: Any = None
    output: Any = None
    code: str = ""


class MessageLogItem(BaseModel):
    """托管消息日志列表项。"""
    id: str
    content: Any = None
    question: str = ""
    account: str = ""
    session: str = ""
    robot: str = ""
    channel: str = ""
    time: str = ""
    status: str = ""


class MessageLogDetail(MessageLogItem):
    """托管消息日志详情（含编排节点追踪列表）。"""
    nodes: List[MessageLogNode] = []


class MessageLogListResponse(BaseModel):
    """托管消息日志分页信封。"""
    items: List[MessageLogItem]
    total: int
    page: int
    pageSize: int
    hasMore: bool


# ---- 客户管理域请求模型 ----
class CustomerProfileUpdateRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    region: Optional[str] = None
    age: Optional[int] = None
    birthday: Optional[str] = None
    remark: Optional[str] = None
    aiSummaryEnabled: Optional[bool] = None


class CommunicationCreateRequest(BaseModel):
    content: str
    type: str = "note"
    aiSummary: Optional[str] = ""


class CustomAttributeCreateRequest(BaseModel):
    name: str
    value: str


class CustomerTagRelationRequest(BaseModel):
    tagIds: list[str] = []


class TagGroupCreateRequest(BaseModel):
    name: str
    isHot: bool = False
    tags: list[dict] = []


class TagGroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    isHot: Optional[bool] = None
    tags: Optional[list[dict]] = None


class CustomerGroupCreateRequest(BaseModel):
    name: str
    type: str = "custom"
    customerIds: Optional[list[str]] = None


class CustomerGroupCreateWithMembersRequest(BaseModel):
    """创建客户分组并同时添加初始成员。"""
    name: str
    type: str = "custom"
    memberIds: list[str] = []


class AddMembersRequest(BaseModel):
    """批量添加分组成员请求体。"""
    contactIds: list[str] = []


class BatchAiSummaryRequest(BaseModel):
    """批量更新 AI 总结开关。"""
    contactIds: list[str] = []
    enabled: bool = False


class BatchTagsRequest(BaseModel):
    """批量操作客户标签。"""
    contactIds: list[str] = []
    tagIds: list[str] = []
    mode: str = "add"  # "add" | "remove" | "replace"


class CustomerGroupDeleteRequest(BaseModel):
    """批量删除客户分组请求体。"""
    group_ids: list[str] = []


# ---- iPad 协议同步域（T02）请求/响应模型 ----
class SendTextRequest(BaseModel):
    """发送文本消息：前端只传目标类型 + 目标 id + 内容，后端反查 user_id/room_id。

    targetType: contact | room | session
    """
    targetType: str
    targetId: str
    content: str


class SyncStatusDTO(BaseModel):
    """账号同步状态。"""
    accountId: str
    syncStatus: str = ""  # '' | syncing | success | degraded | error
    lastSyncAt: str = ""
    syncing: bool = False


class GroupDTO(BaseModel):
    """群（客户群/内部群）DTO。"""
    id: str
    accountId: str
    roomId: str
    groupType: str = "customer_group"
    name: str = ""
    total: int = 0
    roomUrl: str = ""
    noticeContent: str = ""
    createTime: str = ""
    updateTime: str = ""


class GroupMemberDTO(BaseModel):
    """群成员 DTO。"""
    id: str
    groupId: str
    uin: str = ""
    userId: str = ""
    nickname: str = ""
    realname: str = ""
    avatar: str = ""
    roomNickname: str = ""
    sex: int = 0
    mobile: str = ""
    joinTime: str = ""


class GroupDetailDTO(BaseModel):
    """群详情（含成员列表）。"""
    group: GroupDTO
    members: list[GroupMemberDTO] = []
    noticeContent: str = ""
    total: int = 0


class SyncResultDTO(BaseModel):
    """手动同步触发响应。"""
    started: bool = False
    skipped: bool = False
    accountId: str = ""
    message: str = ""


class SendTextResultDTO(BaseModel):
    """发送文本消息响应。"""
    msgId: str = ""
    ok: bool = True
    serverId: str = ""


# ---- P1+P2 增量 DTO（标签 / 搜索添加 / 已读 / 历史回填 / 富媒体 / 回调） ----
class LabelDTO(BaseModel):
    """iPad 标签（映射后）。"""
    accountId: str = ""
    labelId: str = ""
    labelName: str = ""
    labelType: int = 0
    labelGroupId: str = ""
    tagId: str = ""
    syncType: int = 0


class LabelSyncResultDTO(BaseModel):
    """标签同步结果。"""
    accountId: str = ""
    total: int = 0
    synced: int = 0
    skipped: bool = False


class ContactSearchResultDTO(BaseModel):
    """搜索添加外部联系人结果项。"""
    userId: str = ""
    name: str = ""
    sex: int = 0
    headImg: str = ""
    ticket: str = ""
    openId: str = ""
    corpId: str = ""
    state: str = ""


class AddSearchRequest(BaseModel):
    """搜索添加外部联系人：发送好友申请。"""
    vid: str
    openId: str = ""
    phone: str = ""
    content: str = ""
    ticket: str = ""
    # 直接添加兜底（仅限曾被删除场景）：true 时改调 AddWxUser
    useDirectAdd: bool = False


class SearchContactRequest(BaseModel):
    """按手机号/关键词搜索外部联系人。"""
    keyword: str = ""


class SetContactLabelsRequest(BaseModel):
    """编辑联系人 iPad 标签（双写端点请求体，决策 #9）。

    labelIds 为「替换式」完整标签集合（labelid[]），后端先驱动 iPad 侧
    `UserAddLabelsReq` 生效，再落 Morphix 侧双写（重写 customer_profiles.tags
    镜像 + 重建 iPad 标签关系）。
    """
    labelIds: list[str] = []


class MessageExtDTO(BaseModel):
    """扩展消息（含 serverId/msgType/direction/contentType/media）。"""
    id: str
    conversationId: str
    senderType: str = "user"
    content: str = ""
    createdAt: str = ""
    serverId: str = ""
    msgType: int = 0
    senderId: str = ""
    direction: str = "inbound"
    contentType: str = "text"  # text | image | file
    mediaUrl: str = ""
    mediaMeta: Any = None
    isRead: bool = False
    channelAccountId: str = ""


class BackfillResultDTO(BaseModel):
    """消息历史回填结果。"""
    accountId: str = ""
    sessionId: str = ""
    upserted: int = 0
    triggered: bool = False
    message: str = ""


class SendMediaResultDTO(BaseModel):
    """富媒体发送结果。"""
    msgId: str = ""
    serverId: str = ""
    contentType: str = "image"
    mediaUrl: str = ""
    ok: bool = True


class CallbackPayloadDTO(BaseModel):
    """iPad 实时回调负载（POST /wxwork/callback）。"""
    uuid: str = ""
    data: Any = None  # 回调业务体（协议字段名 `json`，此处改名避免遮蔽 BaseModel.json）
    type: str = ""


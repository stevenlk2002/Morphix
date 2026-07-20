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


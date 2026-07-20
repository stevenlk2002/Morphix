"""运营任务 Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ContentBlock(BaseModel):
    """内容块（P0 仅文本，P1 扩展图片/视频/文件/卡片链接）。"""
    type: str = "text"
    content: str = ""


class TaskTargetInput(BaseModel):
    """创建任务时的运营对象输入。"""
    session_id: str = ""
    account_id: str = ""
    target_type: str = "static"


class OperationTaskCreateRequest(BaseModel):
    """创建运营任务请求体。"""
    name: str
    task_type: str = "群发任务"
    channel_type: str = "企业微信"
    session_type: str = "群聊"
    content_blocks: List[ContentBlock] = []
    hosting_action: str = "保持不变"
    run_frequency: str = "一次"
    run_time: str = ""
    effective_start: str = ""
    effective_end: str = ""
    cron_expression: str = ""
    schedule_type: str = ""
    schedule_config: str = ""
    targets: List[TaskTargetInput] = []


class OperationTaskUpdateRequest(BaseModel):
    """更新运营任务请求体（所有字段可选）。"""
    name: Optional[str] = None
    task_type: Optional[str] = None
    channel_type: Optional[str] = None
    session_type: Optional[str] = None
    content_blocks: Optional[List[ContentBlock]] = None
    hosting_action: Optional[str] = None
    run_frequency: Optional[str] = None
    run_time: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    cron_expression: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[str] = None
    enabled: Optional[bool] = None


class OperationTaskResponse(BaseModel):
    """运营任务响应（列表项 + 详情）。"""
    id: str
    name: str
    task_type: str
    channel_type: str
    session_type: str
    content_blocks: List[ContentBlock] = []
    hosting_action: str
    run_frequency: str
    run_time: str
    effective_start: str
    effective_end: str
    cron_expression: str
    schedule_type: str = ""
    schedule_config: str = ""
    run_status: str
    enabled: bool
    next_run_time: str
    target_count: int = 0
    created_at: str
    updated_at: str


class OperationTaskDetailResponse(OperationTaskResponse):
    """运营任务详情（含 targets 列表）。"""
    targets: List[OperationTaskTargetResponse] = []


class OperationTaskTargetResponse(BaseModel):
    """运营任务目标响应。"""
    id: str
    task_id: str
    target_type: str
    session_id: str
    session_name: str = ""
    account_name: str = ""
    session_type: str = ""
    hosted_status: str = ""
    filter_rules: Any = Field(default_factory=dict)


class TargetSessionResponse(BaseModel):
    """可选目标会话。"""
    id: str
    name: str
    account_name: str = ""
    session_type: str = ""
    hosted_status: str = ""
    add_time: str = ""
    selected: bool = False


class OperationTaskTargetsUpdateRequest(BaseModel):
    """全量替换运营对象请求体。"""
    targets: List[TaskTargetInput] = []


class OperationTaskListResponse(BaseModel):
    """运营任务列表分页信封。"""
    items: List[OperationTaskResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---- 新增：运营对象选择器相关模型 ----

class TargetSessionDetailResponse(BaseModel):
    """目标会话详情（含完整字段用于表格展示）。"""
    id: str
    name: str
    avatar: str = ""
    account_id: str = ""
    account_name: str = ""
    channel_type: str = ""
    session_type: str = ""
    hosted_status: str = ""
    hosted_bot_id: str = ""
    hosted_bot_name: str = ""
    hosting_chain: str = ""
    add_time: str = ""
    customer_nickname: str = ""
    customer_remark: str = ""
    selected: bool = False


class HostingAccountResponse(BaseModel):
    """托管账号选项。"""
    id: str
    channel: str = ""
    account_name: str = ""
    display_name: str = ""


class HostingBotResponse(BaseModel):
    """托管机器人选项。"""
    id: str
    name: str = ""
    status: str = ""


class TargetSessionQueryParams(BaseModel):
    """目标会话查询参数。"""
    channel: str = ""
    session_type: str = "single"  # single | group
    keyword: str = ""
    hosting_account_id: str = ""
    hosting_bot_id: str = ""
    tag_id: str = ""
    tag_relation: str = "and"  # and | or
    page: int = 1
    page_size: int = 20


class TargetSessionListResponse(BaseModel):
    """目标会话分页响应。"""
    items: List[TargetSessionDetailResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---- 朋友圈渠道账号 ----

class ChannelAccountResponse(BaseModel):
    """渠道账号（用于朋友圈任务选择运营对象）。"""
    id: str
    account_name: str = ""
    channel_type: str = ""
    status: str = ""
    display_name: str = ""


# ---- AI Cron 生成 ----

class AICronRequest(BaseModel):
    """AI Cron 生成请求体。"""
    prompt: str


class AICronResponse(BaseModel):
    """AI Cron 生成响应。"""
    cron: str
    explanation: str = ""

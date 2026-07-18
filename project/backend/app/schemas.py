"""请求/响应 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

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


class KnowledgeUpdateRequest(BaseModel):
    question: str
    answer: str
    tags: list[str] = []
    source: str = "手动录入"


class MaterialCreateRequest(BaseModel):
    name: str
    type: str
    size: int
    category: str = "未分类"
    url: Optional[str] = None


"""运营SOP Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


# ---- 流程节点 ----

class SopNodeConfig(BaseModel):
    """流程节点配置（与前端类型一致）。"""
    channel: str = ""
    filterType: str = ""
    dynamicFilter: dict = {}
    staticFilter: dict = {}
    stopWhenNotMatch: bool = False
    triggerType: str = ""
    triggerConfig: dict = {}
    contentType: str = "text"
    content: str = ""
    hours: float = 0
    # attr node
    addTagIds: List[str] = []
    removeTagIds: List[str] = []
    # robot node
    robotId: str = ""
    # runRobot node
    runRobotId: str = ""


class SopNode(BaseModel):
    """SOP 流程节点。"""
    id: str
    type: str  # settings | message | attr | robot | runRobot | delay | group-settings
    x: float = 0
    y: float = 0
    config: dict = {}


# ---- 请求模型 ----

class SopCreateRequest(BaseModel):
    """创建 SOP 请求体。"""
    name: str
    type: str = "customer"  # customer | group
    channel: str = "企业微信"
    trigger_type: str = ""
    trigger_config: dict = {}
    nodes: List[SopNode] = []


class SopUpdateRequest(BaseModel):
    """更新 SOP 请求体（所有字段可选）。"""
    name: Optional[str] = None
    type: Optional[str] = None
    channel: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    nodes: Optional[List[SopNode]] = None


class SopToggleRequest(BaseModel):
    """启停切换请求。"""
    enabled: bool


# ---- 响应模型 ----

class SopResponse(BaseModel):
    """SOP 列表项响应。"""
    id: str
    name: str
    type: str
    channel: str
    enabled: bool
    status: str
    trigger_type: str
    trigger_config: dict
    nodes: List[dict] = []
    created_at: str
    updated_at: str


class SopDetailResponse(SopResponse):
    """SOP 详情响应（与列表一致，nodes 为完整流程）。"""
    pass


class SopDeleteResponse(BaseModel):
    """删除响应。"""
    id: str
    deleted: bool


# ---- 运行记录 ----

class SopRecordResponse(BaseModel):
    """SOP 运行记录响应。"""
    id: str
    sop_id: str
    run_time: str
    run_status: str
    error_message: str
    created_at: str

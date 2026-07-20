"""数据面板 Pydantic 请求/响应模型。

端点：
- GET /api/data-panel/metrics → DataPanelMetricsResponse
- 后续可扩展 POST /api/data-panel/export 等。

字段名与前端 TypeScript 类型严格一致，使用 snake_case。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DailyMetric(BaseModel):
    """单日指标（柱状图 6 维 + 折线图 3 比率）。"""

    model_config = ConfigDict(populate_by_name=True)

    date: str = Field(..., description="日期，格式 YYYY-MM-DD")
    new_sessions: int = Field(default=0, description="新增会话数")
    hosted_sessions: int = Field(default=0, description="托管会话数")
    bot_processed_sessions: int = Field(default=0, description="机器人处理会话数")
    total_messages: int = Field(default=0, description="总消息数")
    bot_processed_messages: int = Field(default=0, description="机器人处理消息数")
    bot_transfers: int = Field(default=0, description="机器人转人工数")
    msg_rate: float = Field(default=0.0, description="机器人消息处理率（%）")
    session_rate: float = Field(default=0.0, description="机器人会话处理率（%）")
    transfer_rate: float = Field(default=0.0, description="机器人转人工率（%）")


class MetricsTotal(BaseModel):
    """筛选期内聚合总计。"""

    model_config = ConfigDict(populate_by_name=True)

    new_sessions: int = Field(default=0, description="新增会话数")
    hosted_sessions: int = Field(default=0, description="托管会话数")
    bot_processed_sessions: int = Field(default=0, description="机器人处理会话数")
    total_messages: int = Field(default=0, description="总消息数")
    bot_processed_messages: int = Field(default=0, description="机器人处理消息数")
    bot_transfers: int = Field(default=0, description="机器人转人工数")
    msg_rate: float = Field(default=0.0, description="机器人消息处理率（%）")
    session_rate: float = Field(default=0.0, description="机器人会话处理率（%）")
    transfer_rate: float = Field(default=0.0, description="机器人转人工率（%）")


class DataPanelMetricsResponse(BaseModel):
    """GET /api/data-panel/metrics 响应体。"""

    total: MetricsTotal
    daily: List[DailyMetric]


class FilterOption(BaseModel):
    """下拉选项（渠道/账号/机器人）。"""

    value: str
    label: str


class DataPanelFilterOptionsResponse(BaseModel):
    """筛选器下拉选项响应。"""

    channels: List[FilterOption]
    accounts: List[FilterOption]
    bots: List[FilterOption]

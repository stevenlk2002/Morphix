"""运营任务路由。

端点：
- GET    /api/operations/tasks           → 任务列表（分页+筛选）
- POST   /api/operations/tasks           → 创建任务（含 targets）
- GET    /api/operations/tasks/{id}      → 任务详情（含 targets）
- PUT    /api/operations/tasks/{id}      → 更新任务字段
- PATCH  /api/operations/tasks/{id}/toggle → 启停切换
- GET    /api/operations/tasks/{id}/targets → 获取运营对象
- PUT    /api/operations/tasks/{id}/targets → 设置运营对象
- DELETE /api/operations/tasks/{id}      → 删除任务
- GET    /api/operations/targets/sessions → 可用会话列表
- GET    /api/operations/target-sessions → 运营对象选择器 v2（分页+多条件）
- GET    /api/operations/hosting-accounts → 托管账号列表
- GET    /api/operations/hosting-bots    → 托管机器人列表
- GET    /api/operations/tags            → 客户标签列表
- GET    /api/operations/tag-groups      → 标签分组列表
- POST   /api/operations/ai-cron         → AI 生成 Cron 表达式
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from ..database import get_backend
from ..operations_repository import OperationTaskRepository
from ..operations_schemas import (
    AICronRequest,
    AICronResponse,
    ChannelAccountResponse,
    HostingAccountResponse,
    HostingBotResponse,
    OperationTaskCreateRequest,
    OperationTaskDetailResponse,
    OperationTaskListResponse,
    OperationTaskResponse,
    OperationTaskTargetResponse,
    OperationTaskTargetsUpdateRequest,
    OperationTaskUpdateRequest,
    TargetSessionDetailResponse,
    TargetSessionListResponse,
    TargetSessionResponse,
)

router = APIRouter(prefix="/operations", tags=["operations"])


def _repo() -> OperationTaskRepository:
    return OperationTaskRepository(get_backend())


def _parse_content_blocks(raw: str) -> list:
    """将 content_blocks JSON 字符串解析为列表。"""
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _prepare_task_item(item: dict) -> dict:
    """预处理任务 dict，将 JSON 字符串字段转为 Python 对象。"""
    result = dict(item)
    result["content_blocks"] = _parse_content_blocks(item.get("content_blocks", "[]"))
    return result


# ---- 任务列表 ----

@router.get("/tasks")
def list_tasks(
    search: Optional[str] = None,
    type: Optional[str] = Query(None, alias="type"),
    enabled: Optional[str] = None,
    run_status: Optional[str] = None,
    sortBy: str = "created_at",
    sortOrder: str = "DESC",
):
    """分页查询运营任务列表，支持筛选与排序。"""
    repo = _repo()
    items, total = repo.list_all(
        search=search,
        task_type=type,
        enabled=enabled,
        run_status=run_status,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    # 直接返回数组（无分页信封，与现有端点风格一致）
    return [OperationTaskResponse(**_prepare_task_item(item)) for item in items]


# ---- 创建任务 ----

@router.post("/tasks", status_code=201)
def create_task(body: OperationTaskCreateRequest):
    """创建运营任务（事务写入主表 + 目标表）。"""
    repo = _repo()
    data = body.model_dump()
    # 序列化 content_blocks 为 JSON 字符串
    if isinstance(data.get("content_blocks"), list):
        data["content_blocks"] = json.dumps(data["content_blocks"], ensure_ascii=False)
    result = repo.create(data)
    return OperationTaskResponse(**_prepare_task_item(result))


# ---- 任务详情 ----

@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """获取运营任务详情（含 targets 列表）。"""
    repo = _repo()
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    targets = repo.list_targets(task_id)
    return OperationTaskDetailResponse(
        **_prepare_task_item(task),
        targets=[OperationTaskTargetResponse(**t) for t in targets],
    )


# ---- 更新任务 ----

@router.put("/tasks/{task_id}")
def update_task(task_id: str, body: OperationTaskUpdateRequest):
    """更新运营任务字段（仅更新传入的非 None 字段）。"""
    repo = _repo()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    # 序列化 content_blocks
    if "content_blocks" in data and isinstance(data["content_blocks"], list):
        data["content_blocks"] = json.dumps(data["content_blocks"], ensure_ascii=False)
    result = repo.update(task_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    return OperationTaskResponse(**_prepare_task_item(result))


# ---- 启停切换 ----

@router.patch("/tasks/{task_id}/toggle")
def toggle_task(task_id: str):
    """翻转任务启用状态。"""
    repo = _repo()
    result = repo.toggle(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    return OperationTaskResponse(**_prepare_task_item(result))


# ---- 删除任务 ----

@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """删除运营任务（CASCADE 自动删除关联 targets）。"""
    repo = _repo()
    existing = repo.get(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    repo.delete(task_id)
    return {"id": task_id, "deleted": True}


# ---- 运营对象 ----

@router.get("/tasks/{task_id}/targets")
def list_targets(task_id: str):
    """获取运营任务的运营对象列表（JOIN channel_sessions）。"""
    repo = _repo()
    existing = repo.get(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    targets = repo.list_targets(task_id)
    return [OperationTaskTargetResponse(**t) for t in targets]


@router.put("/tasks/{task_id}/targets")
def set_targets(task_id: str, body: OperationTaskTargetsUpdateRequest):
    """全量替换运营对象（DELETE + INSERT，事务）。"""
    repo = _repo()
    existing = repo.get(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    targets_data = [{"session_id": t.session_id, "target_type": t.target_type} for t in body.targets]
    repo.set_targets(task_id, targets_data)
    targets = repo.list_targets(task_id)
    return [OperationTaskTargetResponse(**t) for t in targets]


# ---- 可用会话 ----

@router.get("/targets/sessions")
def list_target_sessions(
    account_id: Optional[str] = None,
    search: Optional[str] = None,
    session_type: Optional[str] = None,
    task_id: Optional[str] = None,
    channel: Optional[str] = None,
):
    """列出可作为运营对象的 channel_sessions（可选标记已选 + 按渠道过滤）。"""
    repo = _repo()
    sessions = repo.list_sessions_for_targeting(
        account_id=account_id,
        search=search,
        session_type=session_type,
        task_id=task_id,
        channel=channel,
    )
    return [TargetSessionResponse(**s) for s in sessions]


# ---- 新增：运营对象选择器 v2 ----

@router.get("/target-sessions")
def list_target_sessions_v2(
    channel: str = Query("", description="渠道（如 企业微信）"),
    sessionType: str = Query("single", description="会话类型: single(单聊) | group(群聊)"),
    keyword: str = Query("", description="搜索关键词"),
    hostingAccountId: str = Query("", alias="hostingAccountId", description="托管账号 ID"),
    hostingBotId: str = Query("", alias="hostingBotId", description="托管机器人 ID"),
    tagId: str = Query("", alias="tagId", description="标签 ID"),
    tagRelation: str = Query("and", alias="tagRelation", description="标签关系: and | or"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=100, alias="pageSize", description="每页数量"),
):
    """运营对象选择器 v2：分页 + 多条件筛选。

    单聊模式 → 返回好友 members（含 name/avatar/accountId/channelType/addedAt/hostingStatus）
    群聊模式 → 返回 groups（含 name/memberCount/ownerName/accountId/addedAt/hostingStatus）
    """
    repo = _repo()
    normalized_session_type = "single" if sessionType in ("single", "单聊") else "group"
    items, total = repo.list_target_sessions_v2(
        channel=channel,
        session_type=normalized_session_type,
        keyword=keyword,
        hosting_account_id=hostingAccountId,
        hosting_bot_id=hostingBotId,
        tag_id=tagId,
        tag_relation=tagRelation,
        page=page,
        page_size=pageSize,
    )
    has_more = (page * pageSize) < total
    return TargetSessionListResponse(
        items=[TargetSessionDetailResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=pageSize,
        has_more=has_more,
    )


@router.get("/hosting-accounts")
def list_hosting_accounts(
    channel: str = Query("", description="渠道筛选"),
):
    """列出可用于托管账号筛选的渠道账号列表。"""
    repo = _repo()
    accounts = repo.list_hosting_accounts(channel=channel)
    return [HostingAccountResponse(**a) for a in accounts]


@router.get("/hosting-bots")
def list_hosting_bots():
    """列出已上线的机器人列表。"""
    repo = _repo()
    bots = repo.list_hosting_bots()
    return [HostingBotResponse(**b) for b in bots]


@router.get("/tags")
def list_tags():
    """列出所有客户标签（含分组信息），用于运营对象动态筛选。"""
    repo = _repo()
    tags = repo.list_tags_for_targeting()
    return tags


@router.get("/tag-groups")
def list_tag_groups():
    """列出所有标签分组。"""
    repo = _repo()
    groups = repo.list_tag_groups_for_targeting()
    return groups


# ---- 朋友圈渠道账号 ----

@router.get("/channel-accounts")
def list_channel_accounts(
    channel: str = Query("", description="渠道类型筛选：wecom | wechat | whatsapp"),
):
    """列出指定渠道下的所有账号（含在线状态），供朋友圈任务选择运营对象。"""
    repo = _repo()
    accounts = repo.list_channel_accounts_for_moments(channel=channel)
    return [ChannelAccountResponse(**a) for a in accounts]


# ---- AI Cron 生成 ----

def _build_cron_prompt(user_prompt: str) -> str:
    """构建发给 LLM 的 cron 生成 prompt。"""
    return (
        "你是一个 Cron 表达式专家。请根据用户的描述生成一个标准的 Unix cron 表达式。\n"
        "cron 格式：分 时 日 月 周（5 个字段，空格分隔）。\n"
        "请只返回 JSON 格式：{\"cron\": \"<表达式>\", \"explanation\": \"<简短解释>\"}\n"
        "不要返回任何其他内容。\n\n"
        f"用户描述：{user_prompt}"
    )


_MOCK_CRON_RESPONSES: list[dict] = [
    {"cron": "0 9 * * 1-5", "explanation": "每周一到周五早上9点执行"},
    {"cron": "0 8 * * *", "explanation": "每天早上8点执行"},
    {"cron": "0 0 1 * *", "explanation": "每月1号零点执行"},
    {"cron": "*/30 * * * *", "explanation": "每30分钟执行一次"},
    {"cron": "0 10 * * 0", "explanation": "每周日早上10点执行"},
]


def _parse_chinese_hour(text: str) -> int | None:
    """从中文描述中提取小时（0-23）。支持：3点/下午3点/三点/15:00。"""
    import re
    # 24h 数字（15:30 → 15）
    m = re.search(r"(\d{1,2})\s*[:：]\s*\d{1,2}", text)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return h
    # 中文数字
    cn_map = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
    m = re.search(r"([零一二三四五六七八九十]+|1\d|\d{1,2})\s*点", text)
    if m:
        raw = m.group(1)
        h = cn_map.get(raw)
        if h is None and raw.isdigit():
            h = int(raw)
        if h is not None and 0 <= h <= 23:
            # 下午/晚上 +12（12 点除外）
            if h <= 12 and ("下午" in text or "晚上" in text):
                h = h if h == 12 else h + 12
            return h
    return None


def _parse_chinese_minute(text: str) -> int | None:
    """从中文描述中提取分钟（0-59）。"""
    import re
    m = re.search(r"(\d{1,2})\s*分钟", text)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 59:
            return v
    return None


def _parse_chinese_weekday(text: str) -> int | None:
    """从中文描述中提取周几（0=周日, 1=周一 ... 6=周六）。"""
    cn = {"日": 0, "天": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "末": 6}
    for k, v in cn.items():
        if f"周{k}" in text:
            return v
    return None


def _parse_chinese_day_of_month(text: str) -> int | None:
    """从中文描述中提取日期（1-31）。"""
    import re
    m = re.search(r"(\d{1,2})\s*[日号]", text)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 31:
            return v
    return None


def _mock_cron_response(prompt: str) -> dict:
    """根据用户 prompt 智能解析生成 cron 表达式。"""
    hour = _parse_chinese_hour(prompt)
    minute = _parse_chinese_minute(prompt)
    weekday = _parse_chinese_weekday(prompt)
    day_of_month = _parse_chinese_day_of_month(prompt)

    parts: list[str] = []
    explanation_parts: list[str] = []

    # 分钟
    if minute is not None:
        parts.append(f"*/{minute}")
        explanation_parts.append(f"每{minute}分钟")
    else:
        parts.append(str(minute if minute is not None else 0))

    # 小时
    if hour is not None:
        parts.append(str(hour))
        cn_h = {0: "零点", 12: "中午12点", 18: "下午6点", 23: "晚上11点"}.get(hour)
        explanation_parts.append(cn_h or f"{hour}点")
    else:
        parts.append("*")

    # 日期
    if day_of_month is not None:
        parts.append(str(day_of_month))
        explanation_parts.append(f"每月{day_of_month}号")
    else:
        parts.append("*")

    # 月
    parts.append("*")

    # 周几
    if weekday is not None:
        parts.append(str(weekday))
        wd_cn = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][weekday]
        explanation_parts.append(wd_cn)
    else:
        parts.append("*")

    cron = " ".join(parts)
    explanation = "".join(explanation_parts) + "执行"
    return {"cron": cron, "explanation": explanation}


async def _call_llm_for_cron(prompt: str) -> dict:
    """调用 LLM API 生成 cron 表达式。失败时返回 mock 兜底。"""
    api_key = os.getenv("MORPHIX_AI_API_KEY", "")
    base_url = os.getenv("MORPHIX_AI_BASE_URL", "")
    model = os.getenv("MORPHIX_AI_MODEL", "gpt-3.5-turbo")

    if not api_key or not base_url:
        return _mock_cron_response(prompt)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a cron expression generator. Always respond with valid JSON only."},
                        {"role": "user", "content": _build_cron_prompt(prompt)},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # 尝试从响应中提取 JSON
                if content.startswith("```"):
                    # 去掉 markdown 代码块包裹
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                parsed = json.loads(content)
                if "cron" in parsed:
                    return {"cron": parsed["cron"], "explanation": parsed.get("explanation", "")}
    except Exception:
        pass

    return _mock_cron_response(prompt)


@router.post("/ai-cron")
async def generate_cron(body: AICronRequest):
    """AI 生成 Cron 表达式。"""
    if not body.prompt or not body.prompt.strip():
        raise HTTPException(status_code=400, detail="请输入描述内容")
    result = await _call_llm_for_cron(body.prompt.strip())
    return AICronResponse(**result)

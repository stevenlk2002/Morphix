"""系统消息（消息中心）路由。

端点：
- GET  /api/messages                → 消息列表（分页 + tab 过滤 + 标题筛选）
- PUT  /api/messages/{msg_id}/read  → 标记单条消息为已读
- PUT  /api/messages/read-all       → 标记全部未读消息为已读

资源域裸数据返回（无信封），与 data_panel.py 风格一致。
DB 访问约定：
- backend.query(sql, params) 返回 list[dict]
- backend.execute(sql, params) 返回受影响行数（rowcount）
- 占位符统一使用 ?
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..database import get_backend

router = APIRouter(prefix="/messages", tags=["messages"])


def _row_to_dto(row: dict) -> dict:
    """将 DB 行转换为前端 DTO（字段重命名 + 布尔转换）。"""
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "time": row["msg_time"],
        "read": bool(row["is_read"]),
        "warn": bool(row["is_warning"]),
    }


@router.get("")
async def list_messages(
    tab: str = Query("unread", description="unread | read，无 all"),
    title: str = Query("", description="标题筛选，按 LIKE 匹配"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    pageSize: int = Query(20, ge=1, description="每页条数"),
) -> dict:
    """获取消息列表，支持 tab 过滤 / 标题筛选 / 分页。

    返回裸 JSON：
    {
      items: [{id,title,content,time,read,warn}],
      total, page, pageSize,
      titles: string[],   // 全量去重标题，供筛选下拉
      unreadCount: int    // is_read=0 总数
    }
    """
    backend = get_backend()

    is_read_filter = 1 if tab == "read" else 0
    where_clauses = ["is_read = ?"]
    where_params: list = [is_read_filter]
    if title:
        where_clauses.append("title LIKE ?")
        where_params.append(f"%{title}%")

    where_sql = " AND ".join(where_clauses)

    # ---- 当前筛选条件下的总数 ----
    count_rows = backend.query(
        f"SELECT COUNT(*) AS c FROM system_messages WHERE {where_sql}",
        tuple(where_params),
    )
    total = count_rows[0]["c"] if count_rows else 0

    # ---- 分页切片 ----
    offset = (page - 1) * pageSize
    item_rows = backend.query(
        f"SELECT * FROM system_messages WHERE {where_sql} "
        f"ORDER BY msg_time DESC LIMIT ? OFFSET ?",
        tuple(where_params) + (pageSize, offset),
    )
    items = [_row_to_dto(r) for r in item_rows]

    # ---- 全量去重标题（供筛选下拉，不受 tab/分页影响） ----
    title_rows = backend.query(
        "SELECT DISTINCT title FROM system_messages WHERE title != '' ORDER BY title"
    )
    titles = [r["title"] for r in title_rows]

    # ---- 未读总数 ----
    unread_rows = backend.query(
        "SELECT COUNT(*) AS c FROM system_messages WHERE is_read = 0"
    )
    unread_count = unread_rows[0]["c"] if unread_rows else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "titles": titles,
        "unreadCount": unread_count,
    }


@router.put("/{msg_id}/read")
async def mark_message_read(msg_id: str) -> dict:
    """标记单条消息为已读。"""
    backend = get_backend()
    backend.execute(
        "UPDATE system_messages SET is_read = 1 WHERE id = ?",
        (msg_id,),
    )
    return {"id": msg_id, "read": True}


@router.put("/read-all")
async def mark_all_messages_read() -> dict:
    """将所有未读消息标记为已读，返回更新条数。"""
    backend = get_backend()
    updated = backend.execute(
        "UPDATE system_messages SET is_read = 1 WHERE is_read = 0",
        (),
    )
    return {"updated": updated}

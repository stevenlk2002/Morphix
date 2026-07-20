"""运营任务数据访问层（Repository）。

遵循现有模式：所有 SQL 集中于此，Router 层只调用 Repository 方法。
列表查询统一返回 (items, total) 或带分页信封。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from .database import DatabaseBackend
from .schema import BOT_NAMES


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _row_to_task(row: dict) -> dict:
    """将 operation_tasks 行映射为 DTO。"""
    blocks_raw = row.get("content_blocks", "[]") or "[]"
    try:
        content_blocks = json.loads(blocks_raw)
    except (json.JSONDecodeError, TypeError):
        content_blocks = []
    return {
        "id": row["id"],
        "name": row["name"],
        "task_type": row["task_type"],
        "channel_type": row["channel_type"],
        "session_type": row["session_type"],
        "content_blocks": content_blocks,
        "hosting_action": row["hosting_action"],
        "run_frequency": row["run_frequency"],
        "run_time": row["run_time"],
        "effective_start": row["effective_start"],
        "effective_end": row["effective_end"],
        "cron_expression": row["cron_expression"],
        "schedule_type": row.get("schedule_type", ""),
        "schedule_config": row.get("schedule_config", ""),
        "run_status": row["run_status"],
        "enabled": bool(row["enabled"]),
        "next_run_time": row["next_run_time"],
        "target_count": row.get("target_count", 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_target(row: dict) -> dict:
    """将 operation_task_targets JOIN session 行映射为 DTO。"""
    filter_raw = row.get("filter_rules", "{}") or "{}"
    try:
        filter_rules = json.loads(filter_raw)
    except (json.JSONDecodeError, TypeError):
        filter_rules = {}
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "target_type": row["target_type"],
        "session_id": row["session_id"],
        "session_name": row.get("session_name", ""),
        "account_name": row.get("account_name", ""),
        "session_type": row.get("session_type", ""),
        "hosted_status": row.get("hosted_status", ""),
        "filter_rules": filter_rules,
    }


def _row_to_available_session(row: dict, selected_ids: Optional[set] = None) -> dict:
    """将 channel_sessions 行映射为可选会话 DTO。"""
    sid = row["id"]
    return {
        "id": sid,
        "name": row["name"],
        "account_name": row.get("account_name", ""),
        "session_type": row.get("session_type", ""),
        "hosted_status": row.get("hosted_status", ""),
        "add_time": row.get("add_time", ""),
        "selected": sid in (selected_ids or set()),
    }


class OperationTaskRepository:
    """运营任务仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    # ============ 任务 CRUD ============

    def list_all(
        self,
        search: Optional[str] = None,
        task_type: Optional[str] = None,
        enabled: Optional[str] = None,
        run_status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
    ) -> tuple[list[dict], int]:
        """分页查询运营任务列表，返回 (items, total)。"""
        # 安全排序列白名单
        allowed_sort = {"created_at", "updated_at", "name", "next_run_time", "task_type", "run_status"}
        col = sort_by if sort_by in allowed_sort else "created_at"
        order = "DESC" if sort_order.upper() == "DESC" else "ASC"

        where = ["1=1"]
        params: list = []

        if search:
            where.append("ot.name LIKE ?")
            params.append(f"%{search}%")
        if task_type:
            where.append("ot.task_type = ?")
            params.append(task_type)
        if enabled:
            if enabled == "enabled":
                where.append("ot.enabled = 1")
            elif enabled == "disabled":
                where.append("ot.enabled = 0")
        if run_status:
            where.append("ot.run_status = ?")
            params.append(run_status)

        where_sql = " AND ".join(where)

        # Total
        count_row = self._db.query_one(
            f"SELECT COUNT(*) AS c FROM operation_tasks ot WHERE {where_sql}",
            tuple(params),
        )
        total = int(count_row["c"]) if count_row else 0

        # 主查询（LEFT JOIN 计算 target_count）
        sql = f"""
        SELECT ot.*, COUNT(ott.id) AS target_count
        FROM operation_tasks ot
        LEFT JOIN operation_task_targets ott ON ott.task_id = ot.id
        WHERE {where_sql}
        GROUP BY ot.id
        ORDER BY ot.{col} {order}
        """
        rows = self._db.query(sql, tuple(params))
        return [{"id": r["id"], "name": r["name"], "task_type": r["task_type"],
                 "channel_type": r["channel_type"], "session_type": r["session_type"],
                 "content_blocks": r["content_blocks"], "hosting_action": r["hosting_action"],
                 "run_frequency": r["run_frequency"], "run_time": r["run_time"],
                 "effective_start": r["effective_start"], "effective_end": r["effective_end"],
                 "cron_expression": r["cron_expression"],
                 "schedule_type": r.get("schedule_type", ""), "schedule_config": r.get("schedule_config", ""),
                 "run_status": r["run_status"],
                 "enabled": r["enabled"], "next_run_time": r["next_run_time"],
                 "target_count": r["target_count"], "created_at": r["created_at"],
                 "updated_at": r["updated_at"]}
                for r in rows], total

    def get(self, task_id: str) -> Optional[dict]:
        """获取单个任务详情。"""
        row = self._db.query_one(
            """SELECT ot.*, COUNT(ott.id) AS target_count
               FROM operation_tasks ot
               LEFT JOIN operation_task_targets ott ON ott.task_id = ot.id
               WHERE ot.id = ?
               GROUP BY ot.id""",
            (task_id,),
        )
        if row is None:
            return None
        return {
            "id": row["id"], "name": row["name"], "task_type": row["task_type"],
            "channel_type": row["channel_type"], "session_type": row["session_type"],
            "content_blocks": row["content_blocks"], "hosting_action": row["hosting_action"],
            "run_frequency": row["run_frequency"], "run_time": row["run_time"],
            "effective_start": row["effective_start"], "effective_end": row["effective_end"],
            "cron_expression": row["cron_expression"],
            "schedule_type": row.get("schedule_type", ""), "schedule_config": row.get("schedule_config", ""),
            "run_status": row["run_status"],
            "enabled": row["enabled"], "next_run_time": row["next_run_time"],
            "target_count": row["target_count"], "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create(self, data: dict) -> dict:
        """创建运营任务（事务内写入主表 + 目标表）。"""
        task_id = _generate_id("opt")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content_blocks = data.get("content_blocks", [])
        blocks_json = json.dumps(content_blocks, ensure_ascii=False) if isinstance(content_blocks, list) else (content_blocks or "[]")

        with self._db.transaction() as tx:
            tx.execute(
                """INSERT INTO operation_tasks(
                    id, name, task_type, channel_type, session_type,
                    content_blocks, hosting_action, run_frequency, run_time,
                    effective_start, effective_end, cron_expression,
                    schedule_type, schedule_config,
                    run_status, enabled, next_run_time, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    data.get("name", ""),
                    data.get("task_type", "群发任务"),
                    data.get("channel_type", "企业微信"),
                    data.get("session_type", "群聊"),
                    blocks_json,
                    data.get("hosting_action", "保持不变"),
                    data.get("run_frequency", "一次"),
                    data.get("run_time", ""),
                    data.get("effective_start", ""),
                    data.get("effective_end", ""),
                    data.get("cron_expression", ""),
                    data.get("schedule_type", ""),
                    data.get("schedule_config", ""),
                    "未运行",
                    1,
                    data.get("run_time", ""),
                    now,
                    now,
                ),
            )

            targets = data.get("targets", [])
            for target in targets:
                target_id = _generate_id("optt")
                # 支持 account_id（朋友圈任务）和 session_id（常规任务）
                target_ref = target.get("account_id") or target.get("session_id", "")
                tx.execute(
                    "INSERT INTO operation_task_targets(id, task_id, target_type, session_id, filter_rules) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (target_id, task_id, target.get("target_type", "static"), target_ref, "{}"),
                )

        return self.get(task_id) or {"id": task_id}

    def update(self, task_id: str, data: dict) -> Optional[dict]:
        """更新运营任务字段（仅更新传入的非 None 字段）。"""
        existing = self._db.query_one("SELECT * FROM operation_tasks WHERE id = ?", (task_id,))
        if existing is None:
            return None

        updates: list[str] = []
        params: list = []

        field_map = {
            "name": "name",
            "task_type": "task_type",
            "channel_type": "channel_type",
            "session_type": "session_type",
            "hosting_action": "hosting_action",
            "run_frequency": "run_frequency",
            "run_time": "run_time",
            "effective_start": "effective_start",
            "effective_end": "effective_end",
            "cron_expression": "cron_expression",
            "schedule_type": "schedule_type",
            "schedule_config": "schedule_config",
        }

        for key, col in field_map.items():
            if key in data and data[key] is not None:
                updates.append(f"{col} = ?")
                params.append(data[key])

        if "content_blocks" in data and data["content_blocks"] is not None:
            blocks = data["content_blocks"]
            updates.append("content_blocks = ?")
            params.append(json.dumps(blocks, ensure_ascii=False) if isinstance(blocks, list) else blocks)

        if "enabled" in data and data["enabled"] is not None:
            updates.append("enabled = ?")
            params.append(1 if data["enabled"] else 0)

        if not updates:
            return self.get(task_id)

        updates.append("updated_at = ?")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params.append(now)
        params.append(task_id)

        self._db.execute(
            f"UPDATE operation_tasks SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        return self.get(task_id)

    def toggle(self, task_id: str) -> Optional[dict]:
        """切换启用状态（翻转 enabled），返回更新后的任务。"""
        existing = self._db.query_one("SELECT * FROM operation_tasks WHERE id = ?", (task_id,))
        if existing is None:
            return None

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._db.execute(
            "UPDATE operation_tasks SET enabled = CASE WHEN enabled = 1 THEN 0 ELSE 1 END, updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        return self.get(task_id)

    def delete(self, task_id: str) -> None:
        """删除运营任务（CASCADE 自动删除关联 targets）。"""
        self._db.execute("DELETE FROM operation_tasks WHERE id = ?", (task_id,))

    # ============ 运营对象 ============

    def list_targets(self, task_id: str) -> list[dict]:
        """获取指定任务的运营对象列表（JOIN channel_sessions）。"""
        rows = self._db.query(
            """SELECT ott.*, cs.name AS session_name, ca.account_name,
                      cs.session_type, cs.hosted_status
               FROM operation_task_targets ott
               JOIN channel_sessions cs ON cs.id = ott.session_id
               LEFT JOIN channel_accounts ca ON ca.id = cs.account_id
               WHERE ott.task_id = ?
               ORDER BY ott.created_at""",
            (task_id,),
        )
        return [_row_to_target(r) for r in rows]

    def set_targets(self, task_id: str, targets: list[dict]) -> None:
        """全量替换运营对象（DELETE + INSERT，事务）。"""
        with self._db.transaction() as tx:
            tx.execute("DELETE FROM operation_task_targets WHERE task_id = ?", (task_id,))
            for target in targets:
                target_id = _generate_id("optt")
                tx.execute(
                    "INSERT INTO operation_task_targets(id, task_id, target_type, session_id, filter_rules) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (target_id, task_id, target.get("target_type", "static"), target["session_id"], "{}"),
                )

    # ============ 可选会话（用于创建/编辑时选择运营对象） ============

    def list_sessions_for_targeting(
        self,
        account_id: Optional[str] = None,
        search: Optional[str] = None,
        session_type: Optional[str] = None,
        task_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> list[dict]:
        """列出可作为运营对象的 sessions/contacts，支持按渠道过滤。"""
        # 先查出已选 session ids
        selected_ids: set[str] = set()
        if task_id:
            sel_rows = self._db.query(
                "SELECT session_id FROM operation_task_targets WHERE task_id = ?",
                (task_id,),
            )
            selected_ids = {r["session_id"] for r in sel_rows}

        where = ["1=1"]
        params: list = []

        if account_id:
            where.append("cs.account_id = ?")
            params.append(account_id)
        if search:
            where.append("cs.name LIKE ?")
            params.append(f"%{search}%")
        if session_type:
            where.append("cs.session_type = ?")
            params.append(session_type)
        if channel:
            where.append("ca.channel_type = ?")
            params.append(channel)

        where_sql = " AND ".join(where)

        rows = self._db.query(
            f"""SELECT cs.*, ca.account_name, ca.channel_type
                FROM channel_sessions cs
                LEFT JOIN channel_accounts ca ON ca.id = cs.account_id
                WHERE {where_sql}
                ORDER BY cs.add_time DESC, cs.id""",
            tuple(params),
        )
        return [_row_to_available_session(r, selected_ids) for r in rows]

    def list_hosting_accounts(self, channel: Optional[str] = None) -> list[dict]:
        """列出托管账号（可按渠道筛选），供运营对象选择下拉。"""
        where = ""
        params = ()
        if channel:
            where = " WHERE channel_type = ?"
            params = (channel,)
        rows = self._db.query(
            f"SELECT id, account_name, channel_type, channel, status FROM channel_accounts{where} ORDER BY account_name",
            params,
        )
        return [
            {
                "id": r["id"],
                "channel": r.get("channel", ""),
                "account_name": r.get("account_name", ""),
                "display_name": f"{r.get('channel', '')} / {r.get('account_name', '')}",
            }
            for r in rows
        ]

    def list_hosting_bots(self) -> list[dict]:
        """列出已上线机器人，供运营对象选择下拉。"""
        rows = self._db.query(
            "SELECT id, name, status FROM bots WHERE status IN ('online', '已上线', 'running') ORDER BY name"
        )
        return [{"id": r["id"], "name": r["name"], "status": r["status"]} for r in rows]

    # ============ 新增：运营对象选择器 v2 ============

    def list_target_sessions_v2(
        self,
        channel: str = "",
        session_type: str = "single",
        keyword: str = "",
        hosting_account_id: str = "",
        hosting_bot_id: str = "",
        tag_id: str = "",
        tag_relation: str = "and",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """列出可作为运营对象的会话（v2，支持分页 + 多条件筛选）。

        session_type 映射：
        - "single" / "单聊" → 好友成员（含昵称/备注等客户信息）
        - "group" / "群聊"  → 群组
        """
        where: list[str] = ["1=1"]
        params: list = []

        # 渠道筛选
        if channel:
            # channel 匹配 channel_accounts.channel 或 channel_sessions.channel
            where.append("(ca.channel = ? OR cs.channel = ?)")
            params.extend([channel, channel])

        # 会话类型筛选
        if session_type in ("single", "单聊"):
            where.append("(cs.session_type IN ('外部联系人', '单聊', 'single') OR cs.external_tag = '外部')")
        elif session_type in ("group", "群聊"):
            where.append("cs.session_type IN ('群聊', 'group')")

        # 关键词搜索
        if keyword:
            where.append("(cs.name LIKE ? OR cc.name LIKE ? OR cc.remark LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        # 托管账号筛选
        if hosting_account_id:
            where.append("cs.account_id = ?")
            params.append(hosting_account_id)

        # 托管机器人筛选
        if hosting_bot_id:
            where.append("cs.hosted_bot_id = ?")
            params.append(hosting_bot_id)

        where_sql = " AND ".join(where)

        # 计数
        count_sql = f"""
            SELECT COUNT(*) AS c
            FROM channel_sessions cs
            LEFT JOIN channel_accounts ca ON ca.id = cs.account_id
            LEFT JOIN channel_contacts cc ON cc.id = cs.contact_id
            WHERE {where_sql}
        """
        count_row = self._db.query_one(count_sql, tuple(params))
        total = int(count_row["c"]) if count_row else 0

        # 分页查询
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT cs.*, ca.account_name, ca.channel AS account_channel,
                   cc.name AS customer_nickname, cc.remark AS customer_remark,
                   cc.nickname AS contact_nickname
            FROM channel_sessions cs
            LEFT JOIN channel_accounts ca ON ca.id = cs.account_id
            LEFT JOIN channel_contacts cc ON cc.id = cs.contact_id
            WHERE {where_sql}
            ORDER BY cs.add_time DESC, cs.id
            LIMIT ? OFFSET ?
        """
        rows = self._db.query(query_sql, tuple(params) + (page_size, offset))

        items = []
        for r in rows:
            # Resolve hosted bot name
            hosted_bot_name = ""
            bot_id = r.get("hosted_bot_id")
            if bot_id:
                hosted_bot_name = BOT_NAMES.get(bot_id, bot_id)

            items.append({
                "id": r["id"],
                "name": r.get("name") or "",
                "avatar": "",
                "account_id": r.get("account_id") or "",
                "account_name": r.get("account_name") or "",
                "channel_type": r.get("channel_type") or "",
                "session_type": r.get("session_type") or "",
                "hosted_status": r.get("hosted_status") or "",
                "hosted_bot_id": r.get("hosted_bot_id") or "",
                "hosted_bot_name": hosted_bot_name,
                "hosting_chain": r.get("hosting_chain") or "-",
                "add_time": r.get("add_time") or "",
                "customer_nickname": (r.get("customer_nickname") or r.get("contact_nickname") or ""),
                "customer_remark": (r.get("customer_remark") or ""),
                "selected": False,
            })
        return items, total

    def list_tags_for_targeting(self) -> list[dict]:
        """列出所有客户标签（含分组信息），用于运营对象动态筛选。"""
        rows = self._db.query(
            """SELECT ct.*, ctg.name AS group_name
               FROM customer_tags ct
               LEFT JOIN customer_tag_groups ctg ON ctg.id = ct.group_id
               ORDER BY ctg.name, ct.name"""
        )
        return [
            {
                "id": r["id"],
                "group_id": r.get("group_id", ""),
                "name": r.get("name", ""),
                "color": r.get("color", "blue"),
                "group_name": r.get("group_name", ""),
            }
            for r in rows
        ]

    def list_tag_groups_for_targeting(self) -> list[dict]:
        """列出所有标签分组。"""
        rows = self._db.query(
            """SELECT * FROM customer_tag_groups ORDER BY is_hot DESC, name"""
        )
        return [
            {"id": r["id"], "name": r.get("name", ""), "is_hot": bool(r.get("is_hot", 0))}
            for r in rows
        ]

    # ============ 朋友圈渠道账号 ============

    def list_channel_accounts_for_moments(self, channel: str = "") -> list[dict]:
        """列出指定渠道下的所有账号（含在线状态），供朋友圈任务选择运营对象。

        按 channel_type 筛选。channel 参数使用后端值：wecom / wechat / whatsapp。
        """
        where = ""
        params: tuple = ()
        if channel:
            where = " WHERE channel_type = ?"
            params = (channel,)
        rows = self._db.query(
            f"SELECT id, account_name, channel_type, status FROM channel_accounts{where} ORDER BY account_name",
            params,
        )
        return [
            {
                "id": r["id"],
                "account_name": r["account_name"],
                "channel_type": r["channel_type"],
                "status": r["status"],
                "display_name": f"{r['channel_type']} / {r['account_name']}",
            }
            for r in rows
        ]

"""数据访问层（Repository）。

设计目标：
- 所有 SQL 集中在此，Router 层只调用 Repository 方法，不感知 SQL。
- Repository 只依赖 `DatabaseBackend` 接口，可无痛切换 SQLite / PostgreSQL。
- 列表查询统一支持分页，兑现「分页/索引规范」性能落地要求。

行 -> DTO 的映射保持与原 main.py 完全一致，确保对外 contract 不变。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from .database import DatabaseBackend
from .pagination import Pagination, normalize_pagination, paginate_result
from .schema import BOT_NAMES


def _generate_id(prefix: str) -> str:
    import uuid as _uuid
    return f"{prefix}_{_uuid.uuid4().hex[:8]}"


# ---- 行 -> DTO 映射（与原实现字段严格对齐）----
def row_to_bot(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "project": row["project"],
        "status": row["status"],
        "workflow": row["workflow"],
        "tone": row["tone"],
        "trainingPrompt": row["training_prompt"],
        "score": row["score"],
    }


def row_to_channel(row: dict) -> dict:
    return {
        "id": row["id"],
        "channel": row["channel"],
        "accountName": row["account_name"],
        "status": row["status"],
        "boundBot": row["bound_bot"],
        "dailyQuota": row["daily_quota"],
    }


def row_to_tag(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "color": row["color"], "rule": row["rule"]}


class AuditRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def record(self, action: str, target: str, detail: str) -> None:
        self._db.execute(
            "INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)",
            (action, target, detail),
        )

    def recent(self, limit: int = 50) -> list[dict]:
        return self._db.query(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    def recent_unread(self, limit: int = 8) -> list[dict]:
        """从审计事件派生未读通知（首页「未读消息」卡片）。

        MVP 阶段尚未落库独立的未读表，这里用最近审计事件映射成
        用户可理解的未读条目：每条审计事件 -> 一条通知。
        后续接入真实未读/消息中心时，替换为独立表查询即可。
        """
        rows = self._db.query(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        notifications: list[dict] = []
        for r in rows:
            action = (r.get("action") or "").lower()
            title = self._unread_title(action, r.get("target") or "")
            detail = r.get("detail") or ""
            notifications.append(
                {
                    "id": f"un-{r['id']}",
                    "title": title,
                    "desc": detail,
                    "time": r.get("created_at") or "",
                }
            )
        return notifications

    @staticmethod
    def _unread_title(action: str, target: str) -> str:
        """把审计 action 映射成前端未读通知的中文标题。

        action 取值来自真实审计事件：train_bot / create_bot /
        update_workflow_node / handoff / create_sop / create_channel_account /
        create_customer_tag 等。
        """
        mapping = {
            "handoff": f"{target} 转人工",
            "create_sop": f"新增 SOP：{target}",
            "create_bot": f"新增机器人：{target}",
            "train_bot": f"{target} 训练完成",
            "create_channel_account": f"新增渠道账号：{target}",
            "create_customer_tag": f"新增客户标签：{target}",
            "update_workflow_node": f"{target} 工作流节点更新",
        }
        return mapping.get(action, f"{target} 有更新")


class BotRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_all(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM bots ORDER BY created_at, id")
        return [row_to_bot(r) for r in rows]

    def list_paged(self, pagination: Pagination) -> tuple[list[dict], int]:
        total = self._count()
        rows = self._db.query(
            "SELECT * FROM bots ORDER BY created_at, id LIMIT ? OFFSET ?",
            (pagination.limit, pagination.offset),
        )
        return [row_to_bot(r) for r in rows], total

    def _count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) AS c FROM bots")
        return int(row["c"]) if row else 0

    def create(self, bot_id: str, name: str, project: str, workflow: str, tone: str, training_prompt: str) -> dict:
        self._db.execute(
            "INSERT INTO bots(id, name, project, status, workflow, tone, training_prompt, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (bot_id, name, project, "training", workflow, tone, training_prompt, 76),
        )
        return {
            "id": bot_id,
            "name": name,
            "project": project,
            "status": "training",
            "workflow": workflow,
            "tone": tone,
            "trainingPrompt": training_prompt,
            "score": 76,
        }

    def mark_trained(self, bot_id: str) -> None:
        self._db.execute(
            "UPDATE bots SET status = ?, score = MIN(score + 8, 99) WHERE id = ?",
            ("online", bot_id),
        )


class ChannelRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_all(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM channel_accounts ORDER BY created_at, id")
        return [row_to_channel(r) for r in rows]

    def list_paged(self, pagination: Pagination) -> tuple[list[dict], int]:
        total = self._count()
        rows = self._db.query(
            "SELECT * FROM channel_accounts ORDER BY created_at, id LIMIT ? OFFSET ?",
            (pagination.limit, pagination.offset),
        )
        return [row_to_channel(r) for r in rows], total

    def _count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) AS c FROM channel_accounts")
        return int(row["c"]) if row else 0

    def create(self, channel_id: str, channel: str, account_name: str, bound_bot: str, daily_quota: int) -> dict:
        self._db.execute(
            "INSERT INTO channel_accounts(id, channel, account_name, status, bound_bot, daily_quota) VALUES (?, ?, ?, ?, ?, ?)",
            (channel_id, channel, account_name, "online", bound_bot, daily_quota),
        )
        return {
            "id": channel_id,
            "channel": channel,
            "accountName": account_name,
            "status": "online",
            "boundBot": bound_bot,
            "dailyQuota": daily_quota,
        }


class TagRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_all(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM customer_tags ORDER BY created_at, id")
        return [row_to_tag(r) for r in rows]

    def upsert(self, tag_id: str, name: str, color: str, rule: str) -> dict:
        self._db.execute(
            "INSERT OR REPLACE INTO customer_tags(id, name, color, rule) VALUES (?, ?, ?, ?)",
            (tag_id, name, color, rule),
        )
        return {"id": tag_id, "name": name, "color": color, "rule": rule}

    def get(self, tag_id: str) -> Optional[dict]:
        row = self._db.query_one("SELECT * FROM customer_tags WHERE id = ?", (tag_id,))
        return row_to_tag(row) if row else None

    def update(self, tag_id: str, name: str, color: str, rule: str) -> None:
        self._db.execute(
            "UPDATE customer_tags SET name = ?, color = ?, rule = ? WHERE id = ?",
            (name, color, rule, tag_id),
        )

    def delete(self, tag_id: str) -> None:
        self._db.execute("DELETE FROM customer_tags WHERE id = ?", (tag_id,))


class WorkflowRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def node_rows(self, workflow_id: str) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM workflow_nodes WHERE workflow_id = ? ORDER BY node_order",
            (workflow_id,),
        )
        return [
            {
                "id": r["id"],
                "workflowId": r["workflow_id"],
                "order": r["node_order"],
                "nodeType": r["node_type"],
                "label": r["label"],
                "config": json.loads(r["config"] or "{}"),
            }
            for r in rows
        ]

    def get_node(self, workflow_id: str, node_id: str) -> Optional[dict]:
        return self._db.query_one(
            "SELECT * FROM workflow_nodes WHERE workflow_id = ? AND id = ?",
            (workflow_id, node_id),
        )

    def update_node(self, workflow_id: str, node_id: str, label: str, node_type: str, config_json: str) -> None:
        self._db.execute(
            "UPDATE workflow_nodes SET label = ?, node_type = ?, config = ? WHERE workflow_id = ? AND id = ?",
            (label, node_type, config_json, workflow_id, node_id),
        )

    def insert_node(self, workflow_id: str, node_id: str, label: str, node_type: str, config_json: str) -> None:
        row = self._db.query_one(
            "SELECT COALESCE(MAX(node_order), 0) + 1 AS next_order FROM workflow_nodes WHERE workflow_id = ?",
            (workflow_id,),
        )
        next_order = int(row["next_order"]) if row else 1
        self._db.execute(
            "INSERT INTO workflow_nodes(id, workflow_id, node_order, node_type, label, config) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, workflow_id, next_order, node_type, label, config_json),
        )


class SopRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def create(self, sop_id: str, name: str, trigger: str) -> dict:
        self._db.execute(
            "INSERT INTO sops(id, name, trigger_rule, status) VALUES (?, ?, ?, ?)",
            (sop_id, name, trigger, "enabled"),
        )
        return {"id": sop_id, "name": name, "trigger": trigger, "status": "enabled"}

    def list_all(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM sops ORDER BY id")
        return [self._row_to_sop(r) for r in rows]

    @staticmethod
    def _row_to_sop(row: dict) -> dict:
        return {"id": row["id"], "name": row["name"], "trigger": row["trigger_rule"], "status": row["status"]}


class KnowledgeRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_by_bot(
        self,
        bot_id: str,
        kind: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        """获取指定机器人的知识条目，支持按 kind 与关键词（question/answer）筛选。"""
        sql = "SELECT * FROM knowledge_base WHERE bot_id = ?"
        params: list = [bot_id]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if search:
            sql += " AND (question LIKE ? OR answer LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])
        sql += " ORDER BY updated_at DESC"
        rows = self._db.query(sql, tuple(params))
        return [self._row_to_knowledge(row) for row in rows]

    def get(self, knowledge_id: str) -> Optional[dict]:
        """根据 ID 获取知识条目。"""
        row = self._db.query_one("SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,))
        return self._row_to_knowledge(row) if row else None

    def create(
        self,
        knowledge_id: str,
        bot_id: str,
        question: str,
        answer: str,
        tags: list[str],
        source: str,
        kind: str = "common",
        creator: str = "system",
    ) -> dict:
        """创建知识条目。"""
        tags_json = json.dumps(tags, ensure_ascii=False)
        self._db.execute(
            "INSERT INTO knowledge_base(id, bot_id, question, answer, tags, source, kind, creator) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (knowledge_id, bot_id, question, answer, tags_json, source, kind, creator),
        )
        return {
            "id": knowledge_id,
            "botId": bot_id,
            "question": question,
            "answer": answer,
            "tags": tags,
            "source": source,
            "kind": kind,
            "creator": creator,
        }

    def update(
        self,
        knowledge_id: str,
        question: str,
        answer: str,
        tags: list[str],
        source: str,
        kind: Optional[str] = None,
        creator: Optional[str] = None,
    ) -> None:
        """更新知识条目（kind/creator 仅在传入时更新，向后兼容旧调用）。"""
        tags_json = json.dumps(tags, ensure_ascii=False)
        fields = ["question = ?", "answer = ?", "tags = ?", "source = ?"]
        params: list = [question, answer, tags_json, source]
        if kind is not None:
            fields.append("kind = ?")
            params.append(kind)
        if creator is not None:
            fields.append("creator = ?")
            params.append(creator)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(knowledge_id)
        self._db.execute(
            f"UPDATE knowledge_base SET {', '.join(fields)} WHERE id = ?",
            tuple(params),
        )

    def delete(self, knowledge_id: str) -> None:
        """删除知识条目。"""
        self._db.execute("DELETE FROM knowledge_base WHERE id = ?", (knowledge_id,))

    def delete_by_bot_and_kind(self, bot_id: str, kind: str) -> int:
        """按 bot_id + kind 作用域批量删除（侧栏「删除知识库」语义）。返回删除行数。"""
        return self._db.execute(
            "DELETE FROM knowledge_base WHERE bot_id = ? AND kind = ?",
            (bot_id, kind),
        )

    def delete_by_bot_and_ids(self, bot_id: str, ids: list[str]) -> int:
        """按 bot_id 作用域批量删除指定 id 列表，返回删除行数。"""
        if not ids:
            return 0
        placeholders = ", ".join("?" for _ in ids)
        return self._db.execute(
            f"DELETE FROM knowledge_base WHERE bot_id = ? AND id IN ({placeholders})",
            (bot_id, *ids),
        )

    def _row_to_knowledge(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "botId": row["bot_id"],
            "question": row["question"],
            "answer": row["answer"],
            "tags": json.loads(row["tags"]),
            "source": row["source"],
            "kind": row.get("kind", "common"),
            "creator": row.get("creator", "system"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }


class MaterialRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_paged(
        self,
        bot_id: str,
        name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页 + 筛选获取素材，返回 {items, total, page, pageSize, hasMore}。"""
        pagination = normalize_pagination(page, page_size)
        where = ["bot_id = ?"]
        params: list = [bot_id]
        if name:
            where.append("name LIKE ?")
            params.append(f"%{name}%")
        if source:
            where.append("source = ?")
            params.append(source)
        if start_date:
            where.append("date(created_at) >= ?")
            params.append(start_date)
        if end_date:
            where.append("date(created_at) <= ?")
            params.append(end_date)
        where_sql = " AND ".join(where)

        total_row = self._db.query_one(
            f"SELECT COUNT(*) AS c FROM materials WHERE {where_sql}",
            tuple(params),
        )
        total = int(total_row["c"]) if total_row else 0

        rows = self._db.query(
            f"SELECT * FROM materials WHERE {where_sql} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (pagination.limit, pagination.offset),
        )
        items = [self._row_to_material(row) for row in rows]
        return paginate_result(items, total, pagination)

    def get(self, material_id: str) -> Optional[dict]:
        """根据 ID 获取素材。"""
        row = self._db.query_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        return self._row_to_material(row) if row else None

    def create(
        self,
        material_id: str,
        bot_id: str,
        name: str,
        type_: str,
        size: int,
        category: str,
        url: Optional[str],
        source: str = "上传",
    ) -> dict:
        """创建素材。"""
        self._db.execute(
            "INSERT INTO materials(id, bot_id, name, type, size, category, url, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (material_id, bot_id, name, type_, size, category, url, source),
        )
        return {
            "id": material_id,
            "botId": bot_id,
            "name": name,
            "type": type_,
            "size": size,
            "category": category,
            "url": url,
            "source": source,
            "usageCount": 0,
        }

    def delete(self, material_id: str) -> None:
        """删除素材。"""
        self._db.execute("DELETE FROM materials WHERE id = ?", (material_id,))

    def delete_by_bot_and_ids(self, bot_id: str, ids: list[str]) -> int:
        """按 bot_id 作用域批量删除指定 id 列表，返回删除行数。"""
        if not ids:
            return 0
        placeholders = ", ".join("?" for _ in ids)
        return self._db.execute(
            f"DELETE FROM materials WHERE bot_id = ? AND id IN ({placeholders})",
            (bot_id, *ids),
        )

    def increment_usage(self, material_id: str) -> None:
        """增加素材引用次数。"""
        self._db.execute("UPDATE materials SET usage_count = usage_count + 1 WHERE id = ?", (material_id,))

    def _row_to_material(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "botId": row["bot_id"],
            "name": row["name"],
            "type": row["type"],
            "size": row["size"],
            "category": row["category"],
            "url": row["url"],
            "source": row.get("source", "上传"),
            "usageCount": row["usage_count"],
            "uploadedAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }


class WorkflowRunRepository:
    """工作流执行记录仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self.backend = backend

    def list_by_conversation(self, conversation_id: str) -> list[dict]:
        rows = self.backend.query(
            "SELECT id, conversation_id, workflow_id, status, trigger, config, started_at, finished_at "
            "FROM workflow_runs WHERE conversation_id = ? ORDER BY started_at DESC",
            (conversation_id,),
        )
        return [self.row_to_run(row) for row in rows]

    def create(
        self,
        conversation_id: str,
        workflow_id: str,
        status: str = "running",
        trigger: str = "manual",
        config: dict | None = None,
    ) -> dict:
        run_id = _generate_id("run")
        config_json = json.dumps(config or {}, ensure_ascii=False)
        self.backend.execute(
            "INSERT INTO workflow_runs(id, conversation_id, workflow_id, status, trigger, config, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, NULL)",
            (run_id, conversation_id, workflow_id, status, trigger, config_json),
        )
        return {
            "id": run_id,
            "conversationId": conversation_id,
            "workflowId": workflow_id,
            "status": status,
            "trigger": trigger,
            "config": config or {},
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "finishedAt": None,
        }

    def update_status(self, run_id: str, status: str) -> None:
        self.backend.execute(
            "UPDATE workflow_runs SET status = ?, finished_at = CASE WHEN ? IN ('finished', 'interrupted') THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id = ?",
            (status, status, run_id),
        )

    def row_to_run(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "conversationId": row["conversation_id"],
            "workflowId": row["workflow_id"],
            "status": row["status"],
            "trigger": row["trigger"],
            "config": json.loads(row["config"] or "{}"),
            "startedAt": row["started_at"],
            "finishedAt": row["finished_at"],
        }


class ConversationRepository:
    """会话、消息、机器人订阅与渠道坐席仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self.backend = backend

    def upsert_for_session(self, session: dict) -> None:
        """从 dashboard 会话数据同步/更新会话行（兼容已有静态数据）。

        session 字段约定（驼峰来自前端 contract）：
        id / name / channel / bot / state / intent / last / time
        """
        conv_id = session["id"]
        existing = self.backend.query(
            "SELECT id FROM conversations WHERE id = ?", (conv_id,)
        )
        if existing:
            self.backend.execute(
                "UPDATE conversations SET name = ?, channel = ?, bot_id = ?, state = ?, intent = ?, last_message = ?, last_time = ? "
                "WHERE id = ?",
                (
                    session.get("name", ""),
                    session.get("channel", ""),
                    session.get("bot", ""),
                    session.get("state", ""),
                    session.get("intent", ""),
                    session.get("last", ""),
                    session.get("time", ""),
                    conv_id,
                ),
            )
        else:
            self.backend.execute(
                "INSERT INTO conversations(id, name, channel, bot_id, state, intent, last_message, last_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    conv_id,
                    session.get("name", ""),
                    session.get("channel", ""),
                    session.get("bot", ""),
                    session.get("state", ""),
                    session.get("intent", ""),
                    session.get("last", ""),
                    session.get("time", ""),
                ),
            )

    def list_by_bot(self, bot_id: str) -> list[dict]:
        rows = self.backend.query(
            "SELECT id, name, channel, bot_id, state, intent, last_message, last_time, created_at "
            "FROM conversations WHERE bot_id = ? ORDER BY created_at DESC",
            (bot_id,),
        )
        return [self.row_to_conversation(row) for row in rows]

    def list_all(self) -> list[dict]:
        rows = self.backend.query(
            "SELECT id, name, channel, bot_id, state, intent, last_message, last_time, created_at "
            "FROM conversations ORDER BY created_at DESC"
        )
        return [self.row_to_conversation(row) for row in rows]

    def list_paged(self, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        total = self.backend.query("SELECT COUNT(*) AS c FROM conversations")[0]["c"]
        offset = max(page - 1, 0) * page_size
        rows = self.backend.query(
            "SELECT id, name, channel, bot_id, state, intent, last_message, last_time, created_at "
            "FROM conversations ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )
        return [self.row_to_conversation(row) for row in rows], total

    def get_messages(self, conversation_id: str, page: int = 1, page_size: int = 50) -> dict:
        total = self.backend.query(
            "SELECT COUNT(*) AS c FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )[0]["c"]
        offset = max(page - 1, 0) * page_size
        rows = self.backend.query(
            "SELECT id, conversation_id, sender_type, content, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (conversation_id, page_size, offset),
        )
        items = [self.row_to_message(row) for row in rows]
        return {
            "conversationId": conversation_id,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "items": items,
            "hasMore": offset + len(items) < total,
        }

    def row_to_conversation(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "channel": row["channel"],
            "bot": row["bot_id"],
            "state": row["state"],
            "intent": row["intent"],
            "last": row["last_message"],
            "time": row["last_time"],
        }

    def row_to_message(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "conversationId": row["conversation_id"],
            "senderType": row["sender_type"],
            "content": row["content"],
            "createdAt": row["created_at"],
        }


class BotSubscriptionRepository:
    """机器人托管订阅仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self.backend = backend

    def get(self, bot_id: str) -> Optional[dict]:
        rows = self.backend.query(
            "SELECT bot_id, hosted_sessions, expire_at FROM bot_subscriptions WHERE bot_id = ?",
            (bot_id,),
        )
        if not rows:
            return None
        return self.row_to_subscription(rows[0])

    def list_all(self) -> list[dict]:
        rows = self.backend.query(
            "SELECT bot_id, hosted_sessions, expire_at FROM bot_subscriptions ORDER BY expire_at ASC"
        )
        return [self.row_to_subscription(row) for row in rows]

    def row_to_subscription(self, row: dict) -> dict:
        return {
            "botId": row["bot_id"],
            "hostedSessions": row["hosted_sessions"],
            "expireAt": row["expire_at"],
        }


class ChannelSeatRepository:
    """渠道坐席（席位）仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self.backend = backend

    def get(self, channel_account_id: str) -> Optional[dict]:
        rows = self.backend.query(
            "SELECT channel_account_id, seats_left, online_sessions FROM channel_seats WHERE channel_account_id = ?",
            (channel_account_id,),
        )
        if not rows:
            return None
        return self.row_to_seat(rows[0])

    def list_all(self) -> list[dict]:
        rows = self.backend.query(
            "SELECT channel_account_id, seats_left, online_sessions FROM channel_seats ORDER BY seats_left ASC"
        )
        return [self.row_to_seat(row) for row in rows]

    def row_to_seat(self, row: dict) -> dict:
        return {
            "channelAccountId": row["channel_account_id"],
            "seatsLeft": row["seats_left"],
            "onlineSessions": row["online_sessions"],
        }


class OrchestrationWorkflowRepository:
    """编排工作流持久化仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def save(self, bot_id: str, data_json: str) -> None:
        """保存或更新编排工作流（INSERT OR REPLACE）。"""
        self._db.execute(
            "INSERT OR REPLACE INTO orchestration_workflows(bot_id, data, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (bot_id, data_json),
        )

    def load(self, bot_id: str) -> Optional[dict]:
        """加载指定 bot 的编排工作流，不存在返回 None。"""
        return self._db.query_one(
            "SELECT bot_id, data, updated_at FROM orchestration_workflows WHERE bot_id = ?",
            (bot_id,),
        )

    def delete(self, bot_id: str) -> bool:
        """删除指定 bot 的编排工作流，返回是否实际删除了行。"""
        rowcount = self._db.execute(
            "DELETE FROM orchestration_workflows WHERE bot_id = ?",
            (bot_id,),
        )
        return rowcount > 0


class TrainingRepository:
    """训练对话（训练记录 + 训练消息）仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_records(self, bot_id: str) -> list[dict]:
        """列出某 bot 的全部训练记录（按 created_at DESC）。"""
        rows = self._db.query(
            "SELECT * FROM training_records WHERE bot_id = ? ORDER BY created_at DESC",
            (bot_id,),
        )
        return [self._row_to_record(row) for row in rows]

    def get_record(self, record_id: str) -> Optional[dict]:
        """根据 ID 获取训练记录。"""
        row = self._db.query_one("SELECT * FROM training_records WHERE id = ?", (record_id,))
        return self._row_to_record(row) if row else None

    def create_record(self, record_id: str, bot_id: str, title: str) -> dict:
        """创建训练记录。"""
        self._db.execute(
            "INSERT INTO training_records(id, bot_id, title) VALUES (?, ?, ?)",
            (record_id, bot_id, title),
        )
        return self._row_to_record(
            self._db.query_one("SELECT * FROM training_records WHERE id = ?", (record_id,))
        )

    def delete_record(self, record_id: str) -> None:
        """级联删除训练记录及其全部消息。"""
        self._db.execute("DELETE FROM training_messages WHERE record_id = ?", (record_id,))
        self._db.execute("DELETE FROM training_records WHERE id = ?", (record_id,))

    def list_messages(self, record_id: str) -> list[dict]:
        """列出某记录的全部消息（按 msg_order ASC）。"""
        rows = self._db.query(
            "SELECT * FROM training_messages WHERE record_id = ? ORDER BY msg_order ASC",
            (record_id,),
        )
        return [self._row_to_message(row) for row in rows]

    def create_message(
        self,
        message_id: str,
        record_id: str,
        bot_id: str,
        role: str,
        content: str,
        record_ref: str = "",
        msg_order: int = 0,
    ) -> dict:
        """写入一条训练消息；msg_order 为 0 时自动取当前最大 + 1。"""
        if msg_order <= 0:
            order_row = self._db.query_one(
                "SELECT COALESCE(MAX(msg_order), 0) + 1 AS next_order FROM training_messages WHERE record_id = ?",
                (record_id,),
            )
            msg_order = int(order_row["next_order"]) if order_row else 1
        self._db.execute(
            "INSERT INTO training_messages(id, record_id, bot_id, role, content, record_ref, msg_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, record_id, bot_id, role, content, record_ref, msg_order),
        )
        # 消息新增后同步重算并持久化该记录的 good/bad/total，
        # 保证刷新/切换 bot 后 GET records 读到的是最新统计（非陈旧值）。
        self._recompute_record_counts(record_id)
        return self._row_to_message(
            self._db.query_one("SELECT * FROM training_messages WHERE id = ?", (message_id,))
        )

    def update_feedback(self, message_id: str, feedback: Optional[str]) -> dict:
        """更新某消息 feedback 并服务端重算该记录的 good/bad/total（仅统计 role='ai'）。"""
        self._db.execute(
            "UPDATE training_messages SET feedback = ? WHERE id = ?",
            (feedback, message_id),
        )
        link = self._db.query_one(
            "SELECT record_id FROM training_messages WHERE id = ?", (message_id,)
        )
        if not link:
            return {}
        return self._recompute_record_counts(link["record_id"])

    def _recompute_record_counts(self, record_id: str) -> dict:
        """服务端重算并持久化某训练记录的 good/bad/total 统计（仅统计 role='ai'）。

        在消息新增（create_message）或 feedback 变更（update_feedback）后调用，
        保证 GET records 读到的是最新统计，刷新/切换 bot 后不会显示陈旧值。
        feedback='like' 计入 good_count，feedback='dislike' 计入 bad_count，
        total_count 恒等于该记录下 role='ai' 消息的总数。
        """
        good = self._count_ai(record_id, "like")
        bad = self._count_ai(record_id, "dislike")
        total = self._count_ai(record_id, None)
        self._db.execute(
            "UPDATE training_records SET good_count = ?, bad_count = ?, total_count = ? WHERE id = ?",
            (good, bad, total, record_id),
        )
        return self._row_to_record(
            self._db.query_one("SELECT * FROM training_records WHERE id = ?", (record_id,))
        )

    def _count_ai(self, record_id: str, feedback: Optional[str]) -> int:
        """统计该记录下 role='ai' 且 feedback 匹配的消息数（feedback=None 表示统计全部 ai）。"""
        if feedback is None:
            sql = "SELECT COUNT(*) AS c FROM training_messages WHERE record_id = ? AND role = 'ai'"
            params: tuple = (record_id,)
        else:
            sql = "SELECT COUNT(*) AS c FROM training_messages WHERE record_id = ? AND role = 'ai' AND feedback = ?"
            params = (record_id, feedback)
        row = self._db.query_one(sql, params)
        return int(row["c"]) if row else 0

    @staticmethod
    def _row_to_record(row: dict) -> dict:
        return {
            "id": row["id"],
            "botId": row["bot_id"],
            "title": row["title"],
            "createdAt": row["created_at"],
            "goodCount": row["good_count"],
            "badCount": row["bad_count"],
            "totalCount": row["total_count"],
        }

    @staticmethod
    def _row_to_message(row: dict) -> dict:
        return {
            "id": row["id"],
            "recordId": row["record_id"],
            "botId": row["bot_id"],
            "role": row["role"],
            "content": row["content"],
            "recordRef": row["record_ref"],
            "feedback": row["feedback"],
            "msgOrder": row["msg_order"],
            "createdAt": row["created_at"],
        }


# ---- 托管消息日志（message_logs + message_log_traces） ----

# 节点类型 -> 图标（与前端 lucide 映射一致：user/chat/robot/search/send）
NODE_ICON: dict[str, str] = {
    "userInput": "user",
    "kbSearch": "search",
    "aiChat": "robot",
    "msgOutput": "send",
    "chatHistory": "chat",
}


def _parse_json_field(value: Optional[str], default: object = None) -> object:
    """解析 JSON 文本；为空或解析失败时兜底返回原值或 default。"""
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


class MessageLogRepository:
    """托管消息日志仓储：列表分页 + 详情（含编排节点追踪）。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_logs(
        self,
        bot_id: str,
        ai_reply_id: Optional[str] = None,
        question: Optional[str] = None,
        session: Optional[str] = None,
        status: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页 + 筛选获取托管消息日志，返回 {items, total, page, pageSize, hasMore}。"""
        pagination = normalize_pagination(page, page_size)
        where = ["bot_id = ?"]
        params: list = [bot_id]
        if ai_reply_id:
            where.append("id LIKE ?")
            params.append(f"%{ai_reply_id}%")
        if question:
            where.append("question LIKE ?")
            params.append(f"%{question}%")
        if session:
            where.append("session = ?")
            params.append(session)
        if status:
            where.append("status = ?")
            params.append(status)
        if start:
            where.append("date(reply_time) >= ?")
            params.append(start)
        if end:
            where.append("date(reply_time) <= ?")
            params.append(end)
        where_sql = " AND ".join(where)

        total_row = self._db.query_one(
            f"SELECT COUNT(*) AS c FROM message_logs WHERE {where_sql}",
            tuple(params),
        )
        total = int(total_row["c"]) if total_row else 0

        rows = self._db.query(
            f"SELECT * FROM message_logs WHERE {where_sql} ORDER BY reply_time DESC LIMIT ? OFFSET ?",
            tuple(params) + (pagination.limit, pagination.offset),
        )
        items = [self._row_to_log(row) for row in rows]
        return paginate_result(items, total, pagination)

    def get_log_with_nodes(self, bot_id: str, ai_reply_id: str) -> Optional[dict]:
        """获取单条日志及其按 node_order 升序的编排节点追踪。未找到返回 None。"""
        row = self._db.query_one(
            "SELECT * FROM message_logs WHERE id = ? AND bot_id = ?",
            (ai_reply_id, bot_id),
        )
        if row is None:
            return None
        trace_rows = self._db.query(
            "SELECT * FROM message_log_traces WHERE log_id = ? ORDER BY node_order ASC",
            (ai_reply_id,),
        )
        log = self._row_to_log(row)
        log["nodes"] = [self._row_to_node(t) for t in trace_rows]
        return log

    @staticmethod
    def _row_to_log(row: dict) -> dict:
        return {
            "id": row["id"],
            "content": _parse_json_field(row.get("content_json"), {}),
            "question": row.get("question", ""),
            "account": row.get("account", ""),
            "session": row.get("session", ""),
            "robot": BOT_NAMES.get(row.get("bot_id", ""), row.get("bot_id", "")),
            "channel": row.get("channel", ""),
            "time": row.get("reply_time", ""),
            "status": row.get("status", "成功"),
        }

    @staticmethod
    def _row_to_node(row: dict) -> dict:
        return {
            "name": row.get("node_name", ""),
            "icon": NODE_ICON.get(row.get("node_type", ""), "robot"),
            "runtime": row.get("runtime", ""),
            "input": _parse_json_field(row.get("input_json"), {}),
            "output": _parse_json_field(row.get("output_json"), {}),
            "code": row.get("code", ""),
        }


# ---- 渠道会话管理域：托管可选机器人（静态配置，非表） ----
HOSTING_BOTS: list[dict] = [
    {"id": "yefengqiu", "name": "野风秋大健康机器人"},
    {"id": "yangqicheng", "name": "杨奇成健康机器人"},
    {"id": "zhulu", "name": "竹绿健康助手"},
]


# ---- 行 -> DTO 映射（snake_case -> camelCase） ----
def row_to_account(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["account_name"],
        "channel": row["channel"],
        "channelType": row["channel_type"],
        "protocol": row["protocol"],
        "status": row["status"],
        "online": (row["status"] == "online"),
        "sessionsCount": row["sessions_count"],
        "teamId": row.get("team_id", ""),
        "boundBot": row["bound_bot"],
        "seatsLeft": row.get("seats_left"),
        "onlineSessions": row.get("online_sessions"),
        "teamName": row.get("team_name"),
    }


def row_to_contact(row: dict) -> dict:
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "channel": row["channel"],
        "channelType": row["channel_type"],
        "name": row["name"],
        "nickname": row["nickname"],
        "type": row["type"],
        "status": row["status"],
        "remark": row["remark"],
        "description": row["description"],
        "addTime": row["add_time"],
        "source": row["source"],
    }


def row_to_session(row: dict) -> dict:
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "contactId": row.get("contact_id"),
        "name": row["name"],
        "channel": row["channel"],
        "channelType": row["channel_type"],
        "lastMessage": row["last_message"],
        "lastTime": row["last_time"],
        "unreadCount": row["unread_count"],
        "readStatus": row["read_status"],
        "hostedStatus": row["hosted_status"],
        "hostedBotId": row.get("hosted_bot_id"),
        "owner": row["owner"],
        "onlineStatus": row["online_status"],
        "sessionType": row["session_type"],
        "externalTag": row["external_tag"],
        "addTime": row["add_time"],
        "hostingChain": row["hosting_chain"],
    }


def row_to_customer_profile(row: dict) -> dict:
    return {
        "id": row["id"],
        "contactId": row["contact_id"],
        "phone": row["phone"],
        "email": row["email"],
        "company": row["company"],
        "position": row["position"],
        "region": row["region"],
        "age": row.get("age"),
        "birthday": row["birthday"],
        "remark": row["remark"],
        "addTime": row["add_time"],
        "addChannel": row["add_channel"],
        "signature": row["signature"],
        "aiSummaryEnabled": bool(row.get("ai_summary_enabled", 0)),
    }


def row_to_communication(row: dict) -> dict:
    return {
        "id": row["id"],
        "customerId": row["customer_id"],
        "content": row["content"],
        "aiSummary": row["ai_summary"],
        "type": row["type"],
        "createdAt": row["created_at"],
    }


def row_to_custom_attribute(row: dict) -> dict:
    return {
        "id": row["id"],
        "customerId": row["customer_id"],
        "name": row["name"],
        "value": row["value"],
    }


def row_to_hosting_session(row: dict) -> dict:
    return {
        "id": row["id"],
        "sessionKey": row["session_key"],
        "accountId": row["account_id"],
        "customerName": row["customer_name"],
        "customerRemark": row["customer_remark"],
        "addTime": row["add_time"],
        "hostedStatus": row["hosted_status"],
        "hostingChain": row["hosting_chain"],
    }


def row_to_hosting_rule(row: dict) -> dict:
    return {
        "id": row["id"],
        "accountId": row.get("account_id"),
        "autoResumeSeconds": row.get("auto_resume_seconds"),
        "autoCancelEnabled": bool(row.get("auto_cancel_enabled", 0)),
    }


def row_to_wechat_subject(row: dict) -> dict:
    return {
        "id": row["id"],
        "fullName": row["full_name"],
        "shortName": row["short_name"],
        "corpId": row["corp_id"],
        "configJson": row["config_json"],
    }


class ChannelMgmtRepository:
    """渠道会话管理域仓储（accounts/contacts/sessions/hosting/wechat-subjects/teams）。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    # ---- teams ----
    def list_teams(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM teams ORDER BY created_at, id")
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "seatsLeft": r["seats_left"],
                "energyValue": r["energy_value"],
            }
            for r in rows
        ]

    def create_team(self, name: str, seats_left: int = 0, energy_value: int = 0) -> dict:
        team_id = _generate_id("team")
        self._db.execute(
            "INSERT INTO teams(id, name, seats_left, energy_value) VALUES (?, ?, ?, ?)",
            (team_id, name, seats_left, energy_value),
        )
        return {"id": team_id, "name": name, "seatsLeft": seats_left, "energyValue": energy_value}

    # ---- accounts（扩展 DTO，JOIN channel_seats + teams） ----
    def list_accounts_enriched(self) -> list[dict]:
        sql = (
            "SELECT a.*, s.seats_left, s.online_sessions, t.name AS team_name "
            "FROM channel_accounts a "
            "LEFT JOIN channel_seats s ON s.channel_account_id = a.id "
            "LEFT JOIN teams t ON t.id = a.team_id "
            "ORDER BY a.created_at, a.id"
        )
        rows = self._db.query(sql)
        return [row_to_account(r) for r in rows]

    def create_account(self, channel_type: str, protocol: str = "", team_id: str = "", name: str | None = None) -> dict:
        account_id = _generate_id("acc")
        channel_label = {
            "wecom": "企业微信",
            "wechat": "微信",
            "whatsapp": "WhatsApp",
            "business_whatsapp": "企业WhatsApp",
        }.get(channel_type, "渠道账号")
        account_name = name or f"{channel_label}-新账号"
        self._db.execute(
            "INSERT INTO channel_accounts(id, channel, account_name, status, bound_bot, daily_quota, team_id, channel_type, protocol, sessions_count) "
            "VALUES (?, ?, ?, 'online', ?, 0, ?, ?, ?, 0)",
            (account_id, channel_label, account_name, "yefengqiu", team_id, channel_type, protocol),
        )
        row = self._db.query_one(
            "SELECT a.*, s.seats_left, s.online_sessions, t.name AS team_name "
            "FROM channel_accounts a "
            "LEFT JOIN channel_seats s ON s.channel_account_id = a.id "
            "LEFT JOIN teams t ON t.id = a.team_id "
            "WHERE a.id = ?",
            (account_id,),
        )
        if row is None:
            return {"id": account_id, "name": account_name, "channel": channel_label,
                    "channelType": channel_type, "protocol": protocol, "status": "online",
                    "online": True, "sessionsCount": 0, "teamId": team_id, "boundBot": "yefengqiu"}
        return row_to_account(row)

    # ---- contacts ----
    def list_contacts(
        self,
        account_id: str | None = None,
        type_: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM channel_contacts WHERE 1=1"
        params: list = []
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        if type_:
            sql += " AND type = ?"
            params.append(type_)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if search:
            sql += " AND (name LIKE ? OR remark LIKE ? OR nickname LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        sql += " ORDER BY add_time, id"
        rows = self._db.query(sql, tuple(params))
        return [row_to_contact(r) for r in rows]

    def get_contact_detail(self, contact_id: str) -> dict | None:
        contact = self._db.query_one("SELECT * FROM channel_contacts WHERE id = ?", (contact_id,))
        if contact is None:
            return None
        profile = self._db.query_one("SELECT * FROM customer_profiles WHERE contact_id = ?", (contact_id,))
        communications = self._db.query(
            "SELECT * FROM communication_records WHERE customer_id = ? ORDER BY created_at DESC",
            (profile["id"],) if profile else (contact_id,),
        )
        # communication_records.customer_id 关联 customer_profiles.id；
        # 若 profile 不存在则按 contact_id 兜底查询（保持健壮）。
        if not communications and profile is None:
            communications = []
        attributes = self._db.query(
            "SELECT * FROM custom_attributes WHERE customer_id = ? ORDER BY created_at",
            (profile["id"],) if profile else (contact_id,),
        )
        return {
            "contact": row_to_contact(contact),
            "profile": row_to_customer_profile(profile) if profile else None,
            "communications": [row_to_communication(c) for c in communications],
            "attributes": [row_to_custom_attribute(a) for a in attributes],
        }

    # ---- sessions ----
    def list_sessions(
        self,
        account_id: str | None = None,
        read: str | None = None,
        hosted: str | None = None,
        online: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM channel_sessions WHERE 1=1"
        params: list = []
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        if read in ("read", "unread"):
            sql += " AND read_status = ?"
            params.append(read)
        if hosted in ("hosted", "unhosted"):
            sql += " AND hosted_status = ?"
            params.append(hosted)
        if online in ("online", "offline"):
            sql += " AND online_status = ?"
            params.append(online)
        if search:
            sql += " AND name LIKE ?"
            params.append(f"%{search}%")
        sql += " ORDER BY last_time DESC, id"
        rows = self._db.query(sql, tuple(params))
        return [row_to_session(r) for r in rows]

    def list_session_messages(self, session_id: str) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id",
            (session_id,),
        )
        return [
            {
                "id": r["id"],
                "conversationId": r["conversation_id"],
                "senderType": r["sender_type"],
                "content": r["content"],
                "createdAt": r["created_at"],
            }
            for r in rows
        ]

    def set_session_hosting(self, session_id: str, hosted: bool, bot_id: str | None) -> dict | None:
        hosted_status = "hosted" if hosted else "unhosted"
        self._db.execute(
            "UPDATE channel_sessions SET hosted_status = ?, hosted_bot_id = ? WHERE id = ?",
            (hosted_status, bot_id, session_id),
        )
        row = self._db.query_one("SELECT * FROM channel_sessions WHERE id = ?", (session_id,))
        return row_to_session(row) if row else None

    # ---- hosting sessions ----
    def list_hosting_sessions(
        self,
        account_id: str | None = None,
        bot_id: str | None = None,
        session_type: str | None = None,
        nickname: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        # 注：hosting_sessions 表无 bot_id / session_type 列，botId / sessionType
        # 过滤在 P0 阶段暂按无数据口径忽略（托管链维度后续可在 hosting_chain 上扩展）。
        sql = "SELECT * FROM hosting_sessions WHERE 1=1"
        params: list = []
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        if nickname:
            sql += " AND customer_name LIKE ?"
            params.append(f"%{nickname}%")
        if start:
            sql += " AND date(add_time) >= ?"
            params.append(start)
        if end:
            sql += " AND date(add_time) <= ?"
            params.append(end)
        sql += " ORDER BY add_time, id"
        rows = self._db.query(sql, tuple(params))
        return [row_to_hosting_session(r) for r in rows]

    def batch_update_hosting(
        self,
        ids: list[str],
        hosted_status: str | None = None,
        hosting_chain: str | None = None,
    ) -> int:
        if not ids:
            return 0
        placeholders = ", ".join("?" for _ in ids)
        assignments: list[str] = []
        params: list = []
        if hosted_status in ("hosted", "unhosted"):
            assignments.append("hosted_status = ?")
            params.append(hosted_status)
        if hosting_chain is not None:
            assignments.append("hosting_chain = ?")
            params.append(hosting_chain)
        if not assignments:
            return 0
        params.extend(ids)
        sql = f"UPDATE hosting_sessions SET {', '.join(assignments)} WHERE id IN ({placeholders})"
        return self._db.execute(sql, tuple(params))

    # ---- hosting rules ----
    def get_hosting_rules(self, account_id: str | None = None) -> dict:
        row = None
        if account_id:
            row = self._db.query_one("SELECT * FROM hosting_rules WHERE account_id = ?", (account_id,))
        if row is None:
            row = self._db.query_one("SELECT * FROM hosting_rules WHERE account_id IS NULL")
        if row is None:
            return {"id": None, "accountId": account_id, "autoResumeSeconds": None, "autoCancelEnabled": False}
        return row_to_hosting_rule(row)

    def upsert_hosting_rules(
        self,
        account_id: str | None,
        auto_resume_seconds: int | None = None,
        auto_cancel_enabled: bool = False,
    ) -> dict:
        existing = self._db.query_one("SELECT * FROM hosting_rules WHERE account_id IS ?", (account_id,))
        auto_cancel = 1 if auto_cancel_enabled else 0
        if existing:
            assignments = ["auto_cancel_enabled = ?"]
            params: list = [auto_cancel]
            if auto_resume_seconds is not None:
                assignments.append("auto_resume_seconds = ?")
                params.append(auto_resume_seconds)
            params.append(account_id)
            self._db.execute(
                f"UPDATE hosting_rules SET {', '.join(assignments)} WHERE account_id IS ?",
                tuple(params),
            )
            rule_id = existing["id"]
        else:
            rule_id = _generate_id("hr")
            self._db.execute(
                "INSERT INTO hosting_rules(id, account_id, auto_resume_seconds, auto_cancel_enabled) VALUES (?, ?, ?, ?)",
                (rule_id, account_id, auto_resume_seconds, auto_cancel),
            )
        row = self._db.query_one("SELECT * FROM hosting_rules WHERE id = ?", (rule_id,))
        return row_to_hosting_rule(row) if row else {
            "id": rule_id, "accountId": account_id,
            "autoResumeSeconds": auto_resume_seconds, "autoCancelEnabled": auto_cancel_enabled,
        }

    # ---- wechat subjects ----
    def list_wechat_subjects(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM wechat_subjects ORDER BY id")
        return [row_to_wechat_subject(r) for r in rows]

    def create_wechat_subject(self, full_name: str, short_name: str, corp_id: str, config_json: str = "{}") -> dict:
        subject_id = _generate_id("wx-subj")
        self._db.execute(
            "INSERT INTO wechat_subjects(id, full_name, short_name, corp_id, config_json) VALUES (?, ?, ?, ?, ?)",
            (subject_id, full_name, short_name, corp_id, config_json),
        )
        row = self._db.query_one("SELECT * FROM wechat_subjects WHERE id = ?", (subject_id,))
        return row_to_wechat_subject(row) if row else {
            "id": subject_id, "fullName": full_name, "shortName": short_name,
            "corpId": corp_id, "configJson": config_json,
        }

    def get_wechat_subject(self, subject_id: str) -> dict | None:
        row = self._db.query_one("SELECT * FROM wechat_subjects WHERE id = ?", (subject_id,))
        return row_to_wechat_subject(row) if row else None

    def update_wechat_subject(
        self, subject_id: str, full_name: str, short_name: str, corp_id: str, config_json: str = "{}"
    ) -> dict | None:
        self._db.execute(
            "UPDATE wechat_subjects SET full_name = ?, short_name = ?, corp_id = ?, config_json = ? WHERE id = ?",
            (full_name, short_name, corp_id, config_json, subject_id),
        )
        row = self._db.query_one("SELECT * FROM wechat_subjects WHERE id = ?", (subject_id,))
        return row_to_wechat_subject(row) if row else None

    # ---- hosting bots（静态） ----
    def list_hosting_bots(self) -> list[dict]:
        return [dict(b) for b in HOSTING_BOTS]


# ---- 客户管理域 Repository ----
class CustomerRepository:
    """客户管理域仓储（客户列表聚合 / 档案更新 / 沟通记录 / 自定义属性 / 标签关系 / 分组 / 标签分组）。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    # ============ 客户列表聚合 ============

    def list_customers(
        self,
        type_: str | None = None,
        account_id: str | None = None,
        channel: str | None = None,
        channel_type: str | None = None,
        keyword: str | None = None,
        tag_ids: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        """聚合客户列表（JOIN contacts + profile + 最新沟通 + 标签批量聚合）。"""
        pagination = normalize_pagination(page, page_size)

        where = ["1=1"]
        params: list = []

        if type_:
            if type_ == "external":
                where.append("cc.type = 'customer'")
            elif type_ == "internal":
                where.append("cc.type = 'internal'")
            else:
                where.append("cc.type = ?")
                params.append(type_)
        if account_id:
            where.append("cc.account_id = ?")
            params.append(account_id)
        if channel:
            where.append("cc.channel LIKE ?")
            params.append(f"%{channel}%")
        if channel_type:
            where.append("cc.channel_type = ?")
            params.append(channel_type)
        if keyword:
            where.append("(cc.name LIKE ? OR cc.nickname LIKE ? OR cc.remark LIKE ? OR cp.remark LIKE ? OR cp.phone LIKE ? OR cp.company LIKE ?)")
            like = f"%{keyword}%"
            params.extend([like, like, like, like, like, like])
        if date_from:
            where.append("cc.add_time >= ?")
            params.append(date_from)
        if date_to:
            where.append("cc.add_time <= ?")
            params.append(date_to)

        where_sql = " AND ".join(where)

        # 标签筛选：先找出匹配的 customer_profile ids
        if tag_ids:
            placeholders = ", ".join("?" for _ in tag_ids)
            tag_rows = self._db.query(
                f"SELECT DISTINCT ctr.customer_id FROM customer_tag_relations ctr WHERE ctr.tag_id IN ({placeholders})",
                tuple(tag_ids),
            )
            matched_ids = [r["customer_id"] for r in tag_rows]
            if matched_ids:
                id_placeholders = ", ".join("?" for _ in matched_ids)
                where_sql += f" AND cp.id IN ({id_placeholders})"
                params.extend(matched_ids)
            else:
                return paginate_result([], 0, pagination)

        # 聚合主查询
        sql = f"""
        SELECT cp.id, cp.contact_id, cp.phone, cp.email, cp.company, cp.position,
               cp.region, cp.age, cp.birthday, cp.remark AS profile_remark,
               cp.add_time AS profile_add_time, cp.add_channel, cp.signature,
               cp.ai_summary_enabled,
               cc.id AS contact_id_val, cc.account_id, cc.channel, cc.channel_type,
               cc.name, cc.nickname, cc.type, cc.status, cc.remark AS contact_remark,
               cc.description, cc.add_time AS contact_add_time, cc.source,
               lc.created_at AS last_comm_time, lc.content AS last_comm_content,
               lc.ai_summary AS last_comm_ai_summary
        FROM customer_profiles cp
        JOIN channel_contacts cc ON cc.id = cp.contact_id
        LEFT JOIN (
            SELECT customer_id, created_at, content, ai_summary,
                   ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) AS rn
            FROM communication_records
        ) lc ON lc.customer_id = cp.id AND lc.rn = 1
        WHERE {where_sql}
        ORDER BY cc.add_time DESC, cp.id
        LIMIT ? OFFSET ?
        """
        all_params = tuple(params) + (pagination.limit, pagination.offset)
        rows = self._db.query(sql, all_params)

        # Total count
        count_sql = f"""
        SELECT COUNT(*) AS c
        FROM customer_profiles cp
        JOIN channel_contacts cc ON cc.id = cp.contact_id
        WHERE {where_sql}
        """
        total_row = self._db.query_one(count_sql, tuple(params))
        total = int(total_row["c"]) if total_row else 0

        # 批量聚合标签
        profile_ids = [r["id"] for r in rows]
        tag_map: dict[str, list[dict]] = {}
        if profile_ids:
            placeholders = ", ".join("?" for _ in profile_ids)
            tag_rows = self._db.query(
                f"""SELECT ctr.customer_id, ct.id AS tag_id, ct.name AS tag_name, ct.color,
                           ctg.id AS group_id, ctg.name AS group_name
                    FROM customer_tag_relations ctr
                    JOIN customer_tags ct ON ct.id = ctr.tag_id
                    JOIN customer_tag_groups ctg ON ctg.id = ct.group_id
                    WHERE ctr.customer_id IN ({placeholders})
                    ORDER BY ctg.name, ct.name""",
                tuple(profile_ids),
            )
            for tr in tag_rows:
                cid = tr["customer_id"]
                if cid not in tag_map:
                    tag_map[cid] = []
                tag_map[cid].append({
                    "id": tr["tag_id"],
                    "name": tr["tag_name"],
                    "color": tr["color"],
                    "groupId": tr["group_id"],
                    "groupName": tr["group_name"],
                })

        items = []
        for r in rows:
            cid = r["id"]
            items.append({
                "id": cid,
                "contactId": r["contact_id_val"],
                "name": r["name"],
                "nickname": r["nickname"],
                "accountId": r["account_id"],
                "account": r["account_id"],
                "channel": r["channel"],
                "channelType": r["channel_type"],
                "type": r["type"],
                "aiSummaryEnabled": bool(r.get("ai_summary_enabled", 0)),
                "lastCommunicationTime": r.get("last_comm_time") or r.get("contact_add_time") or "",
                "lastCommunicationContent": r.get("last_comm_content") or "",
                "lastCommunicationAiSummary": r.get("last_comm_ai_summary") or "",
                "addTime": r.get("contact_add_time") or r.get("profile_add_time") or "",
                "tags": tag_map.get(cid, []),
                "remark": r.get("profile_remark") or r.get("contact_remark") or "",
                "phone": r.get("phone") or "",
                "email": r.get("email") or "",
                "company": r.get("company") or "",
                "position": r.get("position") or "",
                "region": r.get("region") or "",
                "age": r.get("age"),
                "birthday": r.get("birthday") or "",
                "signature": r.get("signature") or "",
                "description": r.get("description") or "",
                "source": r.get("source") or "",
                "status": r.get("status") or "",
            })

        return paginate_result(items, total, pagination)

    # ============ 档案更新 ============

    def update_customer_profile(self, contact_id: str, fields: dict) -> dict | None:
        """更新 customer_profiles 指定字段（按 contact_id 定位）。"""
        profile = self._db.query_one("SELECT id FROM customer_profiles WHERE contact_id = ?", (contact_id,))
        if profile is None:
            return None

        allowed = {
            "phone", "email", "company", "position", "region",
            "age", "birthday", "remark", "ai_summary_enabled",
        }
        updates: list[str] = []
        params: list = []
        for key, val in fields.items():
            db_key = _camel_to_snake(key)
            if db_key in allowed:
                updates.append(f"{db_key} = ?")
                if db_key == "ai_summary_enabled":
                    params.append(1 if val else 0)
                else:
                    params.append(val if val is not None else "")
        if not updates:
            return None
        params.append(profile["id"])
        self._db.execute(
            f"UPDATE customer_profiles SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        row = self._db.query_one("SELECT * FROM customer_profiles WHERE id = ?", (profile["id"],))
        return row_to_customer_profile(row) if row else None

    # ============ 沟通记录 ============

    def create_communication(self, customer_id: str, content: str, type_: str = "note", ai_summary: str = "") -> dict:
        cr_id = _generate_id("cr")
        self._db.execute(
            "INSERT INTO communication_records(id, customer_id, content, ai_summary, type) VALUES (?, ?, ?, ?, ?)",
            (cr_id, customer_id, content, ai_summary, type_),
        )
        row = self._db.query_one("SELECT * FROM communication_records WHERE id = ?", (cr_id,))
        return row_to_communication(row) if row else {"id": cr_id}

    def list_communications(self, customer_id: str) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM communication_records WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        )
        return [row_to_communication(r) for r in rows]

    # ============ 自定义属性 ============

    def create_attribute(self, customer_id: str, name: str, value: str) -> dict:
        ca_id = _generate_id("ca")
        self._db.execute(
            "INSERT INTO custom_attributes(id, customer_id, name, value) VALUES (?, ?, ?, ?)",
            (ca_id, customer_id, name, value),
        )
        row = self._db.query_one("SELECT * FROM custom_attributes WHERE id = ?", (ca_id,))
        return row_to_custom_attribute(row) if row else {"id": ca_id}

    def list_attributes(self, customer_id: str) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM custom_attributes WHERE customer_id = ? ORDER BY created_at",
            (customer_id,),
        )
        return [row_to_custom_attribute(r) for r in rows]

    # ============ 标签关系 ============

    def get_customer_tags(self, customer_id: str) -> list[dict]:
        rows = self._db.query(
            """SELECT ct.id, ct.name, ct.color, ct.group_id, ctg.name AS group_name
               FROM customer_tag_relations ctr
               JOIN customer_tags ct ON ct.id = ctr.tag_id
               JOIN customer_tag_groups ctg ON ctg.id = ct.group_id
               WHERE ctr.customer_id = ?
               ORDER BY ctg.name, ct.name""",
            (customer_id,),
        )
        return [
            {"id": r["id"], "name": r["name"], "color": r["color"],
             "groupId": r["group_id"], "groupName": r["group_name"]}
            for r in rows
        ]

    def set_customer_tags(self, customer_id: str, tag_ids: list[str]) -> None:
        with self._db.transaction() as tx:
            tx.execute("DELETE FROM customer_tag_relations WHERE customer_id = ?", (customer_id,))
            for tid in tag_ids:
                tx.execute(
                    "INSERT OR IGNORE INTO customer_tag_relations(customer_id, tag_id) VALUES (?, ?)",
                    (customer_id, tid),
                )

    # ============ 标签分组 ============

    def list_tag_groups(self) -> list[dict]:
        groups = self._db.query("SELECT * FROM customer_tag_groups ORDER BY name")
        result = []
        for g in groups:
            tags = self._db.query(
                "SELECT * FROM customer_tags WHERE group_id = ? ORDER BY name",
                (g["id"],),
            )
            result.append({
                "id": g["id"],
                "name": g["name"],
                "isHot": bool(g["is_hot"]),
                "createdAt": g["created_at"],
                "tags": [{"id": t["id"], "name": t["name"], "color": t["color"], "rule": t["rule"]} for t in tags],
            })
        return result

    def create_tag_group(self, name: str, is_hot: bool, tags: list[dict]) -> dict:
        gid = _generate_id("tg")
        with self._db.transaction() as tx:
            tx.execute(
                "INSERT INTO customer_tag_groups(id, name, is_hot) VALUES (?, ?, ?)",
                (gid, name, 1 if is_hot else 0),
            )
            tag_list = []
            for t in tags:
                tid = _generate_id("tag")
                tx.execute(
                    "INSERT INTO customer_tags(id, group_id, name, color, rule) VALUES (?, ?, ?, ?, ?)",
                    (tid, gid, t.get("name", ""), t.get("color", "blue"), t.get("rule", "")),
                )
                tag_list.append({"id": tid, "name": t.get("name", ""), "color": t.get("color", "blue"), "rule": t.get("rule", "")})
        return {"id": gid, "name": name, "isHot": is_hot, "tags": tag_list}

    def update_tag_group(self, group_id: str, name: str | None = None, is_hot: bool | None = None, tags: list[dict] | None = None) -> dict | None:
        existing = self._db.query_one("SELECT * FROM customer_tag_groups WHERE id = ?", (group_id,))
        if existing is None:
            return None
        updates = []
        params: list = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if is_hot is not None:
            updates.append("is_hot = ?")
            params.append(1 if is_hot else 0)
        if updates:
            params.append(group_id)
            self._db.execute(f"UPDATE customer_tag_groups SET {', '.join(updates)} WHERE id = ?", tuple(params))
        if tags is not None:
            # 全量替换组内标签
            with self._db.transaction() as tx:
                tx.execute("DELETE FROM customer_tag_relations WHERE tag_id IN (SELECT id FROM customer_tags WHERE group_id = ?)", (group_id,))
                tx.execute("DELETE FROM customer_tags WHERE group_id = ?", (group_id,))
                for t in tags:
                    tid = _generate_id("tag")
                    tx.execute(
                        "INSERT INTO customer_tags(id, group_id, name, color, rule) VALUES (?, ?, ?, ?, ?)",
                        (tid, group_id, t.get("name", ""), t.get("color", "blue"), t.get("rule", "")),
                    )
        return self.list_tag_groups_single(group_id)

    def delete_tag_group(self, group_id: str) -> bool:
        existing = self._db.query_one("SELECT * FROM customer_tag_groups WHERE id = ?", (group_id,))
        if existing is None:
            return False
        with self._db.transaction() as tx:
            tx.execute("DELETE FROM customer_tag_relations WHERE tag_id IN (SELECT id FROM customer_tags WHERE group_id = ?)", (group_id,))
            tx.execute("DELETE FROM customer_tags WHERE group_id = ?", (group_id,))
            tx.execute("DELETE FROM customer_tag_groups WHERE id = ?", (group_id,))
        return True

    def list_tag_groups_single(self, group_id: str) -> dict | None:
        g = self._db.query_one("SELECT * FROM customer_tag_groups WHERE id = ?", (group_id,))
        if g is None:
            return None
        tags = self._db.query("SELECT * FROM customer_tags WHERE group_id = ? ORDER BY name", (group_id,))
        return {
            "id": g["id"], "name": g["name"], "isHot": bool(g["is_hot"]),
            "createdAt": g["created_at"],
            "tags": [{"id": t["id"], "name": t["name"], "color": t["color"], "rule": t["rule"]} for t in tags],
        }

    # ============ 客户分组 ============

    def list_customer_groups(self, name: str | None = None, type_: str | None = None) -> list[dict]:
        sql = "SELECT * FROM customer_groups WHERE 1=1"
        params: list = []
        if name:
            sql += " AND name LIKE ?"
            params.append(f"%{name}%")
        if type_:
            sql += " AND type = ?"
            params.append(type_)
        sql += " ORDER BY created_at DESC"
        rows = self._db.query(sql, tuple(params))
        return [
            {
                "id": r["id"], "name": r["name"], "type": r["type"],
                "count": r["count"], "createdAt": r["created_at"],
                "updatedAt": r["updated_at"], "editor": r["editor"],
            }
            for r in rows
        ]

    def create_customer_group(self, name: str, type_: str = "custom", customer_ids: list[str] | None = None) -> dict:
        gid = _generate_id("g")
        with self._db.transaction() as tx:
            cnt = len(customer_ids) if customer_ids else 0
            tx.execute(
                "INSERT INTO customer_groups(id, name, type, count, editor) VALUES (?, ?, ?, ?, ?)",
                (gid, name, type_, cnt, ""),
            )
            if customer_ids:
                for cid in customer_ids:
                    tx.execute(
                        "INSERT OR IGNORE INTO customer_group_members(group_id, customer_id) VALUES (?, ?)",
                        (gid, cid),
                    )
        return {"id": gid, "name": name, "type": type_, "count": cnt, "createdAt": "", "updatedAt": "", "editor": ""}

    def create_group_with_members(self, name: str, type_: str = "custom", member_ids: list[str] | None = None) -> dict:
        """创建客户分组并批量添加初始成员（事务）。"""
        member_ids = member_ids or []
        gid = _generate_id("g")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db.transaction() as tx:
            tx.execute(
                "INSERT INTO customer_groups(id, name, type, count, editor, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (gid, name, type_, len(member_ids), "", now, now),
            )
            for cid in member_ids:
                tx.execute(
                    "INSERT OR IGNORE INTO customer_group_members(group_id, customer_id) VALUES (?, ?)",
                    (gid, cid),
                )
        return {
            "id": gid, "name": name, "type": type_, "count": len(member_ids),
            "createdAt": now, "updatedAt": now, "editor": "",
        }

    def add_members_to_group(self, group_id: str, contact_ids: list[str]) -> dict | None:
        """批量添加成员到已有分组。"""
        group = self._db.query_one("SELECT * FROM customer_groups WHERE id = ?", (group_id,))
        if group is None:
            return None
        added = 0
        with self._db.transaction() as tx:
            for cid in contact_ids:
                rowcount = tx.execute(
                    "INSERT OR IGNORE INTO customer_group_members(group_id, customer_id) VALUES (?, ?)",
                    (group_id, cid),
                )
                added += rowcount
            new_count = self._count_group_members_tx(tx, group_id)
            tx.execute("UPDATE customer_groups SET count = ?, updated_at = ? WHERE id = ?",
                       (new_count, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), group_id))
        updated = self._db.query_one("SELECT * FROM customer_groups WHERE id = ?", (group_id,))
        if updated is None:
            return None
        return {
            "id": updated["id"], "name": updated["name"], "type": updated["type"],
            "count": updated["count"], "createdAt": updated["created_at"],
            "updatedAt": updated["updated_at"], "editor": updated["editor"],
            "addedCount": added,
        }

    def get_group_with_members(self, group_id: str) -> dict | None:
        """获取分组详情（含成员列表，含客户聚合数据供详情抽屉使用）。"""
        group = self._db.query_one("SELECT * FROM customer_groups WHERE id = ?", (group_id,))
        if group is None:
            return None
        members = self._db.query(
            """SELECT cgm.customer_id,
                      cc.id AS contact_id,
                      cc.name AS customer_name,
                      cc.nickname,
                      cc.account_id,
                      cc.channel,
                      cc.channel_type,
                      cc.type,
                      cc.remark AS contact_remark,
                      cc.add_time,
                      cp.phone, cp.email, cp.company, cp.position,
                      cp.region, cp.age, cp.birthday,
                      cp.remark AS profile_remark,
                      cp.signature,
                      lc.created_at AS last_comm_time,
                      lc.content AS last_comm_content,
                      lc.ai_summary AS last_comm_ai_summary
               FROM customer_group_members cgm
               LEFT JOIN customer_profiles cp ON cp.id = cgm.customer_id
               LEFT JOIN channel_contacts cc ON cc.id = cp.contact_id
               LEFT JOIN (
                   SELECT customer_id, created_at, content, ai_summary,
                          ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) AS rn
                   FROM communication_records
               ) lc ON lc.customer_id = cp.id AND lc.rn = 1
               WHERE cgm.group_id = ?""",
            (group_id,),
        )

        # 批量聚合标签
        profile_ids = [m["customer_id"] for m in members]
        tag_map: dict[str, list[dict]] = {}
        if profile_ids:
            placeholders = ", ".join("?" for _ in profile_ids)
            tag_rows = self._db.query(
                f"""SELECT ctr.customer_id, ct.id AS tag_id, ct.name AS tag_name, ct.color,
                           ctg.id AS group_id, ctg.name AS group_name
                    FROM customer_tag_relations ctr
                    JOIN customer_tags ct ON ct.id = ctr.tag_id
                    JOIN customer_tag_groups ctg ON ctg.id = ct.group_id
                    WHERE ctr.customer_id IN ({placeholders})
                    ORDER BY ctg.name, ct.name""",
                tuple(profile_ids),
            )
            for tr in tag_rows:
                cid = tr["customer_id"]
                if cid not in tag_map:
                    tag_map[cid] = []
                tag_map[cid].append({
                    "id": tr["tag_id"],
                    "name": tr["tag_name"],
                    "color": tr["color"],
                    "groupId": tr["group_id"],
                    "groupName": tr["group_name"],
                })

        return {
            "id": group["id"], "name": group["name"], "type": group["type"],
            "count": group["count"], "createdAt": group["created_at"],
            "updatedAt": group["updated_at"], "editor": group["editor"],
            "members": [
                {
                    "customerId": m["customer_id"],
                    "customerName": m["customer_name"] or m["customer_id"],
                    "contactId": m["contact_id"] or "",
                    "nickname": m["nickname"] or "",
                    "accountId": m["account_id"] or "",
                    "channel": m["channel"] or "",
                    "channelType": m["channel_type"] or "",
                    "type": m["type"] or "",
                    "lastCommunicationTime": m.get("last_comm_time") or m.get("add_time") or "",
                    "lastCommunicationContent": m.get("last_comm_content") or "",
                    "lastCommunicationAiSummary": m.get("last_comm_ai_summary") or "",
                    "addTime": m.get("add_time") or "",
                    "tags": tag_map.get(m["customer_id"], []),
                    "remark": m.get("profile_remark") or m.get("contact_remark") or "",
                    "phone": m.get("phone") or "",
                    "email": m.get("email") or "",
                    "company": m.get("company") or "",
                    "position": m.get("position") or "",
                    "region": m.get("region") or "",
                    "age": m.get("age"),
                    "birthday": m.get("birthday") or "",
                    "signature": m.get("signature") or "",
                }
                for m in members
            ],
        }

    def delete_groups(self, group_ids: list[str]) -> int:
        """批量删除客户分组（事务内：先删关联 members，再删 groups 行）。

        Returns:
            实际删除的分组数量。
        """
        if not group_ids:
            return 0
        deleted = 0
        with self._db.transaction() as tx:
            for gid in group_ids:
                # 先级联删除成员关联
                tx.execute("DELETE FROM customer_group_members WHERE group_id = ?", (gid,))
                # 再删除分组主行
                rowcount = tx.execute("DELETE FROM customer_groups WHERE id = ?", (gid,))
                deleted += rowcount
        return deleted

    def batch_update_ai_summary(self, contact_ids: list[str], enabled: bool) -> int:
        """批量更新 AI 总结开关（按 contact_id 定位 customer_profiles）。"""
        if not contact_ids:
            return 0
        val = 1 if enabled else 0
        placeholders = ", ".join("?" for _ in contact_ids)
        return self._db.execute(
            f"UPDATE customer_profiles SET ai_summary_enabled = ? WHERE contact_id IN ({placeholders})",
            (val, *contact_ids),
        )

    def batch_update_tags(self, contact_ids: list[str], tag_ids: list[str], mode: str) -> dict:
        """批量操作客户标签。

        mode:
          - "add":    为每个 contact_id 添加所有 tag_ids（幂等）
          - "remove": 为每个 contact_id 删除所有 tag_ids
          - "replace": 为每个 contact_id 先清空再设为 tag_ids
        """
        if not contact_ids:
            return {"updated": 0}
        total = 0
        with self._db.transaction() as tx:
            for cid in contact_ids:
                if mode == "replace":
                    tx.execute("DELETE FROM customer_tag_relations WHERE customer_id = ?", (cid,))
                for tid in tag_ids:
                    if mode in ("add", "replace"):
                        rowcount = tx.execute(
                            "INSERT OR IGNORE INTO customer_tag_relations(customer_id, tag_id) VALUES (?, ?)",
                            (cid, tid),
                        )
                        total += rowcount
                    elif mode == "remove":
                        rowcount = tx.execute(
                            "DELETE FROM customer_tag_relations WHERE customer_id = ? AND tag_id = ?",
                            (cid, tid),
                        )
                        total += rowcount
        return {"updated": len(contact_ids), "rowsAffected": total}

    @staticmethod
    def _count_group_members_tx(tx, group_id: str) -> int:
        row = tx.query_one("SELECT COUNT(*) AS c FROM customer_group_members WHERE group_id = ?", (group_id,))
        return int(row["c"]) if row else 0


def _camel_to_snake(name: str) -> str:
    """camelCase → snake_case 简易转换。"""
    result = []
    for ch in name:
        if ch.isupper():
            result.append("_")
            result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)


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
from .pagination import Pagination


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(prefix)}"


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


class KnowledgeRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_by_bot(self, bot_id: str) -> list[dict]:
        """获取指定机器人的所有知识条目。"""
        rows = self._db.query(
            "SELECT * FROM knowledge_base WHERE bot_id = ? ORDER BY updated_at DESC",
            (bot_id,),
        )
        return [self._row_to_knowledge(row) for row in rows]

    def get(self, knowledge_id: str) -> Optional[dict]:
        """根据 ID 获取知识条目。"""
        row = self._db.query_one("SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,))
        return self._row_to_knowledge(row) if row else None

    def create(self, knowledge_id: str, bot_id: str, question: str, answer: str, tags: list[str], source: str) -> dict:
        """创建知识条目。"""
        tags_json = json.dumps(tags, ensure_ascii=False)
        self._db.execute(
            "INSERT INTO knowledge_base(id, bot_id, question, answer, tags, source) VALUES (?, ?, ?, ?, ?, ?)",
            (knowledge_id, bot_id, question, answer, tags_json, source),
        )
        return {
            "id": knowledge_id,
            "botId": bot_id,
            "question": question,
            "answer": answer,
            "tags": tags,
            "source": source,
        }

    def update(self, knowledge_id: str, question: str, answer: str, tags: list[str], source: str) -> None:
        """更新知识条目。"""
        tags_json = json.dumps(tags, ensure_ascii=False)
        self._db.execute(
            "UPDATE knowledge_base SET question = ?, answer = ?, tags = ?, source = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (question, answer, tags_json, source, knowledge_id),
        )

    def delete(self, knowledge_id: str) -> None:
        """删除知识条目。"""
        self._db.execute("DELETE FROM knowledge_base WHERE id = ?", (knowledge_id,))

    def _row_to_knowledge(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "botId": row["bot_id"],
            "question": row["question"],
            "answer": row["answer"],
            "tags": json.loads(row["tags"]),
            "source": row["source"],
            "updatedAt": row["updated_at"],
        }


class MaterialRepository:
    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    def list_by_bot(self, bot_id: str) -> list[dict]:
        """获取指定机器人的所有素材。"""
        rows = self._db.query(
            "SELECT * FROM materials WHERE bot_id = ? ORDER BY updated_at DESC",
            (bot_id,),
        )
        return [self._row_to_material(row) for row in rows]

    def get(self, material_id: str) -> Optional[dict]:
        """根据 ID 获取素材。"""
        row = self._db.query_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        return self._row_to_material(row) if row else None

    def create(self, material_id: str, bot_id: str, name: str, type_: str, size: int, category: str, url: Optional[str]) -> dict:
        """创建素材。"""
        self._db.execute(
            "INSERT INTO materials(id, bot_id, name, type, size, category, url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (material_id, bot_id, name, type_, size, category, url),
        )
        return {
            "id": material_id,
            "botId": bot_id,
            "name": name,
            "type": type_,
            "size": size,
            "category": category,
            "url": url,
            "usageCount": 0,
        }

    def delete(self, material_id: str) -> None:
        """删除素材。"""
        self._db.execute("DELETE FROM materials WHERE id = ?", (material_id,))

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
            "usageCount": row["usage_count"],
            "uploadedAt": row["created_at"],
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


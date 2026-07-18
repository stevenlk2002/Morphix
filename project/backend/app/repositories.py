"""数据访问层（Repository）。

设计目标：
- 所有 SQL 集中在此，Router 层只调用 Repository 方法，不感知 SQL。
- Repository 只依赖 `DatabaseBackend` 接口，可无痛切换 SQLite / PostgreSQL。
- 列表查询统一支持分页，兑现「分页/索引规范」性能落地要求。

行 -> DTO 的映射保持与原 main.py 完全一致，确保对外 contract 不变。
"""
from __future__ import annotations

import json
from typing import Optional

from .database import DatabaseBackend
from .pagination import Pagination


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


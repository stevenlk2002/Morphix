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


# ---- 模块级 helper（账号卡片增强，T01） ----
def _resolve_avatar_url(user_info: dict | None) -> str:
    """从 iPad 协议 userInfo 解析真实头像 URL。

    优先级：`avatar` > `headImgUrl` > `headimgurl`；空值/缺失返回空串 `''`
    （与项目「空串表示未设置」约定一致，避免 NULL 判空分支）。
    """
    if not isinstance(user_info, dict):
        return ""
    for key in ("avatar", "headImgUrl", "headimgurl"):
        val = user_info.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def assert_online_bot(repo: "BotRepository", bot_id: str | None) -> dict | None:
    """校验「已上线」机器人（唯一来源）。

    - `bot_id` 为空 → 返回 None（允许空态，不清空默认机器人）
    - 机器人不存在 → 抛 ValueError("机器人不存在")
    - 机器人未上线(status!='online') → 抛 ValueError("机器人未上线，无法设为默认接管方")
    路由层捕获 ValueError → 400。
    """
    if not bot_id:
        return None
    bot = repo.get(bot_id)
    if bot is None:
        raise ValueError("机器人不存在")
    if bot.get("status") != "online":
        raise ValueError("机器人未上线，无法设为默认接管方")
    return bot


# ---- 行 -> DTO 映射（与原实现字段严格对齐）----
def row_to_bot(row: dict) -> dict:
    """行 -> 机器人 DTO。

    在原有契约字段（id/name/project/status/workflow/tone/trainingPrompt/score）
    基础上补充 created_at / updated_at：前端 Bots 列表需要「编辑于 {updatedAt}」
    与按时间排序。updated_at 列在部分旧数据上可能为 NULL，统一兜底为 created_at。
    """
    created_at = row["created_at"]
    return {
        "id": row["id"],
        "name": row["name"],
        "project": row["project"],
        "status": row["status"],
        "workflow": row["workflow"],
        "tone": row["tone"],
        "trainingPrompt": row["training_prompt"],
        "score": row["score"],
        "createdAt": created_at,
        "updatedAt": row.get("updated_at") or created_at,
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
        # 回查整行，补齐 created_at / updated_at，使返回结构与 GET /bots 一致
        # （前端 mapBot 需要 createdAt / updatedAt，缺失会显示空「编辑于」）。
        row = self._db.query_one("SELECT * FROM bots WHERE id = ?", (bot_id,))
        if row is None:
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
        return row_to_bot(row)

    def mark_trained(self, bot_id: str) -> None:
        self._db.execute(
            "UPDATE bots SET status = ?, score = MIN(score + 8, 99) WHERE id = ?",
            ("online", bot_id),
        )

    def delete(self, bot_id: str) -> bool:
        existing = self._db.query_one("SELECT id FROM bots WHERE id = ?", (bot_id,))
        if not existing:
            return False
        self._db.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
        return True

    def get(self, bot_id: str) -> dict | None:
        """按 id 取机器人（完整 DTO）。不存在返回 None。"""
        row = self._db.query_one("SELECT * FROM bots WHERE id = ?", (bot_id,))
        return row_to_bot(row) if row else None

    def list_online_bots(self) -> list[dict]:
        """列出所有已上线(status='online')的机器人（选择器数据源）。"""
        rows = self._db.query(
            "SELECT id, name FROM bots WHERE status = 'online' ORDER BY name"
        )
        return [{"id": r["id"], "name": r["name"]} for r in rows]


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
        "ipadUuid": row.get("ipad_uuid", ""),
        "ipadUserInfo": (json.loads(row.get("ipad_user_info") or "{}") or None),
        "hostStatus": row.get("host_status", "pending"),
        "syncStatus": row.get("sync_status", ""),
        "lastSyncAt": row.get("last_sync_at", ""),
        # —— 账号卡片增强（本期） ——
        "avatar": row.get("avatar", ""),
        "defaultSingleBotId": row.get("default_single_bot_id", ""),
        "defaultGroupBotId": row.get("default_group_bot_id", ""),
        # 聚合的默认机器人显示名（双 LEFT JOIN bots，可能为 None）
        "defaultSingleBotName": row.get("default_single_bot_name"),
        "defaultGroupBotName": row.get("default_group_bot_name"),
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
        "avatar": row.get("avatar", ""),
    }


def row_to_session(row: dict) -> dict:
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "contactId": row.get("contact_id"),
        "remoteSessionId": row.get("remote_session_id"),
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
        "tags": _parse_json_field(row.get("tags", "[]"), []),
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
                "description": r.get("description", ""),
            }
            for r in rows
        ]

    def count_teams(self) -> int:
        """团队总数（用于删除末团队守卫）。"""
        row = self._db.query_one("SELECT COUNT(*) AS c FROM teams")
        return int(row["c"]) if row else 0

    def get_team(self, team_id: str) -> dict | None:
        """按 id 取团队（含 description）；不存在返回 None。"""
        row = self._db.query_one("SELECT * FROM teams WHERE id=?", (team_id,))
        if row is None:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "seatsLeft": row["seats_left"],
            "energyValue": row["energy_value"],
            "description": row.get("description", ""),
        }

    def create_team(
        self, name: str, seats_left: int = 1, energy_value: int = 0, description: str = ""
    ) -> dict:
        # seats 默认 1 / energy 默认 0（对齐种子「初始团队」逻辑，详见 PRD Q1）
        team_id = _generate_id("team")
        self._db.execute(
            "INSERT INTO teams(id, name, seats_left, energy_value, description) VALUES (?, ?, ?, ?, ?)",
            (team_id, name, seats_left, energy_value, description),
        )
        return {
            "id": team_id,
            "name": name,
            "seatsLeft": seats_left,
            "energyValue": energy_value,
            "description": description,
        }

    def update_team(
        self, team_id: str, name: str | None = None, description: str | None = None
    ) -> dict | None:
        """部分更新团队（name / description 至少其一）；回查返回最新快照。"""
        fields: list[str] = []
        params: list[object] = []
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if fields:
            params.append(team_id)
            self._db.execute(
                f"UPDATE teams SET {', '.join(fields)} WHERE id=?", params
            )
        return self.get_team(team_id)

    def delete_team(self, team_id: str) -> bool:
        """硬删团队：先清关联账号 team_id、再删成员、最后删团队（避免 FK 冲突）。"""
        # 1) 关联渠道账号 team_id 置空（保留账号数据可用，不清删）
        self._db.execute(
            "UPDATE channel_accounts SET team_id='' WHERE team_id=?", (team_id,)
        )
        # 2) 删除团队成员（team_members.team_id 外键关联 teams，须先于团队删除）
        self._db.execute("DELETE FROM team_members WHERE team_id=?", (team_id,))
        # 3) 删除团队
        return self._db.execute("DELETE FROM teams WHERE id=?", (team_id,)) > 0

    def list_team_members(self, team_id: str) -> list[dict]:
        """团队成员列表（snake_case DB → camelCase）。"""
        rows = self._db.query(
            "SELECT * FROM team_members WHERE team_id=? ORDER BY joined_at, id",
            (team_id,),
        )
        return [
            {
                "id": r["id"],
                "teamId": r["team_id"],
                "userId": r["user_id"],
                "account": r["account"],
                "nickname": r["nickname"],
                "role": r["role"],
                "joinedAt": r["joined_at"],
            }
            for r in rows
        ]

    def add_team_members(self, team_id: str, members: list[dict]) -> list[dict]:
        """批量添加成员（members: 已解析的 {user_id, account, nickname, role}）。

        按 (team_id, user_id) 去重（UNIQUE 约束 + 预查），仅返回本次新增成员。
        """
        existing = {
            r["user_id"]
            for r in self._db.query(
                "SELECT user_id FROM team_members WHERE team_id=?", (team_id,)
            )
        }
        inserted: list[dict] = []
        for m in members:
            user_id = m.get("user_id", "")
            if not user_id or user_id in existing:
                continue
            member_id = _generate_id("tm")
            joined_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._db.execute(
                "INSERT INTO team_members(id, team_id, user_id, account, nickname, role, joined_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    member_id,
                    team_id,
                    user_id,
                    m.get("account", ""),
                    m.get("nickname", ""),
                    m.get("role", ""),
                    joined_at,
                ),
            )
            inserted.append(
                {
                    "id": member_id,
                    "teamId": team_id,
                    "userId": user_id,
                    "account": m.get("account", ""),
                    "nickname": m.get("nickname", ""),
                    "role": m.get("role", ""),
                    "joinedAt": joined_at,
                }
            )
            existing.add(user_id)
        return inserted

    # ---- accounts（扩展 DTO，JOIN channel_seats + teams） ----
    def list_accounts_enriched(self) -> list[dict]:
        sql = (
            "SELECT a.*, s.seats_left, s.online_sessions, t.name AS team_name, "
            "       b1.name AS default_single_bot_name, "
            "       b2.name AS default_group_bot_name "
            "FROM channel_accounts a "
            "LEFT JOIN channel_seats s ON s.channel_account_id = a.id "
            "LEFT JOIN teams t ON t.id = a.team_id "
            "LEFT JOIN bots b1 ON b1.id = a.default_single_bot_id "
            "LEFT JOIN bots b2 ON b2.id = a.default_group_bot_id "
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

    def create_account_with_ipad(
        self,
        channel_type: str,
        protocol: str,
        team_id: str,
        name: str | None,
        ipad_uuid: str,
        ipad_user_info: dict | str | None,
        host_status: str = "hosted",
        avatar: str = "",
    ) -> dict:
        """企业微信 iPad 协议托管落库（loginType==2 时由路由自动调用）。

        复用 `_generate_id("acc")`；channel_label 同 `create_account`；
        status='online'、bound_bot='yefengqiu'、daily_quota=0、sessions_count=0。
        `ipad_user_info` 以 JSON 字符串持久化（已是 str 则原样落库）。
        """
        account_id = _generate_id("acc")
        channel_label = {
            "wecom": "企业微信",
            "wechat": "微信",
            "whatsapp": "WhatsApp",
            "business_whatsapp": "企业WhatsApp",
        }.get(channel_type, "渠道账号")
        account_name = name or f"{channel_label}-新账号"
        if isinstance(ipad_user_info, str):
            ipad_user_info_str = ipad_user_info or "{}"
        elif ipad_user_info is None:
            ipad_user_info_str = "{}"
        else:
            ipad_user_info_str = json.dumps(ipad_user_info, ensure_ascii=False)
        self._db.execute(
            "INSERT INTO channel_accounts("
            "id, channel, account_name, status, bound_bot, daily_quota, team_id, "
            "channel_type, protocol, sessions_count, ipad_uuid, ipad_user_info, host_status, avatar) "
            "VALUES (?, ?, ?, 'online', ?, 0, ?, ?, ?, 0, ?, ?, ?, ?)",
            (
                account_id, channel_label, account_name, "yefengqiu", team_id,
                channel_type, protocol, ipad_uuid, ipad_user_info_str, host_status,
                avatar or "",
            ),
        )
        row = self._db.query_one(
            "SELECT a.*, s.seats_left, s.online_sessions, t.name AS team_name, "
            "       b1.name AS default_single_bot_name, "
            "       b2.name AS default_group_bot_name "
            "FROM channel_accounts a "
            "LEFT JOIN channel_seats s ON s.channel_account_id = a.id "
            "LEFT JOIN teams t ON t.id = a.team_id "
            "LEFT JOIN bots b1 ON b1.id = a.default_single_bot_id "
            "LEFT JOIN bots b2 ON b2.id = a.default_group_bot_id "
            "WHERE a.id = ?",
            (account_id,),
        )
        if row is None:
            return {
                "id": account_id, "name": account_name, "channel": channel_label,
                "channelType": channel_type, "protocol": protocol, "status": "online",
                "online": True, "sessionsCount": 0, "teamId": team_id,
                "boundBot": "yefengqiu", "ipadUuid": ipad_uuid,
                "ipadUserInfo": (ipad_user_info if isinstance(ipad_user_info, dict) else None),
                "hostStatus": host_status,
                "avatar": avatar or "",
                "defaultSingleBotId": "",
                "defaultGroupBotId": "",
                "defaultSingleBotName": None,
                "defaultGroupBotName": None,
            }
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
        # LEFT JOIN channel_contacts，把真实昵称作为会话显示名带出，避免会话列表 /
        # 右侧面板展示 raw sessionid 编号（见任务 Issue #2）。
        # 关联条件覆盖「按 contact_id」与「按 remote_session_id 反查 user_id」两种情形；
        # COALESCE 优先取联系人的真实昵称，兜底回退到会话自身 name。
        sql = (
            "SELECT cs.*, "
            "COALESCE(cc.nickname, cc.name, cg.nickname, cs.name) AS name "
            "FROM channel_sessions cs "
            "LEFT JOIN channel_contacts cc ON cc.account_id = cs.account_id "
            "AND (cc.id = cs.contact_id OR cc.user_id = cs.remote_session_id) "
            "LEFT JOIN channel_groups cg ON cg.account_id = cs.account_id "
            "AND cg.room_id = cs.remote_session_id "
            "WHERE 1=1"
        )
        params: list = []
        if account_id:
            sql += " AND cs.account_id = ?"
            params.append(account_id)
        if read in ("read", "unread"):
            sql += " AND cs.read_status = ?"
            params.append(read)
        if hosted in ("hosted", "unhosted"):
            sql += " AND cs.hosted_status = ?"
            params.append(hosted)
        if online in ("online", "offline"):
            sql += " AND cs.online_status = ?"
            params.append(online)
        if search:
            # 搜索同时匹配会话名与联系人昵称，保证昵称可被检索。
            sql += " AND (cs.name LIKE ? OR cc.nickname LIKE ?)"
            params.append(f"%{search}%")
            params.append(f"%{search}%")
        sql += " ORDER BY cs.last_time DESC, cs.id"
        rows = self._db.query(sql, tuple(params))
        # 结果集中 `name` 已由 COALESCE(cc.nickname, cc.name, s.name) 覆盖为真实昵称，
        # 直接交给 row_to_session 映射即可（见任务 Issue #2）。
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

    # ---- iPad 协议同步域（T01/T02） ----
    def get_account_by_id(self, account_id: str) -> dict | None:
        """按 id 取账号（扩展 DTO，含聚合的默认机器人名）。"""
        row = self._db.query_one(
            "SELECT a.*, s.seats_left, s.online_sessions, t.name AS team_name, "
            "       b1.name AS default_single_bot_name, "
            "       b2.name AS default_group_bot_name "
            "FROM channel_accounts a "
            "LEFT JOIN channel_seats s ON s.channel_account_id = a.id "
            "LEFT JOIN teams t ON t.id = a.team_id "
            "LEFT JOIN bots b1 ON b1.id = a.default_single_bot_id "
            "LEFT JOIN bots b2 ON b2.id = a.default_group_bot_id "
            "WHERE a.id = ?",
            (account_id,),
        )
        return row_to_account(row) if row else None

    def set_default_bots(
        self, account_id: str, single_bot_id: str, group_bot_id: str
    ) -> None:
        """写回账号默认单聊/群聊机器人（空串表示未设置）。

        空值统一用空串 `''`，前端判空用 `!botId`（不使用 NULL）。
        """
        self._db.execute(
            "UPDATE channel_accounts "
            "SET default_single_bot_id = ?, default_group_bot_id = ? "
            "WHERE id = ?",
            (single_bot_id or "", group_bot_id or "", account_id),
        )

    def update_account_status(self, account_id: str, status: str) -> dict | None:
        """更新账号状态并返回更新后的账号 DTO。"""
        self._db.execute(
            "UPDATE channel_accounts SET status=? WHERE id=?",
            (status, account_id),
        )
        return self.get_account_by_id(account_id)

    def set_account_sync_status(
        self, account_id: str, sync_status: str, last_sync_at: str
    ) -> None:
        """写入同步状态 / 最近同步时间。"""
        self._db.execute(
            "UPDATE channel_accounts SET sync_status = ?, last_sync_at = ? WHERE id = ?",
            (sync_status, last_sync_at, account_id),
        )

    def get_contact_by_id(self, contact_id: str) -> dict | None:
        """按 id 取联系人原始行（反查 user_id 用）。"""
        return self._db.query_one(
            "SELECT * FROM channel_contacts WHERE id = ?", (contact_id,)
        )

    def get_group_by_room_id(self, account_id: str, room_id: str) -> dict | None:
        """按 (account_id, room_id) 取群，返回 row_to_group DTO（与 get_group_by_id 一致）。

        注意：必须返回 DTO（camelCase: accountId/roomId/...），否则
        routers/ipad_sync.group_members 直接将其作为 GroupDetailDTO.group 返回时，
        FastAPI 响应校验会因字段为 snake_case 而抛出 ResponseValidationError（生产 500）。
        """
        row = self._db.query_one(
            "SELECT * FROM channel_groups WHERE account_id = ? AND room_id = ?",
            (account_id, room_id),
        )
        return row_to_group(row) if row else None

    def get_session_by_id(self, session_id: str) -> dict | None:
        """按 id 取会话原始行（反查 user_id/room_id + isRoom 用）。"""
        return self._db.query_one(
            "SELECT * FROM channel_sessions WHERE id = ?", (session_id,)
        )

    def upsert_channel_contact(self, contact: dict) -> None:
        """upsert 渠道联系人（自然键 id = {account_id}:{user_id}）。

        含 `avatar` 列：同步时写入真实头像 URL（GetInnerContacts /
        GetExternalContacts 返回 `avatar` 字段），缺失时落空串（与既有
        列「空串表示未设置」约定一致，避免 NULL 判空分支）。
        """
        self._db.execute(
            "INSERT OR REPLACE INTO channel_contacts("
            "id, account_id, channel, channel_type, name, nickname, type, status, "
            "remark, description, add_time, source, user_id, label_ids, raw_status, extra_json, avatar) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                contact["id"], contact["account_id"], contact["channel"],
                contact["channel_type"], contact["name"], contact["nickname"],
                contact["type"], contact["status"], contact["remark"],
                contact["description"], contact["add_time"], contact["source"],
                contact["user_id"], contact["label_ids"], contact["raw_status"],
                contact["extra_json"], contact.get("avatar", ""),
            ),
        )

    def upsert_customer_profile_for_contact(
        self, contact_id: str, fields: dict
    ) -> None:
        """upsert 客户档案（id = contact_id 保证幂等；写入 iPad 标签 tags）。

        fields 约定：phone / company / position / remark / add_time /
        add_channel / tags(JSON 数组，外部联系人 labelid[] 原样镜像，决策 #2)。
        """
        tags = fields.get("tags", [])
        tags_json = tags if isinstance(tags, str) else json.dumps(tags, ensure_ascii=False)
        self._db.execute(
            "INSERT OR REPLACE INTO customer_profiles("
            "id, contact_id, phone, email, company, position, region, age, birthday, "
            "remark, add_time, add_channel, signature, ai_summary_enabled, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                contact_id, contact_id,
                fields.get("phone", ""),
                "",
                fields.get("company", ""),
                fields.get("position", ""),
                "",
                fields.get("age"),
                "",
                fields.get("remark", ""),
                fields.get("add_time", ""),
                fields.get("add_channel", ""),
                "",
                0,
                tags_json,
            ),
        )

    def upsert_channel_session(self, session: dict) -> None:
        """upsert 渠道会话（自然键 id = {account_id}:{sessionid}）。"""
        self._db.execute(
            "INSERT OR REPLACE INTO channel_sessions("
            "id, account_id, contact_id, name, channel, channel_type, last_message, "
            "last_time, unread_count, read_status, hosted_status, hosted_bot_id, owner, "
            "online_status, session_type, external_tag, add_time, hosting_chain, "
            "remote_session_id, msg_type, begin_msg_seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session["id"], session["account_id"], session.get("contact_id"),
                session["name"], session["channel"], session["channel_type"],
                session.get("last_message", ""), session.get("last_time", ""),
                session.get("unread_count", 0), session.get("read_status", "unread"),
                session.get("hosted_status", "unhosted"), session.get("hosted_bot_id"),
                session.get("owner", ""), session.get("online_status", "online"),
                session.get("session_type", ""), session.get("external_tag", ""),
                session.get("add_time", ""), session.get("hosting_chain", "-"),
                session.get("remote_session_id", ""), session.get("msg_type", 0),
                session.get("begin_msg_seq", ""),
            ),
        )

    def upsert_channel_group(self, group: dict) -> None:
        """upsert 客户群（自然键 id = {account_id}:{room_id}）。"""
        self._db.execute(
            "INSERT OR REPLACE INTO channel_groups("
            "id, account_id, room_id, group_type, nickname, total, room_url, "
            "notice_content, create_time, update_time, extra_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                group["id"], group["account_id"], group["room_id"],
                group.get("group_type", "customer_group"), group["nickname"],
                group.get("total", 0), group.get("room_url", ""),
                group.get("notice_content", ""), group.get("create_time", ""),
                group.get("update_time", ""), group.get("extra_json", "{}"),
            ),
        )

    def upsert_channel_group_member(self, member: dict) -> None:
        """upsert 群成员（自然键 id = {group_id}:{uin|user_id}）。"""
        self._db.execute(
            "INSERT OR REPLACE INTO channel_group_members("
            "id, group_id, uin, user_id, nickname, realname, avatar, room_nickname, "
            "sex, mobile, join_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                member["id"], member["group_id"], member.get("uin", ""),
                member.get("user_id", ""), member.get("nickname", ""),
                member.get("realname", ""), member.get("avatar", ""),
                member.get("room_nickname", ""), member.get("sex", 0),
                member.get("mobile", ""), member.get("join_time", ""),
            ),
        )

    def list_groups(
        self, account_id: str, group_type: str | None = None
    ) -> list[dict]:
        """列出某账号下的群（默认按人数降序）。"""
        if group_type:
            rows = self._db.query(
                "SELECT * FROM channel_groups WHERE account_id = ? AND group_type = ? "
                "ORDER BY total DESC, nickname",
                (account_id, group_type),
            )
        else:
            rows = self._db.query(
                "SELECT * FROM channel_groups WHERE account_id = ? "
                "ORDER BY total DESC, nickname",
                (account_id,),
            )
        return [row_to_group(r) for r in rows]

    def list_group_members(self, group_id: str) -> list[dict]:
        """列出某群成员（按昵称排序）。"""
        rows = self._db.query(
            "SELECT * FROM channel_group_members WHERE group_id = ? ORDER BY nickname",
            (group_id,),
        )
        return [row_to_group_member(r) for r in rows]

    def get_group_by_id(self, group_id: str) -> dict | None:
        """按 id 取群（含成员聚合）。"""
        row = self._db.query_one("SELECT * FROM channel_groups WHERE id = ?", (group_id,))
        return row_to_group(row) if row else None

    # ---- 群成员 / 群 / 群会话 维护（T04 群管理） ----
    def count_group_members(self, group_id: str) -> int:
        """群成员数。"""
        row = self._db.query_one(
            "SELECT COUNT(*) AS c FROM channel_group_members WHERE group_id = ?",
            (group_id,),
        )
        return int(row["c"]) if row else 0

    def delete_channel_group_member(self, group_id: str, user_id: str) -> int:
        """按 (group_id, user_id) 删群成员，返回受影响行数。"""
        return self._db.execute(
            "DELETE FROM channel_group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )

    def delete_all_channel_group_members(self, group_id: str) -> int:
        return self._db.execute(
            "DELETE FROM channel_group_members WHERE group_id = ?", (group_id,)
        )

    def delete_channel_group(self, group_id: str) -> int:
        return self._db.execute("DELETE FROM channel_groups WHERE id = ?", (group_id,))

    def delete_session_for_room(self, account_id: str, room_id: str) -> int:
        """删某账号下某 room 的群会话（id = {account_id}:{room_id}）。"""
        sid = f"{account_id}:{room_id}"
        return self._db.execute("DELETE FROM channel_sessions WHERE id = ?", (sid,))


    # ---- P1+P2 iPad 同步域扩展方法 ----
    def upsert_ipad_label(self, account_id: str, label: dict) -> str | None:
        """同步一个 iPad 标签 → 每账号一个 iPad 标签组 + 标签 + ipad_label_map 映射。"""
        ipad_label_id = str(label.get("id") or "")
        if not ipad_label_id:
            return None
        name = label.get("name") or ipad_label_id
        # 协议常省略/返回 null 的 label_type / sync_type；用 `or` 让 None 回落默认值，
        # 而非依赖 .get(..., default)（仅在“缺省键”时生效，key 存在且为 None 时仍崩）。
        sync_type = int(label.get("sync_type") or 1)
        label_type = int(label.get("label_type") or 0)
        label_groupid = str(label.get("label_groupid") or "")
        group_id = f"tg-ipad-{account_id}"
        tag_id = f"itag-{account_id}-{ipad_label_id}"
        if not self._db.query_one(
            "SELECT id FROM customer_tag_groups WHERE id = ?", (group_id,)
        ):
            self._db.execute(
                "INSERT INTO customer_tag_groups(id, name, is_hot) VALUES (?, ?, 0)",
                (group_id, "iPad 标签"),
            )
        self._db.execute(
            "INSERT OR REPLACE INTO customer_tags(id, group_id, name, color, rule) "
            "VALUES (?, ?, ?, 'blue', '')",
            (tag_id, group_id, name),
        )
        self._db.execute(
            "INSERT OR REPLACE INTO ipad_label_map("
            "account_id, ipad_label_id, label_name, label_type, label_group_id, "
            "tag_id, sync_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account_id, ipad_label_id, name, label_type, label_groupid, tag_id, sync_type),
        )
        return tag_id

    def get_ipad_labels(self, account_id: str, sync_type: int | None = None) -> list[dict]:
        """列出某账号的 iPad 标签（按名称排序；sync_type 可过滤 1=企业 2=个人）。"""
        if sync_type is None:
            rows = self._db.query(
                "SELECT * FROM ipad_label_map WHERE account_id = ? ORDER BY label_name",
                (account_id,),
            )
        else:
            rows = self._db.query(
                "SELECT * FROM ipad_label_map WHERE account_id = ? AND sync_type = ? ORDER BY label_name",
                (account_id, int(sync_type)),
            )
        return [self.row_to_label(r) for r in rows]

    @staticmethod
    def row_to_label(row: dict) -> dict:
        """ipad_label_map 行 -> LabelDTO。"""
        return {
            "accountId": row["account_id"],
            "labelId": row["ipad_label_id"],
            "labelName": row["label_name"],
            "labelType": row["label_type"],
            "labelGroupId": row["label_group_id"],
            "tagId": row["tag_id"],
            "syncType": row["sync_type"],
        }

    def map_ipad_labels_to_names(
        self, account_id: str, label_ids: list[str]
    ) -> list[dict]:
        """把 iPad labelid[] 映射为真实标签名列表（保持入参顺序）。"""
        if not label_ids:
            return []
        placeholders = ", ".join("?" for _ in label_ids)
        rows = self._db.query(
            f"SELECT ipad_label_id, label_name FROM ipad_label_map "
            f"WHERE account_id = ? AND ipad_label_id IN ({placeholders})",
            (account_id, *label_ids),
        )
        by_id = {r["ipad_label_id"]: r["label_name"] for r in rows}
        return [{"labelId": lid, "labelName": by_id.get(lid, lid)} for lid in label_ids]

    def get_contact_ipad_labels(self, account_id: str, contact_id: str) -> list[dict]:
        """取联系人 iPad 标签并以真实标签名呈现（来自 customer_profiles.tags 镜像）。"""
        profile = self._db.query_one(
            "SELECT tags FROM customer_profiles WHERE contact_id = ?", (contact_id,)
        )
        if not profile:
            return []
        label_ids = _parse_json_field(profile.get("tags"), [])
        if not isinstance(label_ids, list):
            label_ids = []
        return self.map_ipad_labels_to_names(account_id, label_ids)

    def set_contact_ipad_labels(
        self, account_id: str, contact_id: str, label_ids: list[str]
    ) -> None:
        """持久化联系人 iPad 标签（Morphix 侧双写）。

        - 重写 `customer_profiles.tags` 为 labelid[] 镜像；
        - 重建该客户的 iPad 标签关系（保留非 iPad 标签关系）。
        iPad 侧生效由服务层先调 `UserAddLabelsReq` 保证（决策 #9）。
        """
        profile = self._db.query_one(
            "SELECT id FROM customer_profiles WHERE contact_id = ?", (contact_id,)
        )
        if profile is None:
            return
        customer_id = profile["id"]
        self._db.execute(
            "UPDATE customer_profiles SET tags = ? WHERE contact_id = ?",
            (json.dumps(label_ids, ensure_ascii=False), contact_id),
        )
        ipad_tags = self._db.query(
            "SELECT tag_id FROM ipad_label_map WHERE account_id = ?", (account_id,)
        )
        ipad_tag_ids = {r["tag_id"] for r in ipad_tags}
        cur = self._db.query(
            "SELECT tag_id FROM customer_tag_relations WHERE customer_id = ?", (customer_id,)
        )
        for r in cur:
            if r["tag_id"] in ipad_tag_ids:
                self._db.execute(
                    "DELETE FROM customer_tag_relations WHERE customer_id = ? AND tag_id = ?",
                    (customer_id, r["tag_id"]),
                )
        for lid in label_ids:
            m = self._db.query_one(
                "SELECT tag_id FROM ipad_label_map WHERE account_id = ? AND ipad_label_id = ?",
                (account_id, lid),
            )
            if m:
                self._db.execute(
                    "INSERT OR IGNORE INTO customer_tag_relations(customer_id, tag_id) VALUES (?, ?)",
                    (customer_id, m["tag_id"]),
                )

    def set_account_callback(
        self, account_id: str, url: str, callback_type: str
    ) -> None:
        """写入账号回调配置（P2-4）。"""
        self._db.execute(
            "UPDATE channel_accounts SET callback_url = ?, callback_type = ? WHERE id = ?",
            (url or "", callback_type or "", account_id),
        )

    def add_contact_from_search(self, account_id: str, item: dict) -> str | None:
        """把搜索添加结果落为渠道联系人 + 客户档案（extra_json 存 vid/openId/ticket）。"""
        user_id = str(item.get("user_id") or "")
        if not user_id:
            return None
        cid = f"{account_id}:{user_id}"
        name = item.get("name") or ""
        extra = {
            "headImg": item.get("headImg"),
            "ticket": item.get("ticket"),
            "openId": item.get("openId"),
            "corp_id": item.get("corp_id"),
            "state": item.get("state"),
        }
        self._db.execute(
            "INSERT OR REPLACE INTO channel_contacts("
            "id, account_id, channel, channel_type, name, nickname, type, status, "
            "remark, description, add_time, source, user_id, label_ids, raw_status, extra_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cid, account_id, "企业微信", "wecom", name, name, "customer", "online",
                "", "", "", "search", user_id, "[]", "", json.dumps(extra, ensure_ascii=False),
            ),
        )
        self._db.execute(
            "INSERT OR REPLACE INTO customer_profiles("
            "id, contact_id, phone, email, company, position, region, age, birthday, "
            "remark, add_time, add_channel, signature, ai_summary_enabled, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (cid, cid, "", "", "", "", "", None, "", "", "", "search", "", "[]"),
        )
        return cid

    def message_exists(self, conversation_id: str, server_id: str) -> bool:
        """按 (conversation_id, server_id) 判断消息是否已落库（回调幂等）。"""
        if not server_id:
            return False
        row = self._db.query_one(
            "SELECT id FROM messages WHERE conversation_id = ? AND server_id = ?",
            (conversation_id, server_id),
        )
        return row is not None

    def upsert_channel_message(self, msg: dict) -> None:
        """upsert 渠道消息（P2；复用 messages 表，按 id 幂等，server_id 作为去重键）。"""
        media_meta = msg.get("media_meta", "{}")
        if not isinstance(media_meta, str):
            media_meta = json.dumps(media_meta, ensure_ascii=False)
        self._db.execute(
            "INSERT OR REPLACE INTO messages("
            "id, conversation_id, sender_type, content, created_at, "
            "server_id, msg_type, sender_id, direction, content_type, "
            "media_url, media_meta, is_read, channel_account_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                msg["id"], msg["conversation_id"], msg.get("sender_type", "user"),
                msg.get("content", ""), msg.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                msg.get("server_id", ""), int(msg.get("msg_type", 0)), msg.get("sender_id", ""),
                msg.get("direction", "inbound"), msg.get("content_type", "text"),
                msg.get("media_url", ""), media_meta, int(msg.get("is_read", 0)),
                msg.get("channel_account_id", ""),
            ),
        )

    def row_to_message_ext(self, row: dict) -> dict:
        """messages 行 -> MessageExtDTO（含 serverId/msgType/direction/contentType/media）。"""
        return {
            "id": row["id"],
            "conversationId": row["conversation_id"],
            "senderType": row["sender_type"],
            "content": row["content"],
            "createdAt": row["created_at"],
            "serverId": row.get("server_id", ""),
            "msgType": int(row.get("msg_type", 0) or 0),
            "senderId": row.get("sender_id", ""),
            "direction": row.get("direction", "inbound"),
            "contentType": row.get("content_type", "text"),
            "mediaUrl": row.get("media_url", ""),
            "mediaMeta": _parse_json_field(row.get("media_meta"), {}),
            "isRead": bool(row.get("is_read", 0)),
            "channelAccountId": row.get("channel_account_id", ""),
        }

    def list_session_messages_ext(
        self, conversation_id: str, cursor: str = "", limit: int = 20
    ) -> list[dict]:
        """分页加载会话消息（游标续查；cursor 为最旧已加载消息的 server_id）。

        返回按时间升序，便于前端直接追加渲染；无 cursor 取最新一页。
        """
        if cursor:
            cur = self._db.query_one(
                "SELECT created_at FROM messages WHERE conversation_id = ? AND server_id = ?",
                (conversation_id, cursor),
            )
            if cur:
                rows = self._db.query(
                    "SELECT * FROM messages WHERE conversation_id = ? AND created_at < ? "
                    "ORDER BY created_at DESC, id DESC LIMIT ?",
                    (conversation_id, cur["created_at"], int(limit)),
                )
            else:
                rows = self._db.query(
                    "SELECT * FROM messages WHERE conversation_id = ? "
                    "ORDER BY created_at DESC, id DESC LIMIT ?",
                    (conversation_id, int(limit)),
                )
        else:
            rows = self._db.query(
                "SELECT * FROM messages WHERE conversation_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (conversation_id, int(limit)),
            )
        rows.reverse()
        return [self.row_to_message_ext(r) for r in rows]

    def mark_session_read_db(self, session_id: str) -> dict | None:
        """将会话未读清零并标记已读（P2-2）。"""
        self._db.execute(
            "UPDATE channel_sessions SET unread_count = 0, read_status = 'read' WHERE id = ?",
            (session_id,),
        )
        row = self._db.query_one("SELECT * FROM channel_sessions WHERE id = ?", (session_id,))
        return row_to_session(row) if row else None

    def create_session_for_room(
        self,
        account_id: str,
        room_id: str,
        name: str,
        channel: str,
        channel_type: str,
    ) -> dict | None:
        """为新建群落一个群会话行（支撑「直接点击聊天」）。

        session_type='group'、msg_type=1、unread_count=0、read_status='read'、
        remote_session_id=room_id、online_status='offline'、hosted_status='unhosted'。
        已存在（按 id）则跳过，返回既有行（DTO）；否则插入并返回新行（DTO）。
        """
        sid = f"{account_id}:{room_id}"
        existing = self._db.query_one(
            "SELECT id FROM channel_sessions WHERE id = ?", (sid,)
        )
        if existing:
            row = self._db.query_one(
                "SELECT * FROM channel_sessions WHERE id = ?", (sid,)
            )
            return row_to_session(row) if row else None
        now = datetime.now().isoformat(timespec="seconds")
        self._db.execute(
            "INSERT INTO channel_sessions("
            "id, account_id, contact_id, name, channel, channel_type, last_message, "
            "last_time, unread_count, read_status, hosted_status, hosted_bot_id, owner, "
            "online_status, session_type, external_tag, add_time, hosting_chain, "
            "remote_session_id, msg_type, begin_msg_seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sid, account_id, None, name, channel, channel_type,
                "", now, 0, "read", "unhosted", None, "",
                "offline", "群聊", "外部", now, "-",
                room_id, 1, "",
            ),
        )
        row = self._db.query_one("SELECT * FROM channel_sessions WHERE id = ?", (sid,))
        return row_to_session(row) if row else None

    def mark_sessions_read_local(
        self, account_id: str, session_ids: list[str] | None = None
    ) -> int:
        """仅本地清零未读（不调 iPad）。

        session_ids 为 None → 清空当前账号全部会话未读；
        否则逐条 UPDATE。返回更新行数。
        """
        if session_ids is None:
            return self._db.execute(
                "UPDATE channel_sessions SET unread_count = 0, read_status = 'read' "
                "WHERE account_id = ?",
                (account_id,),
            )
        updated = 0
        for sid in session_ids:
            updated += self._db.execute(
                "UPDATE channel_sessions SET unread_count = 0, read_status = 'read' "
                "WHERE id = ? AND account_id = ?",
                (sid, account_id),
            )
        return updated

    def increment_session_unread(self, conversation_id: str, account_id: str) -> None:
        """回调收到新消息时，将对应会话未读 +1、标记 unread（P2-4）。

        conversation_id 即 iPad 会话标识；优先按 `remote_session_id` 命中本地会话，
        否则按 conversation_id 直接匹配（兼容 1:1 与群）。
        """
        sess = self._db.query_one(
            "SELECT id FROM channel_sessions WHERE account_id = ? AND remote_session_id = ?",
            (account_id, conversation_id),
        )
        final = sess["id"] if sess else conversation_id
        self._db.execute(
            "UPDATE channel_sessions SET unread_count = unread_count + 1, "
            "read_status = 'unread' WHERE id = ?",
            (final,),
        )


def row_to_group(row: dict) -> dict:
    """行 -> 群 DTO。"""
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "roomId": row["room_id"],
        "groupType": row["group_type"],
        "name": row["nickname"],
        "total": row["total"],
        "roomUrl": row["room_url"],
        "noticeContent": row["notice_content"],
        "createTime": row["create_time"],
        "updateTime": row["update_time"],
        "extra": _parse_json_field(row.get("extra_json"), {}),
    }


def row_to_group_member(row: dict) -> dict:
    """行 -> 群成员 DTO。"""
    return {
        "id": row["id"],
        "groupId": row["group_id"],
        "uin": row["uin"],
        "userId": row["user_id"],
        "nickname": row["nickname"],
        "realname": row["realname"],
        "avatar": row["avatar"],
        "roomNickname": row["room_nickname"],
        "sex": row["sex"],
        "mobile": row["mobile"],
        "joinTime": row["join_time"],
    }


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


"""运营SOP数据访问层（Repository）。

遵循现有模式：所有 SQL 集中于此，Router 层只调用 Repository 方法。
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from .database import DatabaseBackend


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _row_to_sop(row: dict) -> dict:
    """将 operation_sops 行映射为 DTO。"""
    nodes_raw = row.get("nodes_json", "[]") or "[]"
    try:
        nodes = json.loads(nodes_raw)
    except (json.JSONDecodeError, TypeError):
        nodes = []
    trigger_config_raw = row.get("trigger_config", "{}") or "{}"
    try:
        trigger_config = json.loads(trigger_config_raw)
    except (json.JSONDecodeError, TypeError):
        trigger_config = {}
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "channel": row.get("channel", ""),
        "enabled": bool(row["enabled"]),
        "status": row["status"],
        "trigger_type": row.get("trigger_type", ""),
        "trigger_config": trigger_config,
        "nodes": nodes,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class OperationSopRepository:
    """运营 SOP 仓储。"""

    def __init__(self, backend: DatabaseBackend) -> None:
        self._db = backend

    # ---- 列表 ----

    def list_all(
        self,
        type_: Optional[str] = None,
        enabled: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
    ) -> list[dict]:
        """查询 SOP 列表，支持筛选与排序。"""
        where: list[str] = ["1=1"]
        params: list = []

        if type_ and type_ != "全部":
            where.append("type = ?")
            params.append(type_)
        if enabled == "已启用":
            where.append("enabled = 1")
        elif enabled == "已停用":
            where.append("enabled = 0")
        if status == "运行中":
            where.append("status = 'running'")
        elif status == "未运行":
            where.append("status = 'stopped'")
        if search:
            where.append("name LIKE ?")
            params.append(f"%{search}%")

        sort_col = "created_at" if sort_by == "最近创建" else "updated_at"
        where_sql = " AND ".join(where)
        sql = f"SELECT * FROM operation_sops WHERE {where_sql} ORDER BY {sort_col} DESC, id"
        rows = self._db.query(sql, tuple(params))
        return [_row_to_sop(r) for r in rows]

    # ---- 详情 ----

    def get(self, sop_id: str) -> Optional[dict]:
        """获取单个 SOP（含完整 nodes_json）。"""
        row = self._db.query_one("SELECT * FROM operation_sops WHERE id = ?", (sop_id,))
        return _row_to_sop(row) if row else None

    # ---- 创建 ----

    def create(self, sop_id: str, name: str, type_: str, channel: str,
               trigger_type: str, trigger_config: dict, nodes: list) -> dict:
        """创建 SOP。"""
        trigger_config_json = json.dumps(trigger_config, ensure_ascii=False)
        nodes_json = json.dumps(nodes, ensure_ascii=False)
        self._db.execute(
            "INSERT INTO operation_sops(id, name, type, channel, enabled, status, "
            "trigger_type, trigger_config, nodes_json) "
            "VALUES (?, ?, ?, ?, 1, 'stopped', ?, ?, ?)",
            (sop_id, name, type_, channel, trigger_type, trigger_config_json, nodes_json),
        )
        return self.get(sop_id) or {
            "id": sop_id, "name": name, "type": type_, "channel": channel,
            "enabled": True, "status": "stopped",
            "trigger_type": trigger_type, "trigger_config": trigger_config,
            "nodes": nodes, "created_at": "", "updated_at": "",
        }

    # ---- 更新 ----

    def update(self, sop_id: str, fields: dict) -> Optional[dict]:
        """部分更新 SOP 字段。"""
        existing = self._db.query_one("SELECT * FROM operation_sops WHERE id = ?", (sop_id,))
        if existing is None:
            return None

        allowed = {"name", "type", "channel", "enabled", "status",
                    "trigger_type", "trigger_config", "nodes_json"}
        updates: list[str] = []
        params: list = []

        for key, val in fields.items():
            db_key = key
            if db_key == "enabled":
                db_key = "enabled"
                val = 1 if val else 0
            elif db_key == "nodes":
                db_key = "nodes_json"
                val = json.dumps(val, ensure_ascii=False)
            elif db_key == "trigger_config":
                db_key = "trigger_config"
                val = json.dumps(val, ensure_ascii=False)
            if db_key in allowed:
                updates.append(f"{db_key} = ?")
                params.append(val)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(sop_id)
            self._db.execute(
                f"UPDATE operation_sops SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )

        return self.get(sop_id)

    # ---- 删除 ----

    def delete(self, sop_id: str) -> bool:
        """删除 SOP，返回是否实际删除。"""
        rowcount = self._db.execute("DELETE FROM operation_sops WHERE id = ?", (sop_id,))
        return rowcount > 0

    # ---- 启停 ----

    def toggle(self, sop_id: str, enabled: bool) -> Optional[dict]:
        """切换启用状态。"""
        existing = self._db.query_one("SELECT * FROM operation_sops WHERE id = ?", (sop_id,))
        if existing is None:
            return None
        self._db.execute(
            "UPDATE operation_sops SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if enabled else 0, sop_id),
        )
        return self.get(sop_id)

    # ---- 运行记录 ----

    def list_records(self, sop_id: str) -> list[dict]:
        """查询 SOP 的运行记录列表（按运行时间倒序）。"""
        sql = (
            "SELECT id, sop_id, run_time, run_status, error_message, created_at "
            "FROM operation_sop_records "
            "WHERE sop_id = ? "
            "ORDER BY run_time DESC, id"
        )
        rows = self._db.query(sql, (sop_id,))
        return [dict(r) for r in rows]

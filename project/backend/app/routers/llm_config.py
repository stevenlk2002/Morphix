"""LLM 配置路由。

端点：
- GET  /api/llm-config           → 返回 primary + secondary 两条配置
- PUT  /api/llm-config/{id}      → 更新单条配置（id = 'primary' | 'secondary'）

使用 SQLite 数据库持久化存储，prepared statement 读写。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend

router = APIRouter(prefix="/llm-config", tags=["llm-config"])

# 响应字段名：DB 列 model_name 映射为前端期望的 model
_KEYS = ("id", "vendor", "model_name", "api_key", "api_base_url", "enabled", "updated_at")


def _row_to_dict(row: dict) -> dict:
    """将数据库行转换为前端友好的字典格式。"""
    return {
        "id": row["id"],
        "vendor": row["vendor"],
        "model": row["model_name"],
        "apiKey": row["api_key"],
        "apiBaseUrl": row["api_base_url"],
        "enabled": bool(row["enabled"]),
        "updatedAt": row["updated_at"],
    }


@router.get("")
def get_all_configs():
    """获取所有 LLM 模型配置。

    返回 { primary: {...}, secondary: {...} } 结构。
    """
    backend = get_backend()
    rows = backend.query(
        "SELECT id, vendor, model_name, api_key, api_base_url, enabled, updated_at "
        "FROM llm_model_configs ORDER BY id"
    )
    result: dict[str, dict] = {}
    for row in rows:
        key = _row_to_dict(row)
        # 不返回 apiKey 明文（脱敏：仅返回密文占位）
        key["apiKey"] = "••••••••" if row["api_key"] else ""
        result[row["id"]] = key
    return result


@router.put("/{config_id}")
def update_config(config_id: str, body: dict):
    """更新单条 LLM 模型配置。

    config_id: 'primary' 或 'secondary'
    请求体: { vendor, model, apiKey, apiBaseUrl, enabled }
    """
    if config_id not in ("primary", "secondary"):
        raise HTTPException(status_code=404, detail=f"未知配置 ID: {config_id}")

    backend = get_backend()

    # 查找现有记录
    existing = backend.query_one(
        "SELECT id FROM llm_model_configs WHERE id = ?", (config_id,)
    )
    if existing is None:
        raise HTTPException(status_code=404, detail=f"配置不存在: {config_id}")

    # 从请求体中提取字段
    vendor = str(body.get("vendor", ""))
    model_name = str(body.get("model", ""))
    api_key = str(body.get("apiKey", ""))
    api_base_url = str(body.get("apiBaseUrl", ""))
    enabled = 1 if body.get("enabled", False) else 0

    backend.execute(
        "UPDATE llm_model_configs SET vendor=?, model_name=?, api_key=?, api_base_url=?, enabled=?, updated_at=datetime('now') "
        "WHERE id=?",
        (vendor, model_name, api_key, api_base_url, enabled, config_id),
    )

    # 回读更新后的记录
    row = backend.query_one(
        "SELECT id, vendor, model_name, api_key, api_base_url, enabled, updated_at "
        "FROM llm_model_configs WHERE id = ?",
        (config_id,),
    )
    if row is None:
        raise HTTPException(status_code=500, detail="更新后读取失败")

    return _row_to_dict(row)

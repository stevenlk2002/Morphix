"""LLM 配置中心凭证解析（内部服务，不做脱敏）。

编排引擎的 agent / aiChat 节点在运行时只持有 `model_id` 引用，
本模块负责把 `model_id` 解析为真实的 `api_key + api_base_url + model_name`，
供 `contract.services.agents` 构造 OpenAI 兼容客户端使用。

注意：这里返回的是明文 api_key，仅限服务端内部使用，绝不暴露给前端。
前端如需展示可选模型列表，请走 `/api/llm-config/registry`（脱敏列表）。
"""
from __future__ import annotations

from app.database import get_backend


def resolve_llm_credentials(model_id: str) -> dict | None:
    """按 model_id 解析模型凭证；不存在返回 None。

    返回字段：id / vendor / model_name / api_key / api_base_url / enabled（明文）。
    """
    backend = get_backend()
    row = backend.query_one(
        "SELECT id, vendor, model_name, api_key, api_base_url, enabled "
        "FROM llm_model_configs WHERE id = ?",
        (model_id,),
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "vendor": row["vendor"],
        "model_name": row["model_name"],
        "api_key": row["api_key"],
        "api_base_url": row["api_base_url"],
        "enabled": bool(row["enabled"]),
    }


def list_model_registry() -> list[dict]:
    """返回模型注册表列表（不含 apiKey），供前端编排节点引用选择。"""
    backend = get_backend()
    rows = backend.query(
        "SELECT id, vendor, model_name, enabled FROM llm_model_configs ORDER BY id"
    )
    return [
        {
            "id": r["id"],
            "vendor": r["vendor"],
            "model": r["model_name"],
            "enabled": bool(r["enabled"]),
        }
        for r in rows
    ]

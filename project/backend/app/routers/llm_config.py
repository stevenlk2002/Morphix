"""LLM 配置路由。

端点：
- GET  /api/llm-config           → 返回 primary + secondary 两条配置
- PUT  /api/llm-config/{id}      → 更新单条配置（id = 'primary' | 'secondary'）
- POST /api/llm-config/{id}/test → 用数据库中存储的真实密钥测试连接

使用 SQLite 数据库持久化存储，prepared statement 读写。
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

import httpx

from ..database import get_backend
from ..llm_registry import list_model_registry, resolve_llm_credentials

logger = logging.getLogger(__name__)

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


@router.get("/registry")
def get_registry():
    """返回模型注册表列表（不含 apiKey），供前端编排节点引用选择。

    与 GET / 的区别：本端点返回数组、不脱敏 apiKey 之外的敏感字段，
    且结构更便于前端下拉选择器消费（id + vendor + model + enabled）。
    """
    return list_model_registry()


@router.put("/{config_id}")
def update_config(config_id: str, body: dict):
    """更新单条 LLM 模型配置。

    config_id: 'primary' 或 'secondary'
    请求体: { vendor, model, apiKey, apiBaseUrl, enabled }
    """
    if config_id not in ("primary", "secondary"):
        raise HTTPException(status_code=404, detail=f"未知配置 ID: {config_id}")

    backend = get_backend()

    # 查找现有记录（同时取出原 api_key 用于兜底）
    existing = backend.query_one(
        "SELECT id, api_key FROM llm_model_configs WHERE id = ?", (config_id,)
    )
    if existing is None:
        raise HTTPException(status_code=404, detail=f"配置不存在: {config_id}")

    # 从请求体中提取字段
    vendor = str(body.get("vendor", ""))
    model_name = str(body.get("model", ""))
    incoming_key = body.get("apiKey")  # None 表示前端未传该字段
    api_base_url = str(body.get("apiBaseUrl", ""))
    enabled = 1 if body.get("enabled", False) else 0

    # 防御：GET 接口向客户端返回脱敏占位符 "••••••••"。
    # 若前端把该占位符原样回传、或未传 apiKey 字段，则保留数据库中原存密钥，
    # 避免把「显示值」当成「真值」写回、覆盖掉真实 Key（曾因此导致密钥被清空）。
    # 仅当客户端明确传了一个非占位符的真实字符串时才更新 api_key。
    if incoming_key is None or incoming_key == "••••••••":
        api_key = existing["api_key"] or ""
    else:
        api_key = str(incoming_key)

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


@router.post("/{config_id}/test")
def test_connection(config_id: str) -> dict:
    """用数据库中存储的真实密钥测试 LLM 连接。

    前端在 apiKeyMasked 状态下（GET 返回脱敏占位符后）本地没有真实密钥，
    无法自行发起测试。本端点从 DB 读取明文 key，发一个轻量 chat completion
    请求验证连通性。

    Returns:
        { "ok": bool, "message": str, "latency_ms": float|None }
    """
    import time

    if config_id not in ("primary", "secondary"):
        raise HTTPException(status_code=404, detail=f"未知配置 ID: {config_id}")

    backend = get_backend()
    row = backend.query_one(
        "SELECT id, vendor, model_name, api_key, api_base_url FROM llm_model_configs WHERE id = ?",
        (config_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"配置不存在: {config_id}")

    api_key = row["api_key"]
    if not api_key or not api_key.strip():
        return {"ok": False, "message": "未配置 API Key，请先填写密钥", "latency_ms": None}

    # 解析凭证（复用 registry 的厂商→base_url 映射）
    try:
        profile = resolve_llm_credentials(config_id)
    except Exception as e:
        return {"ok": False, "message": f"凭证解析失败: {e}", "latency_ms": None}

    base_url = (profile.get("base_url") or row["api_base_url"] or "").rstrip("/")
    model = row["model_name"] or profile.get("model", "")

    if not base_url:
        return {"ok": False, "message": "未配置 API 地址（base_url）", "latency_ms": None}
    if not model:
        return {"ok": False, "message": "未选择模型", "latency_ms": None}

    # 拼接 OpenAI 兼容 /v1/chat/completions
    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }

    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, headers=headers, json=payload)
            latency = round((time.monotonic() - t0) * 1000)
            if resp.status_code == 200:
                # 尝试读取 model 字段确认是有效 LLM 响应
                data = resp.json()
                reply_model = data.get("model", "")
                logger.info("LLM test OK: config=%s model=%s latency=%dms", config_id, reply_model, latency)
                return {
                    "ok": True,
                    "message": f"连接成功（模型: {reply_model}，延迟: {latency}ms）",
                    "latency_ms": latency,
                }
            else:
                err_text = resp.text[:200]
                logger.warning(
                    "LLM test FAIL: config=%s status=%d body=%s",
                    config_id, resp.status_code, err_text,
                )
                return {
                    "ok": False,
                    "message": f"请求失败 ({resp.status_code}): {err_text}",
                    "latency_ms": latency,
                }
    except httpx.TimeoutException:
        latency = round((time.monotonic() - t0) * 1000)
        return {"ok": False, "message": f"连接超时（>{latency}ms），请检查网络或 API 地址", "latency_ms": latency}
    except Exception as e:
        latency = round((time.monotonic() - t0) * 1000)
        logger.error("LLM test ERROR: config=%s %s: %s", config_id, type(e).__name__, e)
        return {"ok": False, "message": f"连接异常: {type(e).__name__}: {e}", "latency_ms": latency}

"""LLM 配置 API 验收测试。

覆盖端点：
- GET  /api/llm-config          → 返回 primary + secondary
- PUT  /api/llm-config/{id}     → 更新单条配置

测试前后重置 seed 数据，确保测试隔离、可重复。
"""
import pytest
from fastapi.testclient import TestClient

from app.database import get_backend
from app.main import app

_SEED_PRIMARY = ("primary", "OpenAI", "GPT-4o", "sk-orchestrator-7f3a9c2e1b4d", "https://api.openai.com/v1", 1)
_SEED_SECONDARY = ("secondary", "Anthropic", "Claude 3.5 Sonnet", "", "", 0)


def _reset_seeds():
    """删除已有数据并重新写入种子数据，确保每次测试起点一致。"""
    backend = get_backend()
    backend.execute("DELETE FROM llm_model_configs")
    backend.execute(
        "INSERT INTO llm_model_configs(id, vendor, model_name, api_key, api_base_url, enabled) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        _SEED_PRIMARY,
    )
    backend.execute(
        "INSERT INTO llm_model_configs(id, vendor, model_name, api_key, api_base_url, enabled) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        _SEED_SECONDARY,
    )


client = TestClient(app)


def test_get_configs_returns_both():
    """GET /api/llm-config → 返回 primary 与 secondary。"""
    _reset_seeds()
    resp = client.get("/api/llm-config")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "primary" in data
    assert "secondary" in data
    assert data["primary"]["vendor"] == "OpenAI"
    assert data["primary"]["model"] == "GPT-4o"
    assert data["primary"]["enabled"] is True
    assert data["secondary"]["vendor"] == "Anthropic"
    assert data["secondary"]["model"] == "Claude 3.5 Sonnet"
    assert data["secondary"]["enabled"] is False


def test_get_configs_masks_api_key():
    """GET 返回的 apiKey 已脱敏（不为原始明文）。"""
    _reset_seeds()
    resp = client.get("/api/llm-config")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    primary_key = data["primary"]["apiKey"]
    assert primary_key != "sk-orchestrator-7f3a9c2e1b4d"
    assert "•••" in primary_key
    assert data["secondary"]["apiKey"] == ""


def test_update_primary():
    """PUT /api/llm-config/primary → 更新主模型后读取验证。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={
            "vendor": "Deepseek",
            "model": "Deepseek-V4-Pro",
            "apiKey": "sk-test",
            "apiBaseUrl": "https://api.deepseek.com/v1",
            "enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["vendor"] == "Deepseek"
    assert data["model"] == "Deepseek-V4-Pro"
    assert data["apiBaseUrl"] == "https://api.deepseek.com/v1"
    assert data["enabled"] is True

    # 再次 GET 验证持久化
    resp2 = client.get("/api/llm-config")
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["primary"]["vendor"] == "Deepseek"
    assert resp2.json()["primary"]["model"] == "Deepseek-V4-Pro"


def test_update_secondary():
    """PUT /api/llm-config/secondary → 更新副模型后读取验证。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/secondary",
        json={
            "vendor": "Anthropic",
            "model": "Claude 3 Opus",
            "apiKey": "sk-new-key",
            "apiBaseUrl": "",
            "enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["vendor"] == "Anthropic"
    assert data["model"] == "Claude 3 Opus"
    assert data["enabled"] is True

    resp2 = client.get("/api/llm-config")
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["secondary"]["model"] == "Claude 3 Opus"


def test_update_nonexistent_404():
    """PUT /api/llm-config/nonexistent → 404。"""
    resp = client.put(
        "/api/llm-config/nonexistent",
        json={"vendor": "Test", "model": "Test", "apiKey": ""},
    )
    assert resp.status_code == 404, resp.text


def test_update_empty_api_key():
    """PUT 时 apiKey 为空字符串应可成功保存。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={
            "vendor": "OpenAI",
            "model": "GPT-4o",
            "apiKey": "",
            "apiBaseUrl": "https://api.openai.com/v1",
            "enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text


def test_update_invalid_vendor():
    """PUT 时 vendor 为空字符串仍可成功（服务端不做业务校验）。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={
            "vendor": "",
            "model": "GPT-4o",
            "apiKey": "sk-test",
            "apiBaseUrl": "",
            "enabled": False,
        },
    )
    assert resp.status_code == 200, resp.text

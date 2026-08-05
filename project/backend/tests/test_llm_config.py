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


def test_registry_returns_no_api_key():
    """GET /api/llm-config/registry → 返回数组且不含明文 apiKey。"""
    _reset_seeds()
    resp = client.get("/api/llm-config/registry")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    ids = {row["id"] for row in data}
    assert "primary" in ids and "secondary" in ids
    # 安全：注册表绝不泄露 api_key
    assert all("api_key" not in row and "apiKey" not in row for row in data)
    primary = next(r for r in data if r["id"] == "primary")
    assert primary["vendor"] == "OpenAI" and primary["model"] == "GPT-4o"


def test_resolve_llm_credentials_returns_raw_key():
    """resolve_llm_credentials('primary') 返回明文 api_key（内部服务）。"""
    _reset_seeds()
    from app.llm_registry import resolve_llm_credentials

    creds = resolve_llm_credentials("primary")
    assert creds is not None
    assert creds["api_key"] == "sk-orchestrator-7f3a9c2e1b4d"
    assert creds["api_base_url"] == "https://api.openai.com/v1"
    assert creds["model_name"] == "GPT-4o"
    # 未知 id → None
    assert resolve_llm_credentials("does-not-exist") is None


def test_invoke_agent_graceful_fallback_offline():
    """invoke_agent(model_profile='primary') 离线环境下回落且不抛异常。"""
    _reset_seeds()
    from app.contract.services import agents as agent_svc

    result = agent_svc.invoke_agent(
        run_id="r1",
        node_execution_id="ne1",
        agent_type="qa",
        model_profile="primary",
        structured_input={"message": "你好"},
    )
    assert "structuredOutput" in result
    assert "reply" in result["structuredOutput"]
    assert isinstance(result["structuredOutput"]["reply"], str)
    # 离线回落到 stub（真实调用不可达），结构仍正确
    assert result["structuredOutput"]["agentType"] == "qa"


def test_invoke_agent_stub_profile_short_circuits():
    """model_profile 以 stub 开头时直接走确定性 stub，不触碰凭证解析。"""
    from app.contract.services import agents as agent_svc

    result = agent_svc.invoke_agent(
        run_id="r2",
        node_execution_id="ne2",
        agent_type="summarizer",
        model_profile="stub-summarizer",
        structured_input={"message": "x"},
    )
    assert result["structuredOutput"]["reply"] == "用户咨询了报价，意向明确，待发送方案。"


def test_put_masked_placeholder_keeps_existing_key():
    """回归：PUT 回传脱敏占位符 '••••••••' 时，不得覆盖真实密钥。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={"vendor": "OpenAI", "model": "GPT-4o",
              "apiKey": "••••••••", "apiBaseUrl": "https://api.openai.com/v1", "enabled": True},
    )
    assert resp.status_code == 200, resp.text
    # 数据库里的真实密钥应被原样保留
    backend = get_backend()
    row = backend.query_one(
        "SELECT api_key FROM llm_model_configs WHERE id='primary'"
    )
    assert row["api_key"] == "sk-orchestrator-7f3a9c2e1b4d"


def test_put_omit_api_key_keeps_existing():
    """PUT 请求体不含 apiKey 字段时，保留原存密钥。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={"vendor": "OpenAI", "model": "GPT-4o",
              "apiBaseUrl": "https://api.openai.com/v1", "enabled": True},
    )
    assert resp.status_code == 200, resp.text
    backend = get_backend()
    row = backend.query_one(
        "SELECT api_key FROM llm_model_configs WHERE id='primary'"
    )
    assert row["api_key"] == "sk-orchestrator-7f3a9c2e1b4d"


def test_put_new_real_key_updates():
    """PUT 传真实新密钥时正常更新。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={"vendor": "OpenAI", "model": "GPT-4o",
              "apiKey": "sk-new-real-xyz", "apiBaseUrl": "https://api.openai.com/v1", "enabled": True},
    )
    assert resp.status_code == 200, resp.text
    backend = get_backend()
    row = backend.query_one(
        "SELECT api_key FROM llm_model_configs WHERE id='primary'"
    )
    assert row["api_key"] == "sk-new-real-xyz"


def test_put_explicit_empty_clears_key():
    """PUT 显式传空串 apiKey 时，允许清除密钥（区别于「省略字段」）。"""
    _reset_seeds()
    resp = client.put(
        "/api/llm-config/primary",
        json={"vendor": "OpenAI", "model": "GPT-4o",
              "apiKey": "", "apiBaseUrl": "https://api.openai.com/v1", "enabled": True},
    )
    assert resp.status_code == 200, resp.text
    backend = get_backend()
    row = backend.query_one(
        "SELECT api_key FROM llm_model_configs WHERE id='primary'"
    )
    assert row["api_key"] == ""

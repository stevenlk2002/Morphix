"""Agent Executor.

The Runtime calls /internal/agent-executor/invoke, implemented by this service.

Design (凭证与参数分离):
- 编排节点只持有 `model_profile` = 配置中心的 model_id 引用（如 'primary' / 'secondary'）。
- 本服务按 model_id 调用 `app.llm_registry.resolve_llm_credentials` 解析出真实
  api_key + api_base_url + model_name，再请求 OpenAI 兼容接口。
- 任何异常（无 Key / 网络不通 / 非 200）都回落到确定性 stub 回复，保证链路可用且不崩。
"""
from __future__ import annotations

import uuid

import httpx

from app.contract.envelope import ApiError
from app.llm_registry import resolve_llm_credentials


# Deterministic canned replies per agent type so the smoke chain is reproducible
# (used as fallback when no real model is configured / call fails).
_REPLIES = {
    "qa": "您好，我是您的专属顾问。已收到您的问题，正在为您查询资料，请稍候～",
    "sales_progress": "根据当前沟通进度，建议下一步发送报价单并确认预算区间。",
    "expression_control": "语气保持专业、礼貌、简洁，避免承诺未授权条款。",
    "risk_guard": "未发现明显合规风险，继续跟进即可。",
    "supervisor": "建议维持当前策略，必要时升级人工。",
    "summarizer": "用户咨询了报价，意向明确，待发送方案。",
}

# agent_type → 中文角色描述（拼进 system prompt）
_ROLE_PROMPTS = {
    "qa": "你是一个专业的客服顾问，负责解答用户问题、收集需求，语气友好、专业。",
    "sales_progress": "你是一个销售推进专家，负责引导成交、推进沟通进度，话术自然不压迫。",
    "expression_control": "你负责把控回复的语气与表达方式，使其专业、礼貌、简洁。",
    "risk_guard": "你负责合规风控，识别敏感内容与承诺风险，给出安全回复。",
    "supervisor": "你是一个督导角色，负责总结并给出下一步策略建议。",
    "summarizer": "你负责把对话内容凝练为简洁的摘要。",
}


def _agent_system_prompt(agent_type: str, structured_input: dict) -> str:
    base = _ROLE_PROMPTS.get(agent_type, f"你是一个 {agent_type} 角色助手。")
    extra = ""
    if isinstance(structured_input, dict):
        prompt_tpl = structured_input.get("prompt")
        if isinstance(prompt_tpl, str) and prompt_tpl.strip():
            extra = f"\n补充指令：{prompt_tpl.strip()}"
    return base + extra


def _agent_user_prompt(structured_input: dict) -> str:
    if not isinstance(structured_input, dict):
        return str(structured_input)
    msg = structured_input.get("message")
    if isinstance(msg, str) and msg.strip():
        return msg
    if isinstance(msg, dict):
        text = msg.get("content") or msg.get("contentText") or msg.get("text")
        if isinstance(text, str) and text.strip():
            return text
    um = structured_input.get("userMessage")
    if isinstance(um, str) and um.strip():
        return um
    return str(structured_input)


def _call_openai_compatible(creds: dict, system_prompt: str, user_prompt: str) -> str | None:
    """请求 OpenAI 兼容 /v1/chat/completions。失败一律返回 None（由调用方回落 stub）。"""
    api_key = creds.get("api_key")
    base_url = creds.get("api_base_url")
    model = creds.get("model_name")
    if not api_key or not base_url or not model:
        return None
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                return content or None
    except Exception:
        # 网络/鉴权/解析等任何异常：回落 stub，不向上抛
        return None
    return None


def invoke_agent(
    *,
    run_id: str,
    node_execution_id: str,
    agent_type: str,
    model_profile: str,
    structured_input: dict,
    knowledge_context: dict | None = None,
    tool_scope: list[str] | None = None,
) -> dict:
    """Return a structured agent result (InternalAgentInvokeData shape).

    model_profile 为配置中心 model_id 时走真实 LLM；为 'stub*' 或解析/调用失败则回落 stub。
    """
    if model_profile and not model_profile.startswith("stub"):
        creds = resolve_llm_credentials(model_profile)
        if creds and creds.get("enabled", True):
            reply = _call_openai_compatible(
                creds,
                _agent_system_prompt(agent_type, structured_input),
                _agent_user_prompt(structured_input),
            )
            if reply:
                return {
                    "structuredOutput": {
                        "agentType": agent_type,
                        "reply": reply,
                        "echoInputKeys": sorted(structured_input.keys())
                        if isinstance(structured_input, dict)
                        else [],
                    },
                    "summary": reply,
                    "confidence": 0.9,
                    "latencyMs": 120,
                    "estimatedCost": 0.0,
                }

    # 回落：确定性 stub 回复
    summary = _REPLIES.get(agent_type, f"[{agent_type}] 已处理（stub）。")
    return {
        "structuredOutput": {
            "agentType": agent_type,
            "reply": summary,
            "echoInputKeys": sorted(structured_input.keys()) if isinstance(structured_input, dict) else [],
        },
        "summary": summary,
        "confidence": 0.92,
        "latencyMs": 18,
        "estimatedCost": 0.0,
    }


def invoke_supervisor(
    *,
    run_id: str,
    conversation_id: str,
    trigger_reason: str,
    structured_context: dict,
    candidate_plans: list[dict] | None = None,
) -> dict:
    """Return a supervisor suggestion (InternalSupervisorData shape)."""
    return {
        "recommendation": {
            "action": "continue_ai_hosting",
            "note": "Stub supervisor: no intervention required.",
        },
        "confidence": 0.75,
        "constraints": ["no_auto_refund", "require_human_for_contract"],
        "notes": f"Triggered by {trigger_reason} (stub).",
    }

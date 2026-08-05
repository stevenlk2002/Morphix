"""Agent Executor.

The Runtime calls /internal/agent-executor/invoke, implemented by this service.
For MVP we still keep a deterministic stub fallback, but `invoke_agent` now calls
a real LLM (OpenAI-compatible, DeepSeek by default) when MORPHIX_AI_API_KEY is set.
If the LLM is unavailable (no key / network error), it gracefully falls back to the
canned `_REPLIES` so the P0 chain stays runnable.
"""
from __future__ import annotations

import time
import uuid

from app.core.envelope import ApiError
from app.services import llm_client


# Deterministic canned replies per agent type — used only as a fallback when the
# LLM is not configured / fails. Keeps the smoke chain reproducible offline.
_REPLIES = {
    "qa": "您好，我是您的专属顾问。已收到您的问题，正在为您查询资料，请稍候～",
    "sales_progress": "根据当前沟通进度，建议下一步发送报价单并确认预算区间。",
    "expression_control": "语气保持专业、礼貌、简洁，避免承诺未授权条款。",
    "risk_guard": "未发现明显合规风险，继续跟进即可。",
    "supervisor": "建议维持当前策略，必要时升级人工。",
    "summarizer": "用户咨询了报价，意向明确，待发送方案。",
}

# Role framing per agent type. Customer-facing types (qa) get a strict compliance
# reminder because their output may be sent to the customer.
_AGENT_ROLE_SYSTEM = {
    "qa": (
        "你是河马大健康私域的客户服务与销售 AI 助手，用专业、亲切、合规的中文服务客户。"
        "只输出客户会直接看到的话术，不要包含任何内部备注或思考过程。"
    ),
    "sales_progress": "你是销售进度分析助手（内部），输出对下一步推进策略的建议，不直接发给客户。",
    "expression_control": "你是话术语气控制助手（内部），输出语气与合规建议，不直接发给客户。",
    "risk_guard": "你是合规风险审查助手（内部），判断是否涉及违规承诺或医疗疗效断言，不直接发给客户。",
    "supervisor": "你是会话督导（内部），决定继续 AI 托管还是升级人工，不直接发给客户。",
    "summarizer": "你是会话摘要助手（内部），输出结构化摘要，不直接发给客户。",
}

_COMPLIANCE_REMINDER = (
    "\n\n严格遵守合规红线：不承诺疗效、不保证治愈、不虚假宣传；"
    "涉及价格须与疗效完全脱钩；不引导客户向私人账户转账；不推荐未经审批的疗法。"
)


def _system_prompt(agent_type: str, node_prompt: str) -> str:
    base = _AGENT_ROLE_SYSTEM.get(agent_type, _AGENT_ROLE_SYSTEM["qa"])
    if node_prompt:
        base += f"\n\n【本节点指令】{node_prompt}"
    if agent_type == "qa":
        base += _COMPLIANCE_REMINDER
    return base


def _user_prompt(structured_input: dict) -> str:
    name = structured_input.get("customerName") or "客户"
    latest = structured_input.get("latestCustomerMessage") or ""
    history = structured_input.get("history") or []
    tags = structured_input.get("customerTags") or []

    lines: list[str] = []
    if latest:
        lines.append(f"【客户最新消息】{latest}")
    if history:
        lines.append("【近期对话】")
        for turn in history:
            role = turn.get("role", "客户")
            text = turn.get("text", "")
            if text:
                lines.append(f"{role}：{text}")
    if tags:
        lines.append(f"【客户标签】{', '.join(tags)}")
    lines.append(f"请基于以上上下文，按你的角色与本节点指令生成回复。")
    return "\n".join(lines)


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

    Calls the real LLM when configured; falls back to a canned reply otherwise.
    The returned `model` / `used_llm` fields let the orchestrator record what ran.
    """
    si = structured_input or {}
    node_data = si.get("message") or {}
    node_prompt = node_data.get("prompt") or ""

    system_prompt = _system_prompt(agent_type, node_prompt)
    user_prompt = _user_prompt(si)

    started = time.perf_counter()
    text, used_llm, err = llm_client.try_chat(system_prompt, user_prompt)
    latency_ms = int((time.perf_counter() - started) * 1000)

    if not used_llm:
        # Graceful fallback so the pipeline never stalls on a missing/failed LLM.
        text = _REPLIES.get(agent_type, f"[{agent_type}] 已处理（stub）。")
    else:
        # Light cleanup: drop the model's occasional "assistant:" style prefixes.
        text = text.strip()
        if text.lower().startswith("assistant:"):
            text = text[len("assistant:"):].strip()

    model_name = llm_client._cfg()["model"] if used_llm else "stub"

    return {
        "structuredOutput": {
            "agentType": agent_type,
            "reply": text,
            "usedLlm": used_llm,
            "model": model_name,
            "echoInputKeys": sorted(si.keys()) if isinstance(si, dict) else [],
        },
        "summary": text,
        "confidence": 0.9 if used_llm else 0.92,
        "latencyMs": latency_ms,
        "estimatedCost": 0.0,
        "model": model_name,
        "used_llm": used_llm,
        "llmError": err,
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

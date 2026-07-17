"""Agent Executor stub (MVP).

The Runtime calls /internal/agent-executor/invoke, implemented by this service.
For the MVP we return deterministic mock output; the real multi-Agent LLM call
is a TODO. This keeps the P0 chain runnable without external model access.
"""
from __future__ import annotations

import uuid

from app.core.envelope import ApiError


# Deterministic canned replies per agent type so the smoke chain is reproducible.
_REPLIES = {
    "qa": "您好，我是您的专属顾问。已收到您的问题，正在为您查询资料，请稍候～",
    "sales_progress": "根据当前沟通进度，建议下一步发送报价单并确认预算区间。",
    "expression_control": "语气保持专业、礼貌、简洁，避免承诺未授权条款。",
    "risk_guard": "未发现明显合规风险，继续跟进即可。",
    "supervisor": "建议维持当前策略，必要时升级人工。",
    "summarizer": "用户咨询了报价，意向明确，待发送方案。",
}


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
    """Return a structured agent result (InternalAgentInvokeData shape)."""
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

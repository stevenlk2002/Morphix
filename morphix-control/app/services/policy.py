"""Policy Router stub (MVP).

In production the Orchestrator calls /internal/policy-router/evaluate, which is
implemented by this service. For the MVP we use deterministic rule-based routing
instead of an LLM, so the inbound orchestration can call this service directly
without an HTTP round-trip to itself.

TODO: replace the rule stub with the real Policy Router (bot_selection /
workflow_selection / interrupt / handoff / model_profile / risk_block /
supervisor_gate) backed by the multi-Agent LLM.
"""
from __future__ import annotations

import uuid

from app.core.envelope import ApiError
from app.models import WorkflowVersion


def _default_model_profile(agent_type: str) -> str:
    # Deterministic mapping so tests are stable.
    return {
        "qa": "stub-qa",
        "sales_progress": "stub-sales",
        "expression_control": "stub-expression",
        "risk_guard": "stub-risk",
        "supervisor": "stub-supervisor",
        "summarizer": "stub-summarizer",
    }.get(agent_type, "stub")


def evaluate_policy(
    *,
    project_id: str,
    conversation_id: str,
    session_runtime_id: str,
    event_type: str,
    event_payload: dict,
    context: dict,
) -> dict:
    """Return a structured routing decision (InternalPolicyEvaluateData shape)."""
    allowed_agent_set = ["qa", "sales_progress", "expression_control", "risk_guard", "summarizer"]
    handoff_decision = "stay_ai"
    reason_codes: list[str] = ["rule:default_ai_hosting"]

    # Simple risk heuristic: profanity / escalation keywords push toward human handoff.
    text = ""
    msg = event_payload.get("message") if isinstance(event_payload, dict) else None
    if isinstance(msg, dict):
        text = (msg.get("contentText") or "").lower()
    risk_signals = ["投诉", "举报", "起诉", "退款", "差评", "人工", "骂"]
    if any(s in text for s in risk_signals):
        handoff_decision = "suggest_human"
        allowed_agent_set = ["risk_guard"]
        reason_codes = ["rule:risk_escalation_detected"]

    # Choose bot / workflow from context if provided, otherwise fall back to published default.
    bot_selection = context.get("botId") or "bot_default"
    workflow_selection = context.get("workflowVersionId") or "wf_default"

    decision = {
        "botSelection": bot_selection,
        "workflowVersionSelection": workflow_selection,
        "allowedAgentSet": allowed_agent_set,
        "modelProfile": _default_model_profile(allowed_agent_set[0]) if allowed_agent_set else "stub",
        "interruptDecision": "DROP_NEW",
        "handoffDecision": handoff_decision,
        "supervisorNeeded": handoff_decision == "force_human",
        "reasonCodes": reason_codes,
    }
    return decision


def publish_policy_decision(
    db,
    *,
    project_id: str | None,
    conversation_id: str | None,
    run_id: str | None,
    decision_type: str,
    decision: str,
    reason_codes: list[str] | None = None,
    model_profile: str | None = None,
):
    """Persist a PolicyDecision row for auditability."""
    from app.models import PolicyDecision

    rec = PolicyDecision(
        id=f"pol_{uuid.uuid4().hex}",
        project_id=project_id,
        conversation_id=conversation_id,
        run_id=run_id,
        decision_type=decision_type,
        decision=decision,
        reason_codes=reason_codes or [],
        model_profile=model_profile,
    )
    db.add(rec)
    db.flush()
    return rec

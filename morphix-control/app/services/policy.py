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


# --- Compliance gate (A8 守门) -------------------------------------------------
# Deterministic rule-based check of the SOP's B1-B8 red lines.
#
# Severity model (mirrors the SOP "BLOCK 级 / REWRITE 级" contract):
#   - BLOCK : hard red line. Any BLOCK hit forces allow_send=False (engine stops
#             before the send node). These are unambiguous violations a real
#             compliance router would never let through.
#   - WARN  : soft/advisory. Allowed to send in the MVP, but flagged so a real
#             engine could rewrite. Covers (a) neutral science-risk reminders
#             (e.g. "症状会越拖越重" used as 科普, not 恐吓), and (b) a keyword
#             that only appears inside a *negation / rejection* context
#             (e.g. "我们不保证有效", "任何声称100%的说法都不严谨").
#
# B8 (price/dosage) is context-aware: ONLY blocks when a price/course number is
# bundled with an efficacy promise ("一个疗程保证见效仅XX元"). A pure commercial
# price disclosure ("原价1280 优惠598 定金48 货到付款550") is WARN, not BLOCK.
#
# B7 (medical identity) is denial-aware: self-disclosure like "我不是医生 /
# 健康顾问" is permitted; only impersonating a clinic/doctor blocks.
_COMPLIANCE_RED_LINES: list[tuple[str, list[str], str]] = [
    # (code, keywords, severity)  severity ∈ {"BLOCK","WARN"}
    ("B1", ["治好", "根治", "彻底清除", "从根本上解决", "无效退款", "保证有效", "一定能好", "包治", "包好", "保疗效"], "BLOCK"),
    ("B2", ["久鸣必聋", "久聋必呆", "会痴呆", "会脑梗", "会失聪", "一定会耳聋"], "BLOCK"),
    ("B2", ["越拖越严重", "越来越严重", "会耳聋", "造成耳聋", "拖延加重"], "WARN"),
    ("B3", ["康复人数", "开口率提升至", "聊天记录显示", "患者原话", "统计数据表明"], "BLOCK"),
    ("B4", ["肾精不足", "气血瘀堵", "肝火旺", "您属于", "您这是"], "BLOCK"),
    ("B5", ["100%", "绝对", "唯一", "国家级", "权威认证"], "BLOCK"),
    ("B5", ["最好", "第一"], "WARN"),
    ("B6", ["名额", "倒计时", "限时优惠", "抓紧", "马上抢", "仅剩"], "BLOCK"),
    ("B7", ["大夫", "医疗机构", "我院", "本诊所", "本院"], "BLOCK"),
]
# B7 "医生" is denial-aware (see _b7_skip).
_B7_KEYWORD = "医生"
_B7_DENIAL_MARKERS = ["不是医生", "非医生", "不是执业医师", "健康顾问", "不诊断", "不开处方", "不判断病因"]
# Negation / rejection markers: if a BLOCK keyword only appears inside a
# negated or quoted-rejection context, downgrade to WARN.
_NEG_MARKERS = ["不", "非", "无", "没", "谨慎", "严谨", "所谓", "切勿", "无法", "不该"]
# B8: price / dosage / course numbers (regex).
_COMPLIANCE_B8_PATTERNS = [
    __import__("re").compile(r"[¥￥]\s?\d+"),
    __import__("re").compile(r"\d+\s*(?:盒|疗程|天|粒|mg|ML|毫升|片)"),
    __import__("re").compile(r"\d+\s*元"),
]
# Efficacy words that, when bundled with a price number, make B8 a BLOCK.
_B8_EFFICACY = ["治好", "根治", "有效", "改善", "康复", "见效", "包好", "保证", "疗程包"]


def _negated(text: str, keyword: str) -> bool:
    idx = text.find(keyword)
    if idx < 0:
        return False
    window = text[max(0, idx - 8):idx]
    return any(m in window for m in _NEG_MARKERS)


def _b7_skip(text: str) -> bool:
    return any(m in text for m in _B7_DENIAL_MARKERS)


def evaluate_compliance(
    *,
    text: str,
    project_id: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Return a structured A8 verdict for the given draft text.

    Shape: {verdict, allow_send, severity, violations[], reason_codes[]}.
      - severity: "BLOCK" | "WARN" | "PASS"
      - verdict:  "BLOCK" if any BLOCK-level hit, else "PASS"  (backward compatible)
      - allow_send: False exactly when severity == "BLOCK"
    """
    if not text:
        return {
            "verdict": "PASS",
            "allow_send": True,
            "severity": "PASS",
            "violations": [],
            "reason_codes": ["rule:compliance_clean"],
        }
    violations: list[dict] = []
    reason_codes: list[str] = []

    b7_skip = _b7_skip(text)

    for code, keywords, severity in _COMPLIANCE_RED_LINES:
        for kw in keywords:
            if kw not in text:
                continue
            if code == "B7" and (kw == _B7_KEYWORD) and b7_skip:
                continue  # self-disclosure, not impersonation
            level = severity
            # negation-aware downgrade for BLOCK keywords
            if severity == "BLOCK" and _negated(text, kw):
                level = "WARN"
            violations.append({"level": level, "code": code, "span": kw})
            reason_codes.append(f"rule:compliance_{code}_{level.lower()}")
            break  # one span per code is enough

    # B8 price/dosage, context-aware
    for pat in _COMPLIANCE_B8_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        eff_bundled = any(k in text for k in _B8_EFFICACY)
        if eff_bundled:
            violations.append({"level": "BLOCK", "code": "B8", "span": m.group(0)})
            reason_codes.append("rule:compliance_B8_block")
        else:
            violations.append({"level": "WARN", "code": "B8", "span": m.group(0)})
            reason_codes.append("rule:compliance_B8_warn")
        break

    has_block = any(v["level"] == "BLOCK" for v in violations)
    severity = "BLOCK" if has_block else ("WARN" if violations else "PASS")
    return {
        "verdict": "BLOCK" if has_block else "PASS",
        "allow_send": not has_block,
        "severity": severity,
        "violations": violations,
        "reason_codes": reason_codes or ["rule:compliance_clean"],
    }


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

"""Internal orchestration endpoints (InternalServiceAuth).

These are called by the Orchestrator (policy routing) and the Runtime (agent
execution). In production they are separate services; for the MVP they are
implemented as in-process stubs (see app/services/policy.py and agents.py) and
also exposed over HTTP so the Bruno/Postman P0 collection can exercise them.

No LLM calls are made; deterministic mock output is returned (TODO: real
multi-Agent LLM).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.envelope import ApiError
from app.core.responses import ok
from app.core.security import require_internal_auth
from app.schemas import (
    InternalAgentInvokeRequest,
    InternalPolicyEvaluateRequest,
    InternalSupervisorRequest,
)
from app.services import agents as agent_svc
from app.services import policy as policy_svc

router = APIRouter(prefix="/internal", tags=["Internal Orchestration"])


@router.post("/policy-router/evaluate")
def evaluate_policy_route(req: InternalPolicyEvaluateRequest, _: str = Depends(require_internal_auth)):
    data = policy_svc.evaluate_policy(
        project_id=req.project_id,
        conversation_id=req.conversation_id,
        session_runtime_id=req.session_runtime_id,
        event_type=req.event_type,
        event_payload=req.event_payload,
        context=req.context,
    )
    return ok(data, status_code=200)


@router.post("/agent-executor/invoke")
def invoke_agent_route(req: InternalAgentInvokeRequest, _: str = Depends(require_internal_auth)):
    data = agent_svc.invoke_agent(
        run_id=req.run_id,
        node_execution_id=req.node_execution_id,
        agent_type=req.agent_type,
        model_profile=req.model_profile,
        structured_input=req.structured_input,
        knowledge_context=req.knowledge_context,
        tool_scope=req.tool_scope,
    )
    return ok(data, status_code=200)


@router.post("/agent-executor/supervisor")
def invoke_supervisor_route(req: InternalSupervisorRequest, _: str = Depends(require_internal_auth)):
    data = agent_svc.invoke_supervisor(
        run_id=req.run_id,
        conversation_id=req.conversation_id,
        trigger_reason=req.trigger_reason,
        structured_context=req.structured_context,
        candidate_plans=req.candidate_plans,
    )
    return ok(data, status_code=200)

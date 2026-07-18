"""In-memory registry for inbound event status lookups (MVP).

The POST /api/runtime/inbound-events/messages returns a top-level requestId
(the SuccessEnvelope requestId). GET /api/runtime/inbound-events/{requestId}
resolves it. In production this would be a durable store; for the MVP an
in-process dict is sufficient because the status is queried within the same
server lifetime as the original POST.
"""
from __future__ import annotations

INBOUND_EVENTS: dict[str, dict] = {}


def record_inbound_event(
    request_id: str,
    *,
    conversation_id: str,
    run_id: str | None,
    status: str,
    dispatch_result: str,
):
    INBOUND_EVENTS[request_id] = {
        "conversationId": conversation_id,
        "runId": run_id,
        "status": status,
        "dispatchResult": dispatch_result,
    }


def get_inbound_event(request_id: str) -> dict | None:
    return INBOUND_EVENTS.get(request_id)

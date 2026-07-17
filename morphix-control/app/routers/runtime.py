"""Runtime-plane endpoints (RuntimeAuth): inbound events + device commands."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import ApiError, new_request_id
from app.core.responses import ok
from app.core.security import require_runtime_auth
from app.models import Conversation, Device, DeviceCommand, SessionRuntime
from app.schemas import (
    CreateDeviceCommandRequest,
    CreateDeviceCommandResponseData,
    InboundEventStatusData,
    InboundMessageEventAcceptedData,
    InboundMessageEventRequest,
)
from app.services import state as runtime_state
from app.services.orchestration import iso, process_inbound_event

router = APIRouter(prefix="/api/runtime", tags=["Runtime Inbound", "Runtime Device Commands"])


@router.post("/inbound-events/messages")
def create_inbound_message_event(
    req: InboundMessageEventRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_runtime_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    data: InboundMessageEventAcceptedData = process_inbound_event(db, req, idempotency_key)
    rid = new_request_id()
    dispatch_result = "merged_into_existing_run" if not data.accepted else "workflow_started"
    runtime_state.record_inbound_event(
        rid,
        conversation_id=data.conversation_id,
        run_id=None,
        status="processed" if data.accepted else "accepted",
        dispatch_result=dispatch_result,
    )
    return ok(data, status_code=202, request_id=rid)


@router.get("/inbound-events/{request_id}")
def get_inbound_event_status(request_id: str, _: str = Depends(require_runtime_auth)):
    ev = runtime_state.get_inbound_event(request_id)
    if ev is None:
        raise ApiError(404, "NOT_FOUND", f"inbound event {request_id} not found or expired")
    data = InboundEventStatusData(
        status=ev["status"],
        conversation_id=ev["conversationId"],
        run_id=ev["runId"],
        dispatch_result=ev["dispatchResult"],
    )
    return ok(data, status_code=200)


@router.post("/device-commands")
def create_device_command(
    req: CreateDeviceCommandRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_runtime_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # Idempotency: same key -> return the previously created command.
    if idempotency_key:
        prior = db.execute(select(DeviceCommand).where(DeviceCommand.idempotency_key == idempotency_key)).scalars().first()
        if prior is not None:
            return ok(CreateDeviceCommandResponseData(command_id=prior.id, status=prior.status), status_code=201)

    device = db.get(Device, req.device_id)
    if device is None:
        raise ApiError(404, "NOT_FOUND", f"device {req.device_id} not found")
    conv = db.get(Conversation, req.conversation_id)
    if conv is None:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", f"conversation {req.conversation_id} not found")

    cmd = DeviceCommand(
        id=f"cmd_{uuid.uuid4().hex}",
        project_id=req.project_id,
        device_id=req.device_id,
        channel_account_id=req.channel_account_id,
        conversation_id=req.conversation_id,
        run_id=req.run_id,
        command_type=req.command_type,
        payload=req.payload.model_dump(by_alias=True, exclude_none=True) if req.payload else {},
        policy_decision_id=req.policy_decision_id,
        status="pending",
        idempotency_key=idempotency_key,
    )
    db.add(cmd)
    db.commit()
    return ok(CreateDeviceCommandResponseData(command_id=cmd.id, status=cmd.status), status_code=201)

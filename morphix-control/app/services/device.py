"""Device-side orchestration: command callbacks, heartbeat, sync, diagnostics (MVP)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.models import (
    AuditLog,
    Conversation,
    Device,
    DeviceCommand,
    SessionRuntime,
)
from app.schemas import (
    DeviceCommandMutationData,
    PendingDeviceCommand,
    PendingDeviceCommandListData,
)

from app.core.envelope import new_request_id  # noqa: F401  (kept for potential use)


def iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _get_command_or_404(db: Session, command_id: str) -> DeviceCommand:
    cmd = db.get(DeviceCommand, command_id)
    if cmd is None:
        raise ApiError(404, "NOT_FOUND", f"command {command_id} not found")
    return cmd


def pull_pending_commands(
    db: Session,
    *,
    device: Device,
    channel_account_id: str | None,
    limit: int = 50,
) -> PendingDeviceCommandListData:
    """Return pending commands for the device and mark them sent.

    During an active human handoff we suppress proactive send_message commands
    (TC-D02: device stops auto-sending while a human is in control).
    """
    q = select(DeviceCommand).where(
        DeviceCommand.device_id == device.id,
        DeviceCommand.status == "pending",
    )
    if channel_account_id:
        q = q.where(DeviceCommand.channel_account_id == channel_account_id)
    q = q.order_by(DeviceCommand.issued_at.asc()).limit(limit)
    cmds = db.execute(q).scalars().all()

    items: list[PendingDeviceCommand] = []
    for c in cmds:
        conv = db.get(Conversation, c.conversation_id)
        if conv is not None and conv.handoff_status == "active" and c.command_type == "send_message":
            # Suppress proactive outbound while human is handling the conversation.
            continue
        c.status = "sent"
        items.append(
            PendingDeviceCommand(
                command_id=c.id,
                command_type=c.command_type,
                payload=c.payload,
                issued_at=iso(c.issued_at),
                idempotency_key=c.idempotency_key,
            )
        )
    db.commit()
    return PendingDeviceCommandListData(items=items)


def _ack(db: Session, device: Device, cmd: DeviceCommand, acked_at: str) -> DeviceCommandMutationData:
    if cmd.device_id != device.id:
        raise ApiError(403, "FORBIDDEN", "command does not belong to this device")
    if cmd.status in ("acked", "done"):
        return DeviceCommandMutationData(command_id=cmd.id, status=cmd.status)  # idempotent no-op
    if cmd.status == "failed":
        raise ApiError(409, "COMMAND_STATUS_INVALID", "cannot ack a failed command")
    cmd.status = "acked"
    cmd.acked_at = _parse(acked_at)
    db.commit()
    return DeviceCommandMutationData(command_id=cmd.id, status=cmd.status)


def _complete(db: Session, device: Device, cmd: DeviceCommand, done_at: str, result: dict | None) -> DeviceCommandMutationData:
    if cmd.device_id != device.id:
        raise ApiError(403, "FORBIDDEN", "command does not belong to this device")
    if cmd.status == "done":
        return DeviceCommandMutationData(command_id=cmd.id, status=cmd.status)  # idempotent no-op
    if cmd.status == "failed":
        raise ApiError(409, "COMMAND_STATUS_INVALID", "cannot complete a failed command")
    cmd.status = "done"
    cmd.done_at = _parse(done_at)
    db.commit()
    # Reflect completion back onto the conversation as a device/system message.
    conv = db.get(Conversation, cmd.conversation_id)
    if conv is not None:
        srt = db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conv.id)).scalars().first()
        if srt is not None and srt.session_state == "WAITING_DEVICE_ACK":
            srt.session_state = "IDLE"
    return DeviceCommandMutationData(command_id=cmd.id, status=cmd.status)


def _fail(db: Session, device: Device, cmd: DeviceCommand, failed_at: str, reason: str, retryable: bool) -> DeviceCommandMutationData:
    if cmd.device_id != device.id:
        raise ApiError(403, "FORBIDDEN", "command does not belong to this device")
    if cmd.status in ("done", "failed"):
        return DeviceCommandMutationData(command_id=cmd.id, status=cmd.status)  # idempotent no-op
    cmd.status = "failed"
    cmd.failed_at = _parse(failed_at)
    cmd.failure_reason = reason
    cmd.retryable = retryable
    db.commit()
    return DeviceCommandMutationData(command_id=cmd.id, status=cmd.status)


def ack_command(db: Session, device: Device, command_id: str, acked_at: str) -> DeviceCommandMutationData:
    return _ack(db, device, _get_command_or_404(db, command_id), acked_at)


def complete_command(db: Session, device: Device, command_id: str, done_at: str, result: dict | None) -> DeviceCommandMutationData:
    return _complete(db, device, _get_command_or_404(db, command_id), done_at, result)


def fail_command(db: Session, device: Device, command_id: str, failed_at: str, reason: str, retryable: bool) -> DeviceCommandMutationData:
    return _fail(db, device, _get_command_or_404(db, command_id), failed_at, reason, retryable)


def record_heartbeat(db: Session, device: Device, req) -> dict:
    device.status = req.device_status
    device.last_heartbeat_at = _parse(req.reported_at)
    db.add(
        AuditLog(
            id=f"aud_{uuid.uuid4().hex}",
            event_type="operator_action",
            resource_type="device",
            resource_id=device.id,
            project_id=device.project_id,
            actor_id=device.id,
            detail={"kind": "heartbeat", "accountStatus": req.account_status},
        )
    )
    db.commit()
    return {
        "serverTime": _utcnow().isoformat(),
        "nextHeartbeatInSec": 30,
        "commandPollIntervalSec": 5,
        "controlDirective": {
            "action": "noop",
            "reason": None,
            "until": None,
            "params": None,
        },
        "warnings": [],
    }


def _parse(v: str) -> datetime:
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return _utcnow()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

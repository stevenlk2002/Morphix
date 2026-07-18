"""Device-edge endpoints (DeviceAuth / DeviceProvisioningAuth)."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contract.database import get_db
from app.contract.envelope import ApiError, new_request_id
from app.contract.responses import ok
from app.contract.security import require_device_auth, require_device_provisioning_auth
from app.contract.models import Conversation, Device, Project
from app.contract.schemas import (
    ContactIdentity,
    ContactRef,
    ContactSyncBatchRequest,
    DeviceCommandAckRequest,
    DeviceCommandCompleteRequest,
    DeviceCommandFailRequest,
    DeviceControlDirective,
    DeviceDiagnosticLogBatchRequest,
    DeviceDiagnosticSnapshotRequest,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponseData,
    DeviceInboundMessageRequest,
    DeviceInboundMessageResponseData,
    DeviceRegistrationRequest,
    DeviceRegistrationResponseData,
    DeviceTokenRefreshRequest,
    DeviceTokenRefreshResponseData,
    DiagnosticUploadAcceptedData,
    GroupSyncBatchRequest,
    InboundMessage,
    InboundMessageEventAcceptedData,
    InboundMessageEventRequest,
    PendingDeviceCommandListData,
    SyncBatchAcceptedData,
)
from app.contract.services import device as device_svc
from app.contract.services.orchestration import process_inbound_event

router = APIRouter(prefix="/api/device", tags=["Device Provisioning", "Device Presence", "Device Inbound", "Device Sync", "Device Diagnostics", "Device Callback"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _channel_account_id_from_bind(bind_code: str) -> str:
    return "acc_" + hashlib.md5(bind_code.encode()).hexdigest()[:12]


@router.post("/registrations")
def register_device(
    req: DeviceRegistrationRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_device_provisioning_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    project = db.get(Project, req.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", f"project {req.project_id} not found")

    existing = db.execute(select(Device).where(Device.bind_code == req.bind_code)).scalars().first()
    if existing is not None:
        raise ApiError(409, "DEVICE_ALREADY_BOUND", f"bind code {req.bind_code} already used")

    settings = get_settings()
    channel_account_id = _channel_account_id_from_bind(req.bind_code)
    device = Device(
        id=f"dev_{uuid.uuid4().hex}",
        project_id=req.project_id,
        channel_account_id=channel_account_id,
        channel_type=req.channel_type,
        account_type=req.account_type,
        install_fingerprint=req.install_fingerprint,
        bind_code=req.bind_code,
        device_token=f"dt_{uuid.uuid4().hex}",
        token_expires_at=_utcnow() + timedelta(seconds=settings.TOKEN_TTL_SEC),
        status="online",
        device_meta=req.device_meta.model_dump(by_alias=True, exclude_none=True),
    )
    db.add(device)
    db.commit()
    return ok(
        DeviceRegistrationResponseData(
            device_id=device.id,
            project_id=device.project_id,
            channel_account_id=device.channel_account_id,
            channel_type=device.channel_type,
            device_token=device.device_token,
            token_expires_at=device.token_expires_at.isoformat(),
            heartbeat_interval_sec=settings.HEARTBEAT_INTERVAL_SEC,
            command_poll_interval_sec=settings.COMMAND_POLL_INTERVAL_SEC,
            control_flags=[],
        ),
        status_code=201,
    )


@router.post("/registrations/{device_id}/refresh-token")
def refresh_device_token(
    device_id: str,
    req: DeviceTokenRefreshRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if device.id != device_id:
        raise ApiError(404, "NOT_FOUND", f"device {device_id} not found")
    settings = get_settings()
    device.device_token = f"dt_{uuid.uuid4().hex}"
    device.token_expires_at = _utcnow() + timedelta(seconds=settings.TOKEN_TTL_SEC)
    db.commit()
    return ok(
        DeviceTokenRefreshResponseData(
            device_id=device.id,
            device_token=device.device_token,
            token_expires_at=device.token_expires_at.isoformat(),
        ),
        status_code=200,
    )


@router.post("/heartbeats")
def report_heartbeat(
    req: DeviceHeartbeatRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    data = device_svc.record_heartbeat(db, device, req)
    return ok(
        DeviceHeartbeatResponseData(
            server_time=data["serverTime"],
            next_heartbeat_in_sec=data["nextHeartbeatInSec"],
            command_poll_interval_sec=data["commandPollIntervalSec"],
            control_directive=DeviceControlDirective(**data["controlDirective"]),
            warnings=data["warnings"],
        ),
        status_code=200,
    )


@router.post("/inbound-messages")
def report_device_inbound_message(
    req: DeviceInboundMessageRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    mapped = InboundMessageEventRequest(
        project_id=device.project_id,
        channel_account_id=req.channel_account_id,
        device_id=device.id,
        conversation_type=req.conversation_type,
        source_conversation_id=req.source_conversation_id,
        source_message_id=req.source_message_id,
        contact=ContactRef(
            external_uid=req.contact.external_uid,
            display_name=req.contact.display_name,
            tags=[req.contact.remark_name] if req.contact.remark_name else None,
        ),
        message=InboundMessage(
            message_type=req.message.message_type,
            content_text=req.message.content_text,
            media_url=req.message.media_url,
            sent_at=req.message.sent_at,
        ),
        metadata={"channelType": req.channel_type, "rawContext": req.raw_context},
    )
    data: InboundMessageEventAcceptedData = process_inbound_event(db, mapped, idempotency_key)
    rid = new_request_id()
    return ok(
        DeviceInboundMessageResponseData(
            accepted=True,
            event_id=rid,
            orchestration_request_id=rid,
            conversation_id=data.conversation_id,
            deduplicated=not data.accepted,
        ),
        status_code=202,
    )


@router.get("/commands/pending")
def list_pending_commands(
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    channel_account_id: str | None = Query(default=None, alias="channelAccountId"),
    limit: int = Query(default=50, ge=1, le=200),
):
    data: PendingDeviceCommandListData = device_svc.pull_pending_commands(
        db, device=device, channel_account_id=channel_account_id, limit=limit
    )
    return ok(data, status_code=200)


@router.post("/commands/{command_id}/ack")
def ack_command(
    command_id: str,
    req: DeviceCommandAckRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    data = device_svc.ack_command(db, device, command_id, req.acked_at)
    return ok(data, status_code=200)


@router.post("/commands/{command_id}/complete")
def complete_command(
    command_id: str,
    req: DeviceCommandCompleteRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    data = device_svc.complete_command(db, device, command_id, req.done_at, req.result)
    return ok(data, status_code=200)


@router.post("/commands/{command_id}/fail")
def fail_command(
    command_id: str,
    req: DeviceCommandFailRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    data = device_svc.fail_command(db, device, command_id, req.failed_at, req.failure_reason, req.retryable)
    return ok(data, status_code=200)


@router.post("/contact-sync/batches")
def upload_contact_sync(
    req: ContactSyncBatchRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return ok(
        SyncBatchAcceptedData(
            sync_session_id=req.sync_session_id,
            batch_no=req.batch_no,
            accepted_count=len(req.contacts),
            finished=req.finished,
        ),
        status_code=202,
    )


@router.post("/group-sync/batches")
def upload_group_sync(
    req: GroupSyncBatchRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return ok(
        SyncBatchAcceptedData(
            sync_session_id=req.sync_session_id,
            batch_no=req.batch_no,
            accepted_count=len(req.groups),
            finished=req.finished,
        ),
        status_code=202,
    )


@router.post("/diagnostics/log-batches")
def upload_diagnostic_logs(
    req: DeviceDiagnosticLogBatchRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return ok(
        DiagnosticUploadAcceptedData(accepted=True, received_at=_utcnow().isoformat(), incident_id=req.incident_id),
        status_code=202,
    )


@router.post("/diagnostics/snapshots")
def upload_diagnostic_snapshot(
    req: DeviceDiagnosticSnapshotRequest,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return ok(
        DiagnosticUploadAcceptedData(accepted=True, received_at=_utcnow().isoformat()),
        status_code=202,
    )

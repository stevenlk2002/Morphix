from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import ApiError
from app.core.config import get_settings
from app.models import Device

# RBAC matrix: which roles may perform writes.
_WRITE_ROLES = {"owner", "admin", "editor"}
_ROLE_ORDER = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}


def _bearer(token: str | None) -> str | None:
    if token and token.lower().startswith("bearer "):
        return token[7:].strip() or None
    return token


def _dev_accept(token: str | None, header_name: str) -> str:
    if not token:
        raise ApiError(401, "UNAUTHORIZED", f"Missing auth header: {header_name}")
    # MVP / dev: accept any non-empty token. Real deployment must verify signature/JWT.
    return token


def require_control_auth(
    authorization: str | None = Header(default=None),
    x_control_token: str | None = Header(default=None, alias="X-Control-Token"),
):
    token = _bearer(authorization) or x_control_token
    return _dev_accept(token, "Authorization/X-Control-Token")


def require_runtime_auth(
    x_runtime_token: str | None = Header(default=None, alias="X-Runtime-Token"),
):
    return _dev_accept(x_runtime_token, "X-Runtime-Token")


def require_internal_auth(
    x_internal_service_token: str | None = Header(
        default=None, alias="X-Internal-Service-Token"
    ),
):
    return _dev_accept(x_internal_service_token, "X-Internal-Service-Token")


def require_device_provisioning_auth(
    x_device_provisioning_key: str | None = Header(
        default=None, alias="X-Device-Provisioning-Key"
    ),
):
    settings = get_settings()
    if not x_device_provisioning_key:
        raise ApiError(401, "UNAUTHORIZED", "Missing device provisioning key")
    # Dev mode accepts any non-empty key; otherwise it must match the configured key.
    if settings.DEV_MODE or x_device_provisioning_key == settings.DEVICE_PROVISIONING_KEY:
        return x_device_provisioning_key
    raise ApiError(401, "UNAUTHORIZED", "Invalid device provisioning key")


def require_device_auth(
    x_device_token: str = Header(..., alias="X-Device-Token"),
    db: Session = Depends(get_db),
) -> Device:
    if not x_device_token:
        raise ApiError(401, "UNAUTHORIZED", "Missing device token")
    device = (
        db.query(Device)
        .filter(Device.device_token == x_device_token, Device.deleted_at.is_(None))
        .first()
    )
    if device is None:
        raise ApiError(401, "DEVICE_UNAUTHORIZED", "Invalid or expired device token")
    return device


def require_role(
    x_role: str | None = Header(default=None, alias="X-Role"),
    allowed: set[str] | None = None,
):
    """RBAC gate for write operations. Raises 403 FORBIDDEN for viewers."""
    allowed = allowed or _WRITE_ROLES
    role = (x_role or "owner").lower()
    if role not in _ROLE_ORDER:
        role = "viewer"
    if role not in allowed:
        raise ApiError(
            403,
            "FORBIDDEN",
            f"Role '{role}' is not permitted for this operation (requires one of {sorted(allowed)})",
        )
    return role

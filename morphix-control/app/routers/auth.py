"""Auth / token bootstrap (contract gap filler).

The unified contract only returns a deviceToken from registration and does not
define endpoints to obtain controlToken / runtimeToken / internalToken /
provisioningKey. This MVP endpoint issues opaque tokens so clients (Bruno /
Postman / scripts) can bootstrap the other security schemes.

MVP: tokens are opaque random strings; no signature verification. Real deployment
must mint signed JWTs and verify them in app/core/security.py.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.envelope import DTO
from app.core.responses import ok

router = APIRouter(tags=["Auth"])


class DevBootstrapRequest(DTO):
    project_id: str | None = None
    scopes: list[str] | None = None  # control | runtime | internal | provisioning


class DevBootstrapData(DTO):
    control_token: str
    runtime_token: str
    internal_token: str
    provisioning_key: str


@router.post("/api/auth/dev-bootstrap")
def dev_bootstrap(
    body: DevBootstrapRequest | None = None,
    x_device_provisioning_key: str | None = Header(default=None, alias="X-Device-Provisioning-Key"),
):
    settings = get_settings()
    scopes = set(body.scopes) if body and body.scopes else {"control", "runtime", "internal", "provisioning"}
    data = DevBootstrapData(
        control_token=f"ctrl_{uuid.uuid4().hex}" if "control" in scopes else "",
        runtime_token=f"rt_{uuid.uuid4().hex}" if "runtime" in scopes else "",
        internal_token=f"int_{uuid.uuid4().hex}" if "internal" in scopes else "",
        provisioning_key=(x_device_provisioning_key or settings.DEVICE_PROVISIONING_KEY)
        if "provisioning" in scopes
        else "",
    )
    return ok(data, status_code=200)

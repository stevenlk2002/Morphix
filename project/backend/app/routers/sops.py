"""SOP 路由。

保持原路径：
- POST /api/sops
"""
from __future__ import annotations

from fastapi import APIRouter

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, SopRepository
from ..schemas import SopCreateRequest

router = APIRouter(tags=["sops"])


@router.post("/sops")
def create_sop(payload: SopCreateRequest):
    backend = get_backend()
    sop_id = make_id("sop")
    with backend.transaction() as tx:
        result = SopRepository(tx).create(sop_id, payload.name, payload.trigger)
        AuditRepository(tx).record("create_sop", payload.name, payload.trigger)
    return result

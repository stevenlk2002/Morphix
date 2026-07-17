"""Morphix Control entrypoint.

Wires the routers, registers exception handlers that emit the unified
SuccessEnvelope / ErrorEnvelope, and seeds demo data on startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.database import SessionLocal, engine
from app.core.envelope import ApiEnvelope, ApiError, ErrorObject, new_request_id
from app.core.responses import fail
from app.routers import auth, control, device, health, internal, management, runtime
from app.seed import seed_demo

import app.models  # noqa: F401  (register ORM tables on Base.metadata)

# NOTE: The database schema is owned exclusively by Alembic. Run
# `alembic upgrade head` to create all tables + constraints before starting
# the app. Application startup no longer calls create_all().


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Morphix Control", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(control.router)
app.include_router(management.router)
app.include_router(runtime.router)
app.include_router(device.router)
app.include_router(internal.router)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return fail(exc)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []))
        details.append({"field": loc, "reason": err.get("msg", "invalid")})
    env = ApiEnvelope(
        request_id=new_request_id(),
        success=False,
        data=None,
        error=ErrorObject(code="INVALID_REQUEST", message="request validation failed", details=details),
    )
    return JSONResponse(status_code=422, content=env.model_dump(by_alias=True))

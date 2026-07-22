"""Morphix MVP 后端主入口（模块化重构版 + 统一契约域收敛）。

收敛说明（工程收敛增量）：
- 资源域（bots/channels/tags/conversations/knowledge/materials/sops/meta/workflows）
  维持原有裸 SQL 实现不变，`/api/conversations`、`/api/workflows` 等遗留端点
  保留但标注 Deprecated（canonical 会话/运行改用契约路径
  `/api/control/conversations`、`/api/control/workflow-runs`）。
- 统一契约域（control/runtime/device/internal/auth）整包移植自 morphix-control，
  自包含 SQLAlchemy 持久层（独立库 morphix_contract.db），挂载到
  `/api/control`、`/api/runtime`、`/api/device`、`/internal`、`/api/auth`。
- 全站统一 Success/Error 封套：仅对契约域抛出的 ApiError 与请求校验错误
  （RequestValidationError）做封套包装；资源域既有响应格式保持不变，确保
  现有测试（tests/test_api.py）无改动通过。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .contract.envelope import ApiEnvelope, ApiError, ErrorObject, new_request_id
from .contract.responses import fail
from .contract.routers import auth, control, device, internal, management, runtime
from .database import get_backend
from .observability import MetricsMiddleware
from .routers import api_router
from .routers import channel_callback
from .schema import init_schema

# 配置日志：慢请求和错误会通过 logger 输出
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：初始化资源域 schema + 契约域 schema + 种子数据。"""
    # 1) 资源域（裸 SQL 自管）
    backend = get_backend()
    init_schema(backend)

    # 2) 契约域（独立 SQLAlchemy 库，双库隔离）
    # 触发 app.contract 包导入，注册全部 ORM 表到 Base.metadata，再建表。
    from . import contract  # noqa: F401

    contract.database.Base.metadata.create_all(bind=contract.database.engine)
    _cdb = contract.database.SessionLocal()
    try:
        contract.seed.seed_demo(_cdb)
    finally:
        _cdb.close()

    yield


app = FastAPI(
    title="Morphix MVP API",
    version="0.2.0",
    description="模块化重构版 + 统一契约域收敛（control/runtime/device/internal/auth）",
    lifespan=lifespan,
)

# CORS：允许前端 1181/1182/5173 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可观测性中间件：记录请求耗时并聚合 P99 指标
app.add_middleware(MetricsMiddleware)

# 挂载资源域路由（保持 /api 前缀，路径与响应结构不变）
app.include_router(api_router)

# 挂载统一契约域路由（移植自 morphix-control，独立持久层）
# 注意：不挂载 contract.routers.health（避免与资源域 /api/health 冲突）。
app.include_router(auth.router)
app.include_router(control.router)
app.include_router(management.router)
app.include_router(runtime.router)
app.include_router(device.router)
app.include_router(internal.router)

# 挂载 iPad 实时回调路由（前缀 /wxwork，独立于资源域 /api，公网可达端点）
app.include_router(channel_callback.router)


# ---- 统一封套异常处理器（仅作用于契约域）----
@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """将契约域抛出的 ApiError 统一包装为 ErrorEnvelope。"""
    return fail(exc)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """将请求体/参数校验错误统一包装为 ErrorEnvelope（422）。"""
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []))
        details.append({"field": loc, "reason": err.get("msg", "invalid")})
    env = ApiEnvelope(
        request_id=new_request_id(),
        success=False,
        data=None,
        error=ErrorObject(
            code="INVALID_REQUEST",
            message="request validation failed",
            details=details,
        ),
    )
    return JSONResponse(status_code=422, content=env.model_dump(by_alias=True))

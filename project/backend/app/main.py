"""Morphix MVP 后端主入口（模块化重构版）。

重构目标：
- 数据访问层抽象，可切换 SQLite / PostgreSQL。
- 分页规范 + 索引定义，性能可观测。
- P99 埋点 + 增强健康检查，满足性能落地要求。
- 模块化拆分（config / database / repositories / routers / schemas），保持对外 API contract 不变。

对外 API 路径与响应格式严格保持与原 main.py 一致，所有现有测试应无改动通过。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import get_backend
from .observability import MetricsMiddleware
from .routers import api_router
from .schema import init_schema

# 配置日志：慢请求和错误会通过 logger 输出
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化数据库 schema + 索引 + 种子数据。"""
    backend = get_backend()
    init_schema(backend)
    yield


app = FastAPI(
    title="Morphix MVP API",
    version="0.2.0",
    description="模块化重构版：数据访问层抽象 + 分页规范 + P99 埋点 + 增强健康检查",
    lifespan=lifespan,
)

# CORS：允许前端 1181 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可观测性中间件：记录请求耗时并聚合 P99 指标
app.add_middleware(MetricsMiddleware)

# 挂载所有路由（保持 /api 前缀）
app.include_router(api_router)

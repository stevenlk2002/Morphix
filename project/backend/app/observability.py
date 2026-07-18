"""可观测性：请求耗时埋点 + P99 指标聚合。

性能落地要求之一：接口 P99 埋点 + 健康检查。
实现方式：
- 中间件记录每个请求的耗时（毫秒），按路由模板聚合。
- 维护滑动窗口样本，暴露 /api/metrics 输出 P50/P95/P99/max。
- 超过 slow_request_ms 阈值的请求打慢日志，便于定位。

MVP 用进程内内存聚合，零外部依赖；升级时可替换为 Prometheus / OTel。
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import settings

logger = logging.getLogger("morphix.perf")

# 每个路由保留最近 N 个样本用于分位数计算
_WINDOW = 500


class _MetricsStore:
    """线程安全的请求指标聚合器。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_WINDOW))
        self._count: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)

    def record(self, route: str, duration_ms: float, is_error: bool) -> None:
        with self._lock:
            self._samples[route].append(duration_ms)
            self._count[route] += 1
            if is_error:
                self._errors[route] += 1

    def snapshot(self) -> dict:
        with self._lock:
            routes = {}
            all_samples: list[float] = []
            for route, samples in self._samples.items():
                ordered = sorted(samples)
                all_samples.extend(ordered)
                routes[route] = {
                    "count": self._count[route],
                    "errors": self._errors[route],
                    "p50": _percentile(ordered, 50),
                    "p95": _percentile(ordered, 95),
                    "p99": _percentile(ordered, 99),
                    "max": round(ordered[-1], 2) if ordered else 0.0,
                }
            overall_sorted = sorted(all_samples)
            return {
                "slowRequestThresholdMs": settings.slow_request_ms,
                "overall": {
                    "count": sum(self._count.values()),
                    "errors": sum(self._errors.values()),
                    "p50": _percentile(overall_sorted, 50),
                    "p95": _percentile(overall_sorted, 95),
                    "p99": _percentile(overall_sorted, 99),
                    "max": round(overall_sorted[-1], 2) if overall_sorted else 0.0,
                },
                "routes": routes,
            }


def _percentile(ordered: list[float], pct: float) -> float:
    """从已排序样本取分位数（最近邻法）。"""
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (pct / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    frac = rank - lower
    value = ordered[lower] * (1 - frac) + ordered[upper] * frac
    return round(value, 2)


metrics_store = _MetricsStore()


def _route_template(request: Request) -> str:
    """取路由模板（含路径参数占位符）作为聚合键，避免高基数。"""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return f"{request.method} {route.path}"
    return f"{request.method} {request.url.path}"


class MetricsMiddleware(BaseHTTPMiddleware):
    """记录每个请求耗时并聚合。"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        is_error = False
        try:
            response = await call_next(request)
            is_error = response.status_code >= 500
            return response
        except Exception:
            is_error = True
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            route = _route_template(request)
            metrics_store.record(route, duration_ms, is_error)
            if duration_ms > settings.slow_request_ms:
                logger.warning("slow request %s took %.1fms", route, duration_ms)

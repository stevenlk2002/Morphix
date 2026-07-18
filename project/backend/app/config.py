"""集中配置。

通过环境变量控制数据库后端与运行参数，MVP 默认 SQLite，
预留 PostgreSQL 切换能力（只需设置 MORPHIX_DB_BACKEND=postgres 并补齐 DSN）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录：app/config.py -> app -> backend -> project -> 仓库根
ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = ROOT_DIR / "database" / "morphix_mvp.db"


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


@dataclass(frozen=True)
class Settings:
    """运行时设置，进程启动时读取一次。"""

    # 数据库后端标识：sqlite | postgres
    db_backend: str = field(default_factory=lambda: _env("MORPHIX_DB_BACKEND", "sqlite"))
    # SQLite 文件路径
    sqlite_path: Path = field(default_factory=lambda: Path(_env("MORPHIX_SQLITE_PATH", str(DEFAULT_SQLITE_PATH))))
    # PostgreSQL DSN（切换到 postgres 时使用）
    postgres_dsn: str = field(default_factory=lambda: _env("MORPHIX_POSTGRES_DSN", ""))
    # 允许的前端来源（CORS）
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in _env(
                "MORPHIX_CORS_ORIGINS",
                "http://localhost:1181,http://127.0.0.1:1181,http://localhost:1182,http://127.0.0.1:1182",
            ).split(",")
            if origin.strip()
        )
    )
    # 慢请求阈值（毫秒），用于 P99 观测与告警日志
    slow_request_ms: float = field(default_factory=lambda: float(_env("MORPHIX_SLOW_REQUEST_MS", "3000")))
    # 分页默认与上限
    default_page_size: int = field(default_factory=lambda: int(_env("MORPHIX_DEFAULT_PAGE_SIZE", "20")))
    max_page_size: int = field(default_factory=lambda: int(_env("MORPHIX_MAX_PAGE_SIZE", "100")))


settings = Settings()

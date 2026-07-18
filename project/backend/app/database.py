"""数据库后端抽象层。

设计目标：数据访问代码只依赖 `DatabaseBackend` 接口，不感知具体是
SQLite 还是 PostgreSQL。MVP 默认 SQLite；切换 PostgreSQL 只需实现
一个新的 backend 并在工厂中注册，Repository 层零改动。

统一约定：
- SQL 中一律使用 `?` 作为占位符，backend 负责翻译成目标方言。
- 查询返回 `list[dict]`，写入返回受影响行数或自增 id。
- 通过 `transaction()` 上下文管理器保证原子性。
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Protocol, Sequence

from .config import Settings


class DatabaseBackend(Protocol):
    """所有数据库后端必须实现的最小接口。"""

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]: ...

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict]: ...

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int: ...

    def executescript(self, script: str) -> None: ...

    @contextmanager
    def transaction(self) -> Iterator["DatabaseBackend"]: ...


class SQLiteBackend:
    """SQLite 实现。

    使用线程局部连接，兼容 FastAPI 的线程池执行模型。
    占位符本身就是 `?`，无需翻译。
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._local = threading.local()
        db_path.parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            # WAL 提升并发读性能，贴合"高并发读"的控制面场景
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return conn

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        cursor = self._conn().execute(sql, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict]:
        cursor = self._conn().execute(sql, tuple(params))
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        conn = self._conn()
        cursor = conn.execute(sql, tuple(params))
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

    def executescript(self, script: str) -> None:
        conn = self._conn()
        conn.executescript(script)
        conn.commit()

    @contextmanager
    def transaction(self) -> Iterator["SQLiteBackend"]:
        conn = self._conn()
        try:
            yield self
            conn.commit()
        except Exception:
            conn.rollback()
            raise


_backend: Optional[DatabaseBackend] = None


def build_backend(settings: Settings) -> DatabaseBackend:
    """根据配置构造数据库后端。

    预留 PostgreSQL 分支：实现 PostgresBackend 后在此注册即可，
    Repository / Router 层无需任何改动。
    """
    if settings.db_backend == "sqlite":
        return SQLiteBackend(settings.sqlite_path)
    if settings.db_backend == "postgres":
        raise NotImplementedError(
            "PostgreSQL 后端尚未实现。MVP 阶段使用 SQLite；"
            "升级时请实现 PostgresBackend 并在 build_backend 注册，"
            "占位符 ? 需翻译为 %s。"
        )
    raise ValueError(f"未知的数据库后端: {settings.db_backend}")


def get_backend() -> DatabaseBackend:
    """获取全局单例后端。"""
    global _backend
    if _backend is None:
        from .config import settings

        _backend = build_backend(settings)
    return _backend


def set_backend(backend: Optional[DatabaseBackend]) -> None:
    """测试注入用：允许替换或重置全局后端。"""
    global _backend
    _backend = backend

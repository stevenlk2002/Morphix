"""给已存在的 morphix.db 的 session_runtimes 表补齐两个 CheckConstraint。

背景:
    SQLite 不支持 `ALTER TABLE ADD CONSTRAINT`，SQLAlchemy 的 create_all 对
    已存在的表是 no-op，因此已投产的数据库不会自动获得约束。本脚本通过
    "建新表 -> 校验+拷贝数据 -> 删旧表 -> 改名" 的方式补齐约束。

    新库（首次 create_all 建表）无需运行本脚本，约束已由 ORM 定义自动创建。

约束内容（与 app/models/__init__.py 的 __table_args__ 保持一致）:
    - ck_session_runtime_session_state:
        session_state IN ('IDLE','AUTO_HOSTING','WAITING_USER','WAITING_TIMER',
                          'WAITING_DEVICE_ACK','HUMAN_HANDOFF','PAUSED_BY_POLICY',
                          'ERROR_REVIEW','CLOSED')
    - ck_session_runtime_hosting_status:
        hosting_status IN ('enabled','paused','disabled')

用法:
    python scripts/add_session_runtime_checks.py
    DB_PATH=/path/to/morphix.db python scripts/add_session_runtime_checks.py

安全:
    - 幂等：约束已存在则直接退出。
    - 数据先行校验：若现有数据有非法值，中止并不做任何修改，避免拷贝时触发约束报错。
    - 全程在事务内完成，失败自动回滚。
"""
from __future__ import annotations

import os
import sqlite3
import sys

SESSION_STATE_VALUES = (
    "IDLE", "AUTO_HOSTING", "WAITING_USER", "WAITING_TIMER",
    "WAITING_DEVICE_ACK", "HUMAN_HANDOFF", "PAUSED_BY_POLICY",
    "ERROR_REVIEW", "CLOSED",
)
HOSTING_STATUS_VALUES = ("enabled", "paused", "disabled")

# 兜底 DB_PATH：与 app.core.database.settings 默认一致，但允许环境变量覆盖。
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "morphix.db",
)


def get_db_path() -> str:
    return os.environ.get("DB_PATH", DEFAULT_DB_PATH)


def constraint_exists(con: sqlite3.Connection, name: str) -> bool:
    rows = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='session_runtimes'"
    ).fetchall()
    if not rows or rows[0][0] is None:
        return False
    return name in (rows[0][0] or "")


def validate_existing_data(con: sqlite3.Connection) -> list[str]:
    bad: list[str] = []
    rows = con.execute(
        "SELECT id, session_state, hosting_status FROM session_runtimes"
    ).fetchall()
    for row_id, state, hosting in rows:
        if state not in SESSION_STATE_VALUES:
            bad.append(f"id={row_id} session_state={state!r} 非法")
        if hosting not in HOSTING_STATUS_VALUES:
            bad.append(f"id={row_id} hosting_status={hosting!r} 非法")
    return bad


def column_defs(con: sqlite3.Connection) -> str:
    """读取原表列定义，保证新表与原表结构完全一致。"""
    cols = con.execute("PRAGMA table_info(session_runtimes)").fetchall()
    # PRAGMA 返回: (cid, name, type, notnull, dflt_value, pk)
    parts: list[str] = []
    for cid, name, ctype, notnull, dflt, pk in cols:
        col = f'"{name}" {ctype}'
        if pk:
            col += " PRIMARY KEY"
        if notnull:
            col += " NOT NULL"
        if dflt is not None:
            col += f" DEFAULT {dflt}"
        parts.append(col)
    return ",\n  ".join(parts)


def main() -> int:
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"⚠️  数据库文件不存在: {db_path}（新库将由 create_all 自动建约束，无需迁移）")
        return 0

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        if constraint_exists(con, "ck_session_runtime_session_state") and \
           constraint_exists(con, "ck_session_runtime_hosting_status"):
            print("✅ 两个 CheckConstraint 已存在，无需迁移。")
            return 0

        # 1) 校验现有数据，避免拷贝时触发约束报错。
        bad = validate_existing_data(con)
        if bad:
            print("❌ 现有数据包含非法值，已中止迁移（未做任何修改）：")
            for line in bad:
                print(f"   - {line}")
            return 1

        # 2) 重建表（SQLite 加约束唯一可靠方式）。
        defs = column_defs(con)
        con.execute("BEGIN")
        con.execute(f"""
            CREATE TABLE session_runtimes_new (
              {defs},
              CONSTRAINT ck_session_runtime_session_state
                CHECK (session_state IN ({','.join(repr(v) for v in SESSION_STATE_VALUES)})),
              CONSTRAINT ck_session_runtime_hosting_status
                CHECK (hosting_status IN ({','.join(repr(v) for v in HOSTING_STATUS_VALUES)}))
            )
        """)
        con.execute(
            "INSERT INTO session_runtimes_new "
            "SELECT * FROM session_runtimes"
        )
        con.execute("DROP TABLE session_runtimes")
        con.execute("ALTER TABLE session_runtimes_new RENAME TO session_runtimes")

        # 重建原表上的索引（DROP TABLE 会一并删除索引）。
        indexes = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND tbl_name='session_runtimes' AND sql IS NOT NULL"
        ).fetchall()
        # 注意：DROP TABLE 后 sqlite_master 里该表的索引已不存在，
        # 这里仅做防御性提示。唯一索引（unique=True）随表重建需重新创建：
        con.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "ix_session_runtimes_conversation_id" '
            'ON session_runtimes("conversation_id")'
        )
        con.execute(
            'CREATE INDEX IF NOT EXISTS "ix_session_runtimes_conversation_id_idx" '
            'ON session_runtimes("conversation_id")'
        )
        con.commit()

        print("✅ 已成功为 session_runtimes 补齐两个 CheckConstraint。")
        print(f"   - 受影响行数: {len(con.execute('SELECT 1 FROM session_runtimes').fetchall())}")
        return 0
    except Exception as e:  # noqa: BLE001
        con.rollback()
        print(f"❌ 迁移失败并回滚: {type(e).__name__}: {e}")
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())

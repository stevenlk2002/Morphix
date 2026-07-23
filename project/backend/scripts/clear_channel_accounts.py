#!/usr/bin/env python3
"""一次性清理脚本：清空所有渠道账号及其衍生数据。

用途：当二维码/验证码流程产生大量测试账号或旧 demo 数据残留时，
用于彻底清空渠道账号相关表，让用户可以从零开始重新走真实托管流程。

清理范围（仅渠道相关表，不动业务核心表）：
- channel_accounts
- channel_seats
- channel_contacts
- channel_sessions
- channel_groups
- channel_group_members

保留以下表（避免误伤）：
- bots, conversations, messages, customers, customer_profiles,
- teams, users, audit_events, workflow_*, sop_*, knowledge_*, materials 等

用法：
    cd project/backend
    .venv/bin/python scripts/clear_channel_accounts.py --yes

不带 --yes 时仅做预览，不会真正删除。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


# 默认数据库路径：从项目根目录相对定位
DEFAULT_DB = Path(__file__).resolve().parents[3] / "database" / "morphix_mvp.db"

TABLES = [
    "channel_group_members",
    "channel_groups",
    "channel_contacts",
    "channel_sessions",
    "channel_seats",
    "channel_accounts",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="清空 Morphix 渠道账号相关数据")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 数据库路径")
    parser.add_argument("--yes", action="store_true", help="确认执行删除（否则仅预览）")
    args = parser.parse_args()

    db_path = args.db
    if not db_path.exists():
        print(f"数据库不存在：{db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 预览各表行数
    print(f"数据库：{db_path}")
    print("-" * 50)
    total = 0
    rows_before: dict[str, int] = {}
    for table in TABLES:
        try:
            cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
            count = int(cur.fetchone()["c"])
        except sqlite3.OperationalError:
            count = 0
        rows_before[table] = count
        total += count
        print(f"  {table}: {count} 行")

    print("-" * 50)
    print(f"合计待清理：{total} 行")

    if total == 0:
        print("无需清理，渠道相关表已为空。")
        conn.close()
        return 0

    if not args.yes:
        print("\n⚠️  这是一次性清理操作，以上数据将被永久删除。")
        print("若确认执行，请追加 --yes 参数。")
        conn.close()
        return 0

    # 执行清理（按外键依赖逆序）
    print("\n正在清理…")
    for table in TABLES:
        try:
            cur.execute(f"DELETE FROM {table}")
            print(f"  已清空 {table}（{cur.rowcount} 行）")
        except sqlite3.OperationalError as exc:
            print(f"  跳过 {table}：{exc}", file=sys.stderr)

    conn.commit()
    conn.close()
    print("\n✅ 渠道账号及相关数据已清空。请重启后端服务以同步内存状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

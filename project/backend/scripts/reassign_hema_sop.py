#!/usr/bin/env python3
"""将 SOP 编排 / 知识库从源 bot 重新归属到目标 bot（一次性迁移脚本）。

背景：
- 河马大健康客户机器人（前端 bot id = `hema`）的编排界面、知识库 Tab 此前
  读取不到任何数据，因为真实 SOP 数据被挂在 `hema_kefu` 这个"幽灵" owner 上
  （无 bots 表行、前端不可见）。
- 本脚本把 orchestration_workflows 与 knowledge_base 中 bot_id = --from 的行
  重新归属为 --to（默认 hema），使前端「河马大健康客户」直接看到完整 SOP 流程
  与知识库，并可在界面内增删改。

影响范围（仅重新归属，不复制、不删除其它 bot 的数据）：
- orchestration_workflows.bot_id        (from -> to)，并同步修正 data 内 botId 字段
- knowledge_base.bot_id                 (from -> to)

幂等：若 --from 已无数据，则直接报告"无需处理"。

用法：
    cd project/backend
    .venv/bin/python scripts/reassign_hema_sop.py            # 仅预览
    .venv/bin/python scripts/reassign_hema_sop.py --yes      # 执行（先自动备份 DB）
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[3] / "database" / "morphix_mvp.db"

FROM_BOT = "hema_kefu"
TO_BOT = "hema"


def _count(cur: sqlite3.Cursor, table: str, bot_id: str) -> int:
    cur.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE bot_id = ?", (bot_id,))
    return int(cur.fetchone()["c"])


def main() -> int:
    parser = argparse.ArgumentParser(description="将 SOP 编排/知识库重新归属到目标 bot")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 数据库路径")
    parser.add_argument("--from", dest="from_bot", default=FROM_BOT, help="源 bot id")
    parser.add_argument("--to", dest="to_bot", default=TO_BOT, help="目标 bot id")
    parser.add_argument("--yes", action="store_true", help="确认执行重新归属（否则仅预览）")
    args = parser.parse_args()

    db_path = args.db
    if not db_path.exists():
        print(f"数据库不存在：{db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    orch_n = _count(cur, "orchestration_workflows", args.from_bot)
    kb_n = _count(cur, "knowledge_base", args.from_bot)

    print(f"数据库：{db_path}")
    print(f"源 bot：{args.from_bot}  ->  目标 bot：{args.to_bot}")
    print("-" * 50)
    print(f"  orchestration_workflows 待归属：{orch_n} 行")
    print(f"  knowledge_base          待归属：{kb_n} 行")
    print("-" * 50)

    if orch_n == 0 and kb_n == 0:
        print("无需处理：源 bot 已无 SOP 数据。")
        conn.close()
        return 0

    if not args.yes:
        print("\n⚠️  这是数据归属变更操作（会先自动备份数据库）。确认执行请追加 --yes。")
        conn.close()
        return 0

    # 备份
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_suffix(f".db.bak-reassign-{stamp}")
    shutil.copy2(db_path, backup)
    print(f"\n已备份数据库：{backup}")

    # 1) orchestration_workflows：更新 bot_id 并同步 data.botId
    moved_orch = 0
    if orch_n:
        cur.execute(
            "SELECT bot_id, data FROM orchestration_workflows WHERE bot_id = ?",
            (args.from_bot,),
        )
        for row in cur.fetchall():
            data = json.loads(row["data"])
            data["botId"] = args.to_bot
            cur.execute(
                "UPDATE orchestration_workflows SET bot_id = ?, data = ?, updated_at = datetime('now') WHERE bot_id = ?",
                (args.to_bot, json.dumps(data, ensure_ascii=False), args.from_bot),
            )
            moved_orch += 1
        print(f"  ✅ orchestration_workflows 归属 {moved_orch} 行 -> {args.to_bot}")

    # 2) knowledge_base：更新 bot_id
    moved_kb = 0
    if kb_n:
        cur.execute(
            "UPDATE knowledge_base SET bot_id = ? WHERE bot_id = ?",
            (args.to_bot, args.from_bot),
        )
        moved_kb = cur.rowcount
        print(f"  ✅ knowledge_base 归属 {moved_kb} 行 -> {args.to_bot}")

    conn.commit()
    conn.close()

    # 校验
    print("\n校验目标 bot 现有数据：")
    c2 = sqlite3.connect(str(db_path))
    c2.row_factory = sqlite3.Row
    cur2 = c2.cursor()
    print(f"  orchestration_workflows[{args.to_bot}]: {_count(cur2, 'orchestration_workflows', args.to_bot)} 行")
    print(f"  knowledge_base[{args.to_bot}]: {_count(cur2, 'knowledge_base', args.to_bot)} 行")
    print(f"  源 bot 残留：orch={_count(cur2, 'orchestration_workflows', args.from_bot)} kb={_count(cur2, 'knowledge_base', args.from_bot)}")
    c2.close()

    print("\n✅ 重新归属完成。请重启后端服务（或确认其已热加载）以生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

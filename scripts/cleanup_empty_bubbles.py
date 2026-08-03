#!/usr/bin/env python3
"""清理 messages 表中的「空气泡」历史脏数据。

背景（Bug：聊天框刷出成片只有时间戳的空蓝气泡）：
iPad 协议的控制/回执类事件（2001 MarkAsRead 已读回执、2118/2131 多端同步事件）
`referid` 恰为 0，绕过了 `handle_callback` 里 `referid != 0` 那道闸门，被当普通
消息落库。已在 `app/ipad_sync.py` 侧根治（`CONTROL_EVENT_MSG_TYPES` +
`_has_visible_content` 双闸门），本脚本负责清理修复前留下的存量脏数据。

删除口径与线上判定完全一致（前端 `messageVisibility.ts` 同规则）：
  A. 控制/回执类 msg_type ∈ {2001, 2118, 2131} 且无媒体 URL
     （含历史误判为「表情」的 content='[表情]' 脏行）；
  B. 任意 msg_type：正文剔除控制字符后为空，且无媒体 URL
     （覆盖 1002/1003/1023/2055/2063 等未文档化信令与空正文行）。
携带 media_url 的一律保留（图片/动画表情不误伤）。

用法（默认 dry-run，只统计不删除）：
    python3 scripts/cleanup_empty_bubbles.py
    python3 scripts/cleanup_empty_bubbles.py --db database/morphix_mvp.db
真正执行删除（会先备份数据库文件）：
    python3 scripts/cleanup_empty_bubbles.py --apply
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 与 app/ipad_sync.py CONTROL_EVENT_MSG_TYPES 保持一致。
CONTROL_EVENT_MSG_TYPES: tuple[int, ...] = (2001, 2118, 2131)

# C0/C1 控制字符（保留 \t \n \r），与后端 `_CONTROL_CHARS_RE` 同规则。
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

DEFAULT_DB = Path(__file__).resolve().parent.parent / "database" / "morphix_mvp.db"


def _is_blank(content: object) -> bool:
    """正文剔除控制字符后是否为空（protobuf 裸字节视为空）。"""
    text = str(content or "")
    return not CONTROL_CHARS_RE.sub("", text).strip()


def _has_media(media_url: object) -> bool:
    """是否携带有效媒体 URL（携带则一律保留）。"""
    return bool(str(media_url or "").strip())


def collect_targets(conn: sqlite3.Connection) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """扫描全表，返回 (控制事件行, 空正文行) 两组待删除记录（无交集）。"""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, msg_type, content, media_url, direction, conversation_id, created_at "
        "FROM messages"
    ).fetchall()
    control_rows: list[sqlite3.Row] = []
    blank_rows: list[sqlite3.Row] = []
    for row in rows:
        if _has_media(row["media_url"]):
            continue
        if int(row["msg_type"] or 0) in CONTROL_EVENT_MSG_TYPES:
            control_rows.append(row)
        elif _is_blank(row["content"]):
            blank_rows.append(row)
    return control_rows, blank_rows


def summarize(rows: list[sqlite3.Row], title: str) -> None:
    """按 msg_type 打印分组统计，便于人工核对后再决定是否执行。"""
    print(f"\n[{title}] 共 {len(rows)} 条")
    if not rows:
        return
    buckets: dict[int, int] = {}
    for row in rows:
        key = int(row["msg_type"] or 0)
        buckets[key] = buckets.get(key, 0) + 1
    for msg_type in sorted(buckets):
        print(f"    msg_type={msg_type:<6} {buckets[msg_type]:>5} 条")


def main() -> int:
    parser = argparse.ArgumentParser(description="清理 messages 表空气泡脏数据")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 数据库路径")
    parser.add_argument("--apply", action="store_true", help="真正执行删除（默认仅统计）")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在：{db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        control_rows, blank_rows = collect_targets(conn)
        print(f"数据库：{db_path}\nmessages 总行数：{total}")
        summarize(control_rows, "A. 控制/回执类事件（2001/2118/2131，无媒体）")
        summarize(blank_rows, "B. 正文为空且无媒体（含 protobuf 裸字节）")
        doomed = [row["id"] for row in control_rows] + [row["id"] for row in blank_rows]
        print(f"\n合计待删除：{len(doomed)} 条，删除后剩余：{total - len(doomed)} 条")

        if not args.apply:
            print("\n当前为 dry-run，未做任何修改。确认无误后加 --apply 执行删除。")
            return 0
        if not doomed:
            print("\n无需清理。")
            return 0

        backup = db_path.with_name(
            f"{db_path.stem}.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}{db_path.suffix}"
        )
        shutil.copy2(db_path, backup)
        print(f"\n已备份数据库 → {backup}")
        conn.executemany("DELETE FROM messages WHERE id = ?", [(mid,) for mid in doomed])
        conn.commit()
        left = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        print(f"删除完成，messages 剩余 {left} 条。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

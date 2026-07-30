"""Fix 1 一次性数据修正脚本。

把已绑定账号 acc_35ade9b6（ipad_uuid=1567d39bfac53d26fc70c1c709bcb22e）的错误
account_name（「企业微信-1567d3」）与空的 ipad_user_info（{}）修正为真实昵称。

做法：
- 调用真实 iPad 协议服务 POST /wxwork/GetRunClientInfo {"uuid": ...}
- 从 data.userInfo 取 nickname（兜底 englishName/realname/acctid）
- UPDATE channel_accounts SET account_name=?, ipad_user_info=? WHERE ipad_uuid=?
- 打印更新前后的值

仅做数据修正，不删库、不重启后端。运行：
    cd project/backend && .venv/bin/python fix1_account_name.py
"""
from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from typing import Any

# 与 app/config.py 解析出的数据库路径一致（仓库根/database/morphix_mvp.db）。
DB_PATH = "/Users/stevenmac/Desktop/工作目录/Morphix/database/morphix_mvp.db"
IPAD_BASE = "http://47.94.7.218:9912"
UUID = "1567d39bfac53d26fc70c1c709bcb22e"


def fetch_user_info(uuid: str) -> dict[str, Any]:
    """调用真实 iPad 协议服务取 userInfo（兼容 {"data": {...}} 与 {...} 两种信封）。"""
    url = f"{IPAD_BASE}/wxwork/GetRunClientInfo"
    req = urllib.request.Request(
        url,
        data=json.dumps({"uuid": uuid}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    body = payload.get("data", payload) if isinstance(payload.get("data"), dict) else payload
    return body.get("userInfo") or {}


def pick_name(user_info: dict[str, Any]) -> str | None:
    """按协议字段优先级取真实昵称（见 Fix 1 字段优先级）。"""
    for key in ("nickname", "englishName", "realname", "acctid"):
        val = user_info.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        row = conn.execute(
            "SELECT account_name, ipad_user_info FROM channel_accounts WHERE ipad_uuid = ?",
            (UUID,),
        ).fetchone()
        if row is None:
            print(f"[ERROR] 未找到 ipad_uuid={UUID} 的账号，终止。")
            return

        before_name = row["account_name"]
        before_info = row["ipad_user_info"]
        print(f"[BEFORE] account_name  = {before_name!r}")
        print(f"[BEFORE] ipad_user_info = {before_info!r}")

        try:
            user_info = fetch_user_info(UUID)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"[ERROR] 调用真实 iPad 服务失败：{exc}")
            return

        name = pick_name(user_info) or f"企业微信-{UUID[:6]}"
        print(f"[API]    userInfo = {json.dumps(user_info, ensure_ascii=False)}")
        print(f"[API]    解析昵称 = {name!r}")

        info_str = json.dumps(user_info, ensure_ascii=False)
        cur = conn.execute(
            "UPDATE channel_accounts SET account_name = ?, ipad_user_info = ? WHERE ipad_uuid = ?",
            (name, info_str, UUID),
        )
        conn.commit()
        print(f"[UPDATE] 影响行数 = {cur.rowcount}")

        after = conn.execute(
            "SELECT account_name, ipad_user_info FROM channel_accounts WHERE ipad_uuid = ?",
            (UUID,),
        ).fetchone()
        print(f"[AFTER]  account_name  = {after['account_name']!r}")
        print(f"[AFTER]  ipad_user_info = {after['ipad_user_info']!r}")
        print("[OK] 修正完成。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

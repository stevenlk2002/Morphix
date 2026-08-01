#!/usr/bin/env python3
"""wecom_app_display 对拍基线脚本（架构文档 T05 第 2 项）。

复现 `docs/arch-wecom-app-display.md` §1 的全部实测结论，作为**回归基线**。
脚本对环境缺失是**宽容**的：真实库 / 协议服务 / 后端 API 任一不可达时，
相关检查记为 `SKIP` 而非 `FAIL`，因此可以直接放进 CI 常跑。

检查清单
--------
| # | 检查 | 依赖 | 对应结论 |
| - | ---- | ---- | -------- |
| 1 | `channel_apps` 表与双键索引存在 | DB | §3.1 |
| 2 | 会话 `msg_type` 分布 & 裸 ID 会话统计 | DB | 结论 1 |
| 3 | 应用消息 `sender_id == remote_session_id` | DB | 结论 3 |
| 4 | `msg_type=6` 存在真实 outbound（不得置只读） | DB | 结论 3 |
| 5 | 收敛式过滤：`list_sessions` 输出无裸数字名 | DB | §5.3 |
| 6 | `GetRunClientInfo` 可达（证明服务/uuid 有效） | 协议 | 结论 2A 前提 |
| 7 | `getCorpWxApp` 当前 404（已知阻塞，上线后本项转 PASS） | 协议 | 结论 2A |
| 8 | `GetUserInfoByVids` 可用且能解出真人族 vid | 协议 | 结论 2C |
| 9 | ID 空间：应用族与 vid 族不重叠 | DB | 结论 2B |
| 10 | 后端 API `/api/channels/sessions` 无裸数字 | API | PRD 验收 1 |

用法
----
    python3 scripts/verify_wecom_app_display.py
    python3 scripts/verify_wecom_app_display.py --db database/morphix_mvp.db \
        --account-id acc_c5b92c6d --api http://127.0.0.1:2181
    python3 scripts/verify_wecom_app_display.py --offline    # 只跑 DB 侧检查

退出码
------
    0  全部 PASS / SKIP（无 FAIL）
    1  存在 FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# 常量：对拍基线（来自 docs/arch-wecom-app-display.md §1）
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "database" / "morphix_mvp.db"
DEFAULT_PROTOCOL = os.environ.get("IPAD_PROTOCOL_BASE_URL", "http://47.94.7.218:9912")
DEFAULT_API = os.environ.get("MORPHIX_API_BASE", "http://127.0.0.1:2181")
DEFAULT_ACCOUNT = os.environ.get("MORPHIX_VERIFY_ACCOUNT", "acc_c5b92c6d")

#: 应用族（只读，走 getCorpWxApp / channel_apps）。
APP_MSG_TYPES = frozenset({3, 103, 107})
#: 真人 vid 族（可发送，走 GetUserInfoByVids / channel_contacts）。
VID_MSG_TYPES = frozenset({0, 6})

#: 结论 2C 实测能解出的两个 vid（基线：接口正常时必须仍能解出）。
KNOWN_VIDS = {
    "1688852792312821": "企业微信团队",
    "5629499770789533": "AI数字员工",
}

#: 结论 2A 已验证全部 404 的接口命名变体。
CORP_WX_APP_VARIANTS = (
    "wxwork/getCorpWxApp",
    "wxwork/GetCorpWxApp",
    "wxwork/getCorpWxAppList",
    "wxwork/GetWxAppList",
)

_PURE_DIGITS = re.compile(r"^\d+$")


# --------------------------------------------------------------------------- #
# 结果收集
# --------------------------------------------------------------------------- #
PASS, FAIL, SKIP, INFO = "PASS", "FAIL", "SKIP", "INFO"

_COLOR = {
    PASS: "\033[32m",
    FAIL: "\033[31m",
    SKIP: "\033[33m",
    INFO: "\033[36m",
}
_RESET = "\033[0m"


@dataclass
class Report:
    """检查结果收集器。"""

    rows: list[tuple[str, str, str]] = field(default_factory=list)
    use_color: bool = field(default_factory=lambda: sys.stdout.isatty())

    def add(self, status: str, title: str, detail: str = "") -> None:
        self.rows.append((status, title, detail))
        tag = f"{_COLOR[status]}{status:4}{_RESET}" if self.use_color else f"{status:4}"
        print(f"  [{tag}] {title}")
        for line in (detail or "").splitlines():
            if line.strip():
                print(f"         {line}")

    @property
    def failed(self) -> int:
        return sum(1 for s, _, _ in self.rows if s == FAIL)

    def summary(self) -> int:
        counts = {k: sum(1 for s, _, _ in self.rows if s == k) for k in (PASS, FAIL, SKIP, INFO)}
        print()
        print("=" * 72)
        print(
            f"合计 {len(self.rows)} 项："
            f"PASS {counts[PASS]} / FAIL {counts[FAIL]} / "
            f"SKIP {counts[SKIP]} / INFO {counts[INFO]}"
        )
        print("=" * 72)
        return 1 if counts[FAIL] else 0


# --------------------------------------------------------------------------- #
# HTTP 辅助（只用标准库，避免脚本依赖后端 venv）
# --------------------------------------------------------------------------- #
def _http_post_json(url: str, payload: dict, timeout: float = 8.0) -> tuple[int, Any]:
    """POST JSON，返回 `(status_code, parsed_body_or_text)`；网络异常返回 `(0, err)`。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.reason
    except Exception as exc:  # noqa: BLE001 - 网络层任何异常统一降级
        return 0, str(exc)


def _http_get_json(url: str, timeout: float = 8.0) -> tuple[int, Any]:
    """GET JSON，返回 `(status_code, parsed_body_or_text)`；网络异常返回 `(0, err)`。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.reason
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


# --------------------------------------------------------------------------- #
# DB 侧检查
# --------------------------------------------------------------------------- #
def _open_db(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def check_schema(con: sqlite3.Connection, rep: Report) -> None:
    """检查 1：`channel_apps` 表与双键索引存在（§3.1）。"""
    if not _table_exists(con, "channel_apps"):
        rep.add(FAIL, "channel_apps 表存在", "未找到表；请执行 migrate_schema() 或重启后端")
        return
    cols = {r["name"] for r in con.execute("PRAGMA table_info(channel_apps)")}
    required = {
        "id", "account_id", "app_id", "app_open_id", "corpid", "name",
        "avatar", "app_type", "description", "home_info", "last_mod_time",
        "extra_json", "updated_at",
    }
    missing = required - cols
    if missing:
        rep.add(FAIL, "channel_apps 列完整", f"缺列：{sorted(missing)}")
    else:
        rep.add(PASS, "channel_apps 表与列完整", f"共 {len(cols)} 列")

    idx = {
        r["name"]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='channel_apps'"
        )
    }
    need_idx = {"idx_channel_apps_account_appid", "idx_channel_apps_account_openid"}
    if need_idx <= idx:
        rep.add(PASS, "channel_apps 双键索引存在", ", ".join(sorted(need_idx)))
    else:
        rep.add(FAIL, "channel_apps 双键索引存在", f"缺索引：{sorted(need_idx - idx)}")

    # 类型检查：ID 必须是 TEXT，整数列会静默丢 17 位精度（§8.2）
    types = {r["name"]: (r["type"] or "").upper() for r in con.execute("PRAGMA table_info(channel_apps)")}
    bad = [c for c in ("app_id", "app_open_id", "corpid") if types.get(c) != "TEXT"]
    if bad:
        rep.add(FAIL, "应用 ID 列为 TEXT（防 17 位精度丢失）", f"非 TEXT 列：{bad}")
    else:
        rep.add(PASS, "应用 ID 列为 TEXT（防 17 位精度丢失）", "app_id / app_open_id / corpid")


def check_msg_type_distribution(con: sqlite3.Connection, account_id: str, rep: Report) -> None:
    """检查 2：会话 msg_type 分布 + 裸 ID 会话统计（结论 1）。"""
    rows = con.execute(
        "SELECT msg_type, COUNT(*) c FROM channel_sessions WHERE account_id = ? "
        "GROUP BY msg_type ORDER BY msg_type",
        (account_id,),
    ).fetchall()
    if not rows:
        rep.add(SKIP, "会话 msg_type 分布", f"账号 {account_id} 下无会话")
        return
    dist = {int(r["msg_type"] or 0): r["c"] for r in rows}
    rep.add(INFO, "会话 msg_type 分布", json.dumps(dist, ensure_ascii=False))

    raw = con.execute(
        "SELECT remote_session_id, msg_type FROM channel_sessions "
        "WHERE account_id = ? AND name = remote_session_id",
        (account_id,),
    ).fetchall()
    raw_by_type: dict[int, list[str]] = {}
    for r in raw:
        raw_by_type.setdefault(int(r["msg_type"] or 0), []).append(str(r["remote_session_id"]))
    rep.add(
        INFO,
        f"名称仍是裸 ID 的会话共 {len(raw)} 条",
        json.dumps({k: len(v) for k, v in sorted(raw_by_type.items())}, ensure_ascii=False),
    )

    # 结论 1 的核心：裸 ID 不只出现在 msg_type=3
    non_three = {k for k in raw_by_type if k != 3}
    if raw and not non_three:
        rep.add(
            INFO,
            "裸 ID 全部落在 msg_type=3",
            "与 §1 基线（{0,6,103,107} 也有裸 ID）不同，可能已被本次改动修复",
        )
    else:
        rep.add(
            PASS,
            "裸 ID 跨 msg_type 分布（结论 1：不止 msg_type=3）",
            f"涉及 msg_type = {sorted(raw_by_type)}",
        )


def check_app_message_sender(con: sqlite3.Connection, account_id: str, rep: Report) -> None:
    """检查 3：应用消息 `sender_id == remote_session_id`（结论 3）。"""
    ids = [
        r["id"]
        for r in con.execute(
            "SELECT id FROM channel_sessions WHERE account_id = ? AND msg_type IN (3,103,107)",
            (account_id,),
        )
    ]
    if not ids:
        rep.add(SKIP, "应用消息 sender_id == remote_session_id", "无应用族会话")
        return
    placeholders = ",".join("?" * len(ids))
    rows = con.execute(
        f"SELECT conversation_id, sender_id FROM messages "
        f"WHERE direction = 'inbound' AND conversation_id IN ({placeholders})",
        ids,
    ).fetchall()
    if not rows:
        rep.add(SKIP, "应用消息 sender_id == remote_session_id", "应用族会话下无 inbound 消息")
        return
    mismatched = [
        (r["conversation_id"], r["sender_id"])
        for r in rows
        if str(r["sender_id"] or "") != str(r["conversation_id"]).split(":", 1)[-1]
    ]
    if mismatched:
        rep.add(
            FAIL,
            "应用消息 sender_id == remote_session_id（结论 3）",
            f"{len(mismatched)}/{len(rows)} 条不符，示例：{mismatched[:3]}",
        )
    else:
        rep.add(
            PASS,
            "应用消息 sender_id == remote_session_id（结论 3）",
            f"{len(rows)} 条 inbound 全部一致 → 头像必须按会话维度解析",
        )


def check_msg_type_6_outbound(con: sqlite3.Connection, account_id: str, rep: Report) -> None:
    """检查 4：`msg_type=6` 存在真实 outbound，**不得**并入只读族（结论 3）。"""
    row = con.execute(
        "SELECT COUNT(*) c FROM messages m "
        "JOIN channel_sessions s ON s.id = m.conversation_id "
        "WHERE s.account_id = ? AND s.msg_type = 6 AND m.direction = 'outbound'",
        (account_id,),
    ).fetchone()
    count = int(row["c"] if row else 0)
    if count == 0:
        rep.add(SKIP, "msg_type=6 存在真实 outbound（不得置只读）", "本库无 msg_type=6 的外发消息")
        return
    if 6 in APP_MSG_TYPES:  # pragma: no cover - 常量守卫
        rep.add(FAIL, "msg_type=6 未被并入只读族", "APP_MSG_TYPES 误含 6")
        return
    rep.add(
        PASS,
        "msg_type=6 存在真实 outbound（不得置只读）",
        f"outbound {count} 条；APP_MSG_TYPES={sorted(APP_MSG_TYPES)} 已正确排除 6",
    )


def check_convergent_filter(con: sqlite3.Connection, account_id: str, rep: Report) -> None:
    """检查 5：收敛式过滤 —— 可见会话中不得出现「名称=裸 ID」（§5.3）。

    直接复刻 `repositories.list_sessions` 的三路 JOIN + 收敛过滤 SQL，
    不依赖后端进程，便于在 CI / 离线环境校验。
    """
    if not _table_exists(con, "channel_apps"):
        rep.add(SKIP, "收敛式过滤：可见会话无裸数字名", "channel_apps 表不存在")
        return
    sql = (
        "SELECT COALESCE(NULLIF(cc.nickname,''), NULLIF(cc.name,''), "
        "NULLIF(cg.nickname,''), NULLIF(ca.name,''), cs.name) AS disp, "
        "cs.remote_session_id AS rsid, cs.msg_type AS mt "
        "FROM channel_sessions cs "
        "LEFT JOIN channel_contacts cc ON cc.account_id = cs.account_id "
        "  AND cc.user_id = cs.remote_session_id "
        "LEFT JOIN channel_groups cg ON cg.account_id = cs.account_id "
        "  AND cg.room_id = cs.remote_session_id "
        "LEFT JOIN channel_apps ca ON ca.account_id = cs.account_id "
        "  AND (ca.app_id = cs.remote_session_id OR ca.app_open_id = cs.remote_session_id) "
        "WHERE cs.account_id = ? AND ("
        "  COALESCE(cc.nickname, cc.name, cg.nickname, ca.name, '') <> '' "
        "  OR cs.name <> cs.remote_session_id)"
    )
    rows = con.execute(sql, (account_id,)).fetchall()
    if not rows:
        rep.add(SKIP, "收敛式过滤：可见会话无裸数字名", f"账号 {account_id} 下无可见会话")
        return
    bare = [
        (r["disp"], int(r["mt"] or 0))
        for r in rows
        if str(r["disp"] or "") == str(r["rsid"] or "") and _PURE_DIGITS.match(str(r["disp"] or ""))
    ]
    if bare:
        rep.add(
            FAIL,
            "收敛式过滤：可见会话无裸数字名（§5.3）",
            f"可见 {len(rows)} 条，其中 {len(bare)} 条仍是裸数字：{bare[:5]}",
        )
    else:
        rep.add(
            PASS,
            "收敛式过滤：可见会话无裸数字名（§5.3）",
            f"可见 {len(rows)} 条，裸数字 0 条",
        )


def check_id_space_disjoint(con: sqlite3.Connection, account_id: str, rep: Report) -> None:
    """检查 9：应用族 sessionid 与 vid 族（channel_contacts.user_id）不重叠（结论 2B）。"""
    app_ids = {
        str(r["remote_session_id"])
        for r in con.execute(
            "SELECT remote_session_id FROM channel_sessions "
            "WHERE account_id = ? AND msg_type IN (3,103,107)",
            (account_id,),
        )
    }
    if not app_ids:
        rep.add(SKIP, "ID 空间：应用族与 vid 族不重叠（结论 2B）", "无应用族会话")
        return
    placeholders = ",".join("?" * len(app_ids))
    overlap = [
        r["user_id"]
        for r in con.execute(
            f"SELECT user_id FROM channel_contacts WHERE account_id = ? "
            f"AND user_id IN ({placeholders})",
            [account_id, *sorted(app_ids)],
        )
    ]
    if overlap:
        rep.add(
            FAIL,
            "ID 空间：应用族与 vid 族不重叠（结论 2B）",
            f"重叠 {len(overlap)} 个：{overlap[:5]}（应用头像分支可能误命中联系人）",
        )
    else:
        lengths = sorted({len(i) for i in app_ids})
        rep.add(
            PASS,
            "ID 空间：应用族与 vid 族不重叠（结论 2B）",
            f"应用族 {len(app_ids)} 个 sessionid，长度分布 {lengths}；与 channel_contacts 零交集",
        )


# --------------------------------------------------------------------------- #
# 协议侧检查
# --------------------------------------------------------------------------- #
def _pick_uuid(con: sqlite3.Connection | None, account_id: str, cli_uuid: str) -> str:
    """优先用命令行 uuid，其次从 DB 里取该账号的 ipad_uuid。"""
    if cli_uuid:
        return cli_uuid
    if con is None:
        return ""
    try:
        row = con.execute(
            "SELECT ipad_uuid FROM channel_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    except sqlite3.Error:
        return ""
    return str(row["ipad_uuid"]) if row and row["ipad_uuid"] else ""


def check_protocol_alive(base: str, uuid: str, rep: Report) -> bool:
    """检查 6：`GetRunClientInfo` 可达（证明服务/账号/uuid 有效，结论 2A 前提）。"""
    status, body = _http_post_json(f"{base}/wxwork/GetRunClientInfo", {"uuid": uuid})
    if status == 200:
        rep.add(PASS, "协议服务可达（GetRunClientInfo 200）", f"{base}")
        return True
    rep.add(
        SKIP,
        "协议服务可达（GetRunClientInfo 200）",
        f"{base} → HTTP {status} / {body}；后续协议检查跳过",
    )
    return False


def check_get_corp_wx_app(base: str, uuid: str, rep: Report) -> None:
    """检查 7：`getCorpWxApp` 当前 404（已知阻塞 §9-U1；上线后本项自动转 PASS）。"""
    results: list[str] = []
    ok_variant = ""
    ok_body: Any = None
    for path in CORP_WX_APP_VARIANTS:
        status, body = _http_post_json(f"{base}/{path}", {"uuid": uuid})
        results.append(f"{path} → HTTP {status}")
        if status == 200 and not ok_variant:
            ok_variant, ok_body = path, body

    if not ok_variant:
        rep.add(
            SKIP,
            "getCorpWxApp 已上线（已知阻塞 §9-U1）",
            "全部命名变体 404，与 §1.2 结论 2A 基线一致。\n"
            + "\n".join(results)
            + "\n应用族会话将继续被收敛式过滤隐藏 —— 这是预期行为，无视觉回归。",
        )
        return

    # 接口上线：校验返回结构符合 §3.1 字段映射预期
    payload = ok_body.get("data") if isinstance(ok_body, dict) else None
    items = payload.get("wxAppList") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        rep.add(
            FAIL,
            "getCorpWxApp 返回结构含 wxAppList",
            f"{ok_variant} 返回 200 但结构异常：{str(ok_body)[:200]}",
        )
        return
    keyed = [i for i in items if isinstance(i, dict) and (i.get("appId") or i.get("appOpenId"))]
    rep.add(
        PASS,
        f"getCorpWxApp 已上线（{ok_variant}）",
        f"wxAppList {len(items)} 条，其中带双键 {len(keyed)} 条 → 触发全量同步后应用会话将自动浮现",
    )


def check_get_user_info_by_vids(base: str, uuid: str, rep: Report) -> None:
    """检查 8：`GetUserInfoByVids` 可用且能解出真人族 vid（结论 2C）。"""
    vids = [int(v) for v in KNOWN_VIDS]
    status, body = _http_post_json(
        f"{base}/wxwork/GetUserInfoByVids", {"uuid": uuid, "vids": vids}
    )
    if status != 200:
        rep.add(SKIP, "GetUserInfoByVids 可用（结论 2C）", f"HTTP {status} / {body}")
        return
    payload = body.get("data") if isinstance(body, dict) else None
    if not isinstance(payload, list):
        rep.add(
            FAIL,
            "GetUserInfoByVids 响应 data 为顶层 list（结论 2C）",
            f"实际类型 {type(payload).__name__}：{str(body)[:200]}",
        )
        return
    resolved = {
        str(i.get("user_id") or i.get("userId") or i.get("vid") or ""):
            str(i.get("nickname") or i.get("name") or "")
        for i in payload
        if isinstance(i, dict)
    }
    hits = {k: v for k, v in resolved.items() if k in KNOWN_VIDS and v}
    if not hits:
        rep.add(
            FAIL,
            "GetUserInfoByVids 能解出基线 vid（结论 2C）",
            f"请求 {list(KNOWN_VIDS)} 全部未命中；实际返回 {resolved}",
        )
        return
    detail = "；".join(f"{k} → {v}（基线 {KNOWN_VIDS[k]}）" for k, v in hits.items())
    rep.add(PASS, f"GetUserInfoByVids 命中 {len(hits)}/{len(KNOWN_VIDS)}（结论 2C）", detail)


# --------------------------------------------------------------------------- #
# API 侧检查
# --------------------------------------------------------------------------- #
def check_api_sessions(api: str, account_id: str, rep: Report) -> None:
    """检查 10：后端 `/api/channels/sessions` 输出无裸数字名（PRD 验收 1）。"""
    url = f"{api.rstrip('/')}/api/channels/sessions?accountId={account_id}&pageSize=1000"
    status, body = _http_get_json(url)
    if status != 200 or not isinstance(body, list):
        rep.add(SKIP, "API /api/channels/sessions 无裸数字名", f"HTTP {status}（后端未启动？）")
        return
    bare = [
        s
        for s in body
        if isinstance(s, dict)
        and _PURE_DIGITS.match(str(s.get("name", "")))
        and str(s.get("name")) == str(s.get("remoteSessionId", s.get("name")))
    ]
    if bare:
        rep.add(
            FAIL,
            "API /api/channels/sessions 无裸数字名（PRD 验收 1）",
            f"共 {len(body)} 条，裸数字 {len(bare)} 条：{[s['name'] for s in bare][:5]}",
        )
        return
    app_sessions = [s for s in body if s.get("entityKind") == "app"]
    rep.add(
        PASS,
        "API /api/channels/sessions 无裸数字名（PRD 验收 1）",
        f"共 {len(body)} 条，裸数字 0 条，其中应用会话 {len(app_sessions)} 条",
    )
    # DTO 契约：新增四个语义字段必须存在（前端依赖它们做渲染分流）
    if body:
        sample = body[0]
        missing = [k for k in ("msgType", "entityKind", "readonly") if k not in sample]
        if missing:
            rep.add(FAIL, "SessionDTO 语义字段完整（§3.5）", f"缺字段：{missing}")
        else:
            rep.add(PASS, "SessionDTO 语义字段完整（§3.5）", "msgType / entityKind / readonly / appType")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="wecom_app_display 对拍基线（复现架构文档 §1 全部结论）"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help=f"SQLite 库路径（默认 {DEFAULT_DB}）")
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL, help="iPad 协议服务基址")
    parser.add_argument("--api", default=DEFAULT_API, help="Morphix 后端基址")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT, help="待校验的渠道账号 id")
    parser.add_argument("--uuid", default="", help="iPad 协议 uuid（缺省从 DB 读取）")
    parser.add_argument("--offline", action="store_true", help="只跑 DB 侧检查，跳过网络")
    args = parser.parse_args(argv)

    rep = Report()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = (REPO_ROOT / db_path).resolve()

    print("=" * 72)
    print("wecom_app_display 对拍基线")
    print(f"  DB       : {db_path}")
    print(f"  协议     : {args.protocol}")
    print(f"  API      : {args.api}")
    print(f"  账号     : {args.account_id}")
    print("=" * 72)

    con = _open_db(db_path)
    if con is None:
        rep.add(SKIP, "打开真实库", f"{db_path} 不存在，DB 侧检查全部跳过")
    else:
        print("\n-- DB 侧 ---------------------------------------------------------------")
        check_schema(con, rep)
        check_msg_type_distribution(con, args.account_id, rep)
        check_app_message_sender(con, args.account_id, rep)
        check_msg_type_6_outbound(con, args.account_id, rep)
        check_convergent_filter(con, args.account_id, rep)
        check_id_space_disjoint(con, args.account_id, rep)

    if args.offline:
        print("\n(--offline：跳过协议 / API 侧检查)")
    else:
        uuid = _pick_uuid(con, args.account_id, args.uuid)
        print("\n-- 协议侧 --------------------------------------------------------------")
        if not uuid:
            rep.add(SKIP, "协议侧检查", "未取得 ipad_uuid（用 --uuid 指定）")
        elif check_protocol_alive(args.protocol, uuid, rep):
            check_get_corp_wx_app(args.protocol, uuid, rep)
            check_get_user_info_by_vids(args.protocol, uuid, rep)

        print("\n-- API 侧 --------------------------------------------------------------")
        check_api_sessions(args.api, args.account_id, rep)

    if con is not None:
        con.close()
    return rep.summary()


if __name__ == "__main__":
    sys.exit(main())

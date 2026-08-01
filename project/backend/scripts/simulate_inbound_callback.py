#!/usr/bin/env python3
"""入向回调联调自测脚本（不依赖公网隧道）。

用途
----
把「对方回复的消息收不到」这一现象拆成两段独立验证：

1. **代码链路**（本脚本默认模式 ``--mode isolated``）：在一个全新的临时 SQLite
   库里造一个托管账号 + 一个 1:1 会话，用 FastAPI TestClient 直接 POST 一条真实
   协议形态的入向回调到 ``/wxwork/callback``，然后断言：
   - HTTP 200 且 ``upserted == 1``；
   - ``messages`` 表出现 direction='inbound' 且 ``conversation_id`` 等于会话主键；
   - ``GET /api/channels/{account_id}/messages?conversationId=...`` 能查到该消息。
   全程零外网、零生产库写入。

2. **环境链路**（``--mode probe``）：只读探测本地后端与公网隧道是否可达，
   不写任何数据（用一个不存在的 uuid，handler 会直接返回「未知账号」）。

因此：
- ``isolated`` 通过 + ``probe`` 隧道不通 → 代码没问题，是内网穿透隧道断了。
- ``isolated`` 失败 → 回调解析/落库/查询链路存在代码缺陷。

用法
----
    cd project/backend
    .venv/bin/python scripts/simulate_inbound_callback.py                # 隔离库自测
    .venv/bin/python scripts/simulate_inbound_callback.py --mode probe   # 环境探测
    .venv/bin/python scripts/simulate_inbound_callback.py --mode all     # 两者都跑

退出码：0 = 全部通过；1 = 存在失败项。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# 保证以 `python scripts/xxx.py` 直接运行时能 import 到 app 包。
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# 必须早于 import app：settings 在导入时读取一次环境变量。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "mock")
os.environ.setdefault("MORPHIX_DEV", "1")

DEFAULT_LOCAL_BASE = "http://127.0.0.1:2181"
DEFAULT_TUNNEL_URL = "https://123wx9061na45.vicp.fun:443/wxwork/callback"

# 隔离库中使用的假身份（与生产账号无关，避免误触真实数据）。
SIM_UUID = "sim-uuid-inbound-0001"
SIM_ACCOUNT_VID = "1688850473951280"
SIM_FRIEND_ID = "7881302555913738"
SIM_SERVER_ID = 990001


def _ok(msg: str) -> None:
    print(f"  \033[32m[PASS]\033[0m {msg}")


def _fail(msg: str) -> None:
    print(f"  \033[31m[FAIL]\033[0m {msg}")


def _info(msg: str) -> None:
    print(f"  [info] {msg}")


def _inbound_payload(server_id: int = SIM_SERVER_ID, content: str = "对方回复：收到了") -> dict:
    """构造 IPad 协议「下发-消息接收」真实形态的 1:1 文本入向消息体。"""
    return {
        "flag": 16777216,
        "receiver": int(SIM_ACCOUNT_VID),
        "sender_name": "",
        "is_room": 0,
        "server_id": server_id,
        "content": content,
        "issync": False,
        "send_time": 1724024152,
        "sender": int(SIM_FRIEND_ID),
        "referid": 0,
        "app_info": "3304183318011621608",
        "readuinscount": 0,
        "msg_id": 1011720,
        "msgType": 2,
        "atList": [],
    }


def _session_row(account_id: str, remote_id: str) -> dict:
    """构造 channel_sessions 行（id = {account_id}:{remote_id}，与生产约定一致）。"""
    return {
        "id": f"{account_id}:{remote_id}",
        "account_id": account_id,
        "contact_id": None,
        "name": "联调好友",
        "channel": "企业微信",
        "channel_type": "wecom",
        "last_message": "",
        "last_time": "",
        "unread_count": 0,
        "read_status": "read",
        "hosted_status": "unhosted",
        "hosted_bot_id": None,
        "owner": "",
        "online_status": "online",
        "session_type": "好友",
        "external_tag": "外部",
        "add_time": "",
        "hosting_chain": "-",
        "remote_session_id": remote_id,
        "msg_type": 0,
        "begin_msg_seq": "",
    }


def run_isolated() -> bool:
    """隔离库端到端验证入向回调链路。返回 True 表示全部断言通过。"""
    from fastapi.testclient import TestClient

    import app.database as db_mod
    from app import schema as schema_mod
    from app.database import SQLiteBackend, set_backend
    from app.main import app
    from app.repositories import ChannelMgmtRepository

    print("\n=== [1/2] 隔离库回调链路自测（零外网、零生产库写入） ===")
    passed = True
    with tempfile.TemporaryDirectory() as tmp:
        backend = SQLiteBackend(Path(tmp) / "simulate_inbound.db")
        schema_mod.init_schema(backend)
        prev = db_mod._backend
        set_backend(backend)
        try:
            repo = ChannelMgmtRepository(backend)
            account = repo.create_account_with_ipad(
                channel_type="wecom",
                protocol="ipad",
                team_id="team-sim",
                name="入向联调账号",
                ipad_uuid=SIM_UUID,
                ipad_user_info={"userId": SIM_ACCOUNT_VID},
                host_status="hosted",
            )
            account_id = account["id"]
            session_id = f"{account_id}:{SIM_FRIEND_ID}"
            repo.upsert_channel_session(_session_row(account_id, SIM_FRIEND_ID))
            _info(f"account_id={account_id}  conversationId={session_id}")

            wrapper = {
                "uuid": SIM_UUID,
                # 真实协议 json 字段为字符串，需二次解码。
                "json": json.dumps(_inbound_payload(), ensure_ascii=False),
                "type": "102000",
            }
            with TestClient(app) as client:
                resp = client.post("/wxwork/callback", json=wrapper)
                # 断言 ①：回调返回 200 且落库 1 条
                if resp.status_code == 200:
                    _ok(f"POST /wxwork/callback → 200 {resp.json()}")
                else:
                    passed = False
                    _fail(f"POST /wxwork/callback → {resp.status_code} {resp.text}")
                body = resp.json() if resp.status_code == 200 else {}
                if body.get("upserted") == 1:
                    _ok("handle_callback upserted == 1")
                else:
                    passed = False
                    _fail(f"handle_callback upserted != 1，实际 {body!r}")

                # 断言 ②：messages 表出现 inbound 行，且 conversation_id 对齐会话主键
                row = backend.query_one(
                    "SELECT * FROM messages WHERE conversation_id = ? AND direction = 'inbound'",
                    (session_id,),
                )
                if row:
                    _ok(
                        "messages 落库 inbound：id=%s conversation_id=%s content=%r"
                        % (row["id"], row["conversation_id"], row["content"])
                    )
                else:
                    passed = False
                    _fail(f"messages 表未查到 conversation_id={session_id} 的 inbound 行")
                expect_id = f"chmsg-{session_id}:{SIM_SERVER_ID}"
                if row and row["id"] == expect_id:
                    _ok(f"幂等键符合约定 {expect_id}")
                elif row:
                    passed = False
                    _fail(f"幂等键不符：期望 {expect_id}，实际 {row['id']}")

                # 断言 ③：前端读取端点能查到
                api = client.get(
                    f"/api/channels/{account_id}/messages",
                    params={"conversationId": session_id, "limit": 20},
                )
                if api.status_code == 200:
                    items = api.json()
                    hit = [m for m in items if m.get("direction") == "inbound"]
                    if hit:
                        _ok(
                            "GET /api/channels/{id}/messages 命中 %d 条 inbound，首条=%r"
                            % (len(hit), hit[0].get("content"))
                        )
                    else:
                        passed = False
                        _fail(f"消息列表接口未返回 inbound 消息，实际 {items!r}")
                else:
                    passed = False
                    _fail(f"GET 消息列表 → {api.status_code} {api.text}")

                # 断言 ④：重复回调幂等
                dup = client.post("/wxwork/callback", json=wrapper)
                if dup.status_code == 200 and dup.json().get("upserted") == 0:
                    _ok("重复回调幂等（upserted == 0）")
                else:
                    passed = False
                    _fail(f"重复回调未幂等：{dup.status_code} {dup.text}")
        finally:
            set_backend(prev)
    return passed


def _http_probe(url: str, method: str = "GET", body: dict | None = None, timeout: int = 8):
    """返回 (status_code, text)；不可达时 status_code 为 0。"""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")[:400]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:400]
    except Exception as exc:  # noqa: BLE001  网络不可达 / TLS 失败 / 超时
        return 0, f"{type(exc).__name__}: {exc}"


def run_probe(local_base: str, tunnel_url: str) -> bool:
    """只读探测本地后端与公网隧道可达性（不写任何数据）。"""
    print("\n=== [2/2] 环境可达性探测（只读，不写库） ===")
    passed = True

    code, _ = _http_probe(f"{local_base}/openapi.json")
    if code == 200:
        _ok(f"本地后端可达 {local_base}")
    else:
        passed = False
        _fail(f"本地后端不可达 {local_base}（code={code}）→ 请检查 uvicorn / launchd")

    # 用不存在的 uuid 探测：handler 直接返回「未知账号」，不写任何数据。
    probe_body = {
        "uuid": "__probe_not_a_real_uuid__",
        "type": "102000",
        "json": json.dumps({"sender": 1, "content": "probe", "server_id": 1, "referid": 0}),
    }
    code, text = _http_probe(f"{local_base}/wxwork/callback", "POST", probe_body)
    if code == 200 and "未知账号" in text:
        _ok(f"本地回调路由存活 POST {local_base}/wxwork/callback → 200 {text}")
    else:
        passed = False
        _fail(f"本地回调路由异常 code={code} body={text}")

    code, text = _http_probe(tunnel_url, "POST", probe_body)
    if code == 200:
        _ok(f"公网隧道可达 {tunnel_url} → 200 {text}")
    else:
        passed = False
        _fail(
            f"公网隧道不可达 {tunnel_url}（code={code}, {text}）\n"
            "         → 入向消息无法到达本服务。请启动内网穿透（花生壳）客户端，\n"
            "           或更换公网域名并同步更新 IPAD_CALLBACK_PUBLIC_URL 后重启后端。"
        )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description="入向回调联调自测（不依赖公网隧道）")
    parser.add_argument(
        "--mode",
        choices=["isolated", "probe", "all"],
        default="isolated",
        help="isolated=隔离库代码链路自测（默认）；probe=环境可达性探测；all=两者都跑",
    )
    parser.add_argument("--local-base", default=DEFAULT_LOCAL_BASE, help="本地后端基址")
    parser.add_argument("--tunnel-url", default=DEFAULT_TUNNEL_URL, help="公网回调地址")
    args = parser.parse_args()

    results: list[bool] = []
    if args.mode in ("isolated", "all"):
        results.append(run_isolated())
    if args.mode in ("probe", "all"):
        results.append(run_probe(args.local_base, args.tunnel_url))

    print("\n=== 结论 ===")
    if all(results):
        print("  全部通过。")
        return 0
    print("  存在失败项，详见上方 [FAIL] 行。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

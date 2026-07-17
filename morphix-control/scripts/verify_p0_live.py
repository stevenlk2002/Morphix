"""实时 P0 主链路验证（针对真实运行的 morphix-control 服务）。

与 tests/test_smoke.py（离线 hermetic）不同，本脚本连接一个**已在运行**的
morphix-control 实例（默认 http://localhost:8000），自动通过 dev-bootstrap
签发令牌（无硬编码 token），跑通 P0 主链路并以 ✅/❌ 汇总。

用法:
    python scripts/verify_p0_live.py                 # 默认 http://localhost:8000
    BASE_URL=http://localhost:8000 python scripts/verify_p0_live.py
    python scripts/verify_p0_live.py --base-url http://localhost:9000

依赖: httpx（与项目测试依赖一致，无需额外安装）
"""
from __future__ import annotations

import argparse
import os
import sys
import time


class BackendUnavailable(Exception):
    """后端服务无法连接（未在运行或地址错误）。致命错误，应中止而非记为步骤失败。"""

try:
    import httpx
except ImportError:
    sys.stderr.write("缺少 httpx，请先: pip install httpx\n")
    sys.exit(2)


class Verify:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.ok = 0
        self.fail = 0
        self.tokens: dict[str, str] = {}
        self.device_id: str | None = None
        self.device_token: str | None = None
        self.channel_account_id: str | None = None
        self.conversation_id: str | None = None

    # ---- helpers ----
    def step(self, name: str, fn) -> bool:
        try:
            fn()
            self.ok += 1
            print(f"  ✅ {name}")
            return True
        except BackendUnavailable:
            raise  # 致命错误，冒泡到 main 统一处理
        except AssertionError as e:
            self.fail += 1
            print(f"  ❌ {name}  -> {e}")
            return False
        except Exception as e:  # noqa: BLE001
            self.fail += 1
            print(f"  ❌ {name}  -> {type(e).__name__}: {e}")
            return False

    def post(self, path: str, json=None, headers=None):
        r = httpx.post(f"{self.base}{path}", json=json, headers=headers or {}, timeout=10)
        assert r.status_code < 500, f"{r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body.get("success") is True, f"{r.status_code} {body}"
        return r, body["data"]

    def get(self, path: str, params=None, headers=None):
        r = httpx.get(f"{self.base}{path}", params=params, headers=headers or {}, timeout=10)
        assert r.status_code < 500, f"{r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body.get("success") is True, f"{r.status_code} {body}"
        return r, body["data"]

    # ---- steps ----
    def health(self):
        try:
            r = httpx.get(f"{self.base}/api/health", timeout=5)
        except Exception as e:  # noqa: BLE001  # 连接拒绝/超时均视为后端未就绪
            raise BackendUnavailable(f"{self.base} -> {type(e).__name__}: {e}") from e
        assert r.status_code == 200 and r.json().get("status") == "ok", r.text

    def bootstrap(self):
        r, d = self.post(
            "/api/auth/dev-bootstrap",
            json={"project_id": "01JPROJECT", "scopes": ["control", "runtime", "internal", "provisioning"]},
            headers={"X-Device-Provisioning-Key": "dev-provisioning-key"},
        )
        assert d["control_token"] and d["runtime_token"] and d["internal_token"]
        assert d["provisioning_key"]
        self.tokens = d

    def register_device(self):
        r, d = self.post(
            "/api/device/registrations",
            json={
                "bindCode": "BIND-LIVE-001",
                "projectId": "01JPROJECT",
                "channelType": "wechat",
                "accountType": "personal",
                "installFingerprint": "android-14:pixel7:live",
                "deviceMeta": {"brand": "Google", "model": "Pixel 7", "osVersion": "Android 14", "appVersion": "0.1.0"},
            },
            headers={"X-Device-Provisioning-Key": self.tokens["provisioning_key"]},
        )
        assert d["deviceId"] and d["deviceToken"] and d["channelAccountId"]
        self.device_id = d["deviceId"]
        self.device_token = d["deviceToken"]
        self.channel_account_id = d["channelAccountId"]

    def heartbeat(self):
        r, d = self.post(
            "/api/device/heartbeats",
            json={
                "deviceId": self.device_id,
                "reportedAt": "2026-07-17T16:00:00+08:00",
                "deviceStatus": "online",
                "accountStatus": "online",
                "commandQueue": {"pendingCount": 0, "runningCount": 0, "retryCount": 0},
            },
            headers={"X-Device-Token": self.device_token},
        )
        assert d["commandPollIntervalSec"] >= 3

    def refresh_token(self):
        r, d = self.post(
            f"/api/device/registrations/{self.device_id}/refresh-token",
            json={"refreshReason": "expiring"},
            headers={"X-Device-Token": self.device_token},
        )
        assert d["deviceToken"] and d["deviceToken"] != self.device_token
        self.device_token = d["deviceToken"]

    def inbound(self):
        r, d = self.post(
            "/api/runtime/inbound-events/messages",
            json={
                "projectId": "01JPROJECT",
                "channelAccountId": self.channel_account_id,
                "deviceId": self.device_id,
                "conversationType": "direct",
                "sourceConversationId": "wx_conv_live",
                "sourceMessageId": f"wx_msg_live_{int(time.time())}",
                "contact": {"externalUid": "wx_user_live", "displayName": "王五"},
                "message": {"messageType": "text", "contentText": "报价多少", "sentAt": "2026-07-17T16:30:00+08:00"},
            },
            headers={"X-Runtime-Token": self.tokens["runtime_token"]},
        )
        assert d["accepted"] is True and d["conversationId"] and d["sessionRuntimeId"]
        self.conversation_id = d["conversationId"]

    def control_views(self):
        r, d = self.get("/api/control/conversations", params={"projectId": "01JPROJECT"})
        assert d["total"] >= 1
        r, d = self.get(f"/api/control/conversations/{self.conversation_id}")
        assert d["handoffStatus"] == "none" and d["currentBot"] is not None
        r, d = self.get(f"/api/control/conversations/{self.conversation_id}/messages")
        assert len(d["items"]) >= 1
        r, d = self.get(f"/api/control/conversations/{self.conversation_id}/runtime")
        assert d["sessionState"] == "WAITING_DEVICE_ACK"
        self.runtime = d

    def device_command_loop(self):
        r, d = self.get(
            "/api/device/commands/pending",
            params={"deviceId": self.device_id},
            headers={"X-Device-Token": self.device_token},
        )
        items = d["items"]
        assert len(items) == 1 and items[0]["commandType"] == "send_message"
        cmd_id = items[0]["commandId"]
        r, d = self.post(
            f"/api/device/commands/{cmd_id}/ack",
            json={"deviceId": self.device_id, "ackedAt": "2026-07-17T16:31:00+08:00"},
            headers={"X-Device-Token": self.device_token},
        )
        assert d["status"] == "acked"
        r, d = self.post(
            f"/api/device/commands/{cmd_id}/complete",
            json={"deviceId": self.device_id, "doneAt": "2026-07-17T16:31:05+08:00", "result": {"ok": True}},
            headers={"X-Device-Token": self.device_token},
        )
        assert d["status"] == "done"

    def audit(self):
        run_id = self.runtime["activeRunId"]
        r, d = self.get(f"/api/control/workflow-runs/{run_id}")
        assert d["status"] == "completed"
        r, d = self.get(f"/api/control/workflow-runs/{run_id}/node-executions")
        assert len(d["items"]) >= 3
        r, d = self.get(f"/api/control/workflow-runs/{run_id}/agent-invocations")
        assert len(d["items"]) >= 1

    def handoff(self):
        cid = self.conversation_id
        r, d = self.post(
            f"/api/control/conversations/{cid}/handoff",
            json={"projectId": "01JPROJECT", "operatorId": "op_001", "reason": "customer request"},
        )
        assert d["handoffStatus"] == "active"
        # 并发接管 -> 409
        r = httpx.post(
            f"{self.base}/api/control/conversations/{cid}/handoff",
            json={"projectId": "01JPROJECT", "operatorId": "op_002", "reason": "dup"},
            timeout=10,
        )
        assert r.status_code == 409, f"期望 409, 实得 {r.status_code}"
        # 接管期间不应有主动 send_message
        r, d = self.get(
            "/api/device/commands/pending",
            params={"deviceId": self.device_id},
            headers={"X-Device-Token": self.device_token},
        )
        assert all(c["commandType"] != "send_message" for c in d["items"])
        r, d = self.post(
            f"/api/control/conversations/{cid}/handoff/return",
            json={"projectId": "01JPROJECT", "operatorId": "op_001", "resumeMode": "continue"},
        )
        assert d["handoffStatus"] == "none"

    def run_all(self):
        print(f"\n=== Morphix 实时 P0 主链路验证 @ {self.base} ===\n")
        steps = [
            ("健康检查 /api/health", self.health),
            ("Dev-Bootstrap 签发令牌", self.bootstrap),
            ("设备注册绑定", self.register_device),
            ("设备心跳上报", self.heartbeat),
            ("设备令牌刷新", self.refresh_token),
            ("运行时入站消息(编排)", self.inbound),
            ("控制面会话/消息/运行态查询", self.control_views),
            ("设备命令拉取→ACK→complete 闭环", self.device_command_loop),
            ("审计: 运行实例/节点/触发", self.audit),
            ("人工接管→并发冲突→交还", self.handoff),
        ]
        for name, fn in steps:
            self.step(name, fn)
            if self.fail:  # 任一关键步失败即停止，避免连锁报错淹没真实原因
                print("\n⚠️  关键步骤失败，中止后续验证。")
                break

        print(f"\n=== 结果: {self.ok} 通过 / {self.fail} 失败 ===")
        return 0 if self.fail == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="Morphix 实时 P0 主链路验证")
    ap.add_argument("--base-url", default=None, help="后端基址，默认取 BASE_URL 环境变量或 http://localhost:8000")
    args = ap.parse_args()
    base = args.base_url or os_environ("BASE_URL", "http://localhost:8000")
    v = Verify(base)
    try:
        sys.exit(v.run_all())
    except BackendUnavailable as e:
        sys.stderr.write(f"\n❌ 无法连接 {base}，请先启动 morphix-control (uvicorn --port 8000)。\n   详情: {e}\n")
        sys.exit(3)


def os_environ(key: str, default: str) -> str:
    return os.environ.get(key, default)


if __name__ == "__main__":
    main()

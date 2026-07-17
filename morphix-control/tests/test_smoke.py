"""P0 main-chain smoke test.

Drives the full Morphix control-plane backend through the contract-shaped
endpoints and asserts the success envelope + key data fields. Uses a throwaway
SQLite file so it is hermetic.
"""
import os
import sys

BASE = "/Users/stevenmac/Desktop/工作目录/Morphix/morphix-control"
sys.path.insert(0, BASE)

TEST_DB = os.path.join(BASE, "data", "test_morphix.db")
os.environ["MORPHIX_DB"] = TEST_DB
os.environ["MORPHIX_DEV"] = "1"

if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo  # noqa: E402

# Ensure tables + demo seed exist regardless of lifespan timing.
Base.metadata.create_all(bind=engine)
_db = SessionLocal()
try:
    seed_demo(_db)
finally:
    _db.close()

client = TestClient(app)

RUNTIME_H = {"X-Runtime-Token": "rt_test"}
PROVISION_H = {"X-Device-Provisioning-Key": "dev-provisioning-key"}
INTERNAL_H = {"X-Internal-Service-Token": "int_test"}


def _data(r):
    assert r.status_code < 500, f"{r.status_code}: {r.text}"
    body = r.json()
    assert body.get("success") is True, body
    return body["data"]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_p0_main_chain():
    # 1) Device registration
    reg = client.post(
        "/api/device/registrations",
        headers=PROVISION_H,
        json={
            "bindCode": "BIND-TEST-001",
            "projectId": "01JPROJECT",
            "channelType": "wechat",
            "accountType": "personal",
            "installFingerprint": "android-14:pixel7:abc123",
            "deviceMeta": {"brand": "Google", "model": "Pixel 7", "osVersion": "Android 14", "appVersion": "0.1.0"},
        },
    )
    assert reg.status_code == 201, reg.text
    d = _data(reg)
    assert d["deviceId"] and d["deviceToken"] and d["channelAccountId"]
    device_id = d["deviceId"]
    device_token = d["deviceToken"]
    channel_account_id = d["channelAccountId"]
    device_h = {"X-Device-Token": device_token}

    # 2) Heartbeat
    hb = client.post(
        "/api/device/heartbeats",
        headers=device_h,
        json={
            "deviceId": device_id,
            "reportedAt": "2026-07-12T16:00:00+08:00",
            "deviceStatus": "online",
            "accountStatus": "online",
            "commandQueue": {"pendingCount": 0, "runningCount": 0, "retryCount": 0},
        },
    )
    assert hb.status_code == 200, hb.text
    assert _data(hb)["commandPollIntervalSec"] >= 3

    # 3) Token refresh
    rf = client.post(
        "/api/device/registrations/{}/refresh-token".format(device_id),
        headers=device_h,
        json={"refreshReason": "expiring"},
    )
    assert rf.status_code == 200, rf.text
    new_token = _data(rf)["deviceToken"]
    assert new_token != device_token
    device_h = {"X-Device-Token": new_token}

    # 4) Inbound message (runtime) -> creates conversation + run + agent + command
    ib = client.post(
        "/api/runtime/inbound-events/messages",
        headers=RUNTIME_H,
        json={
            "projectId": "01JPROJECT",
            "channelAccountId": channel_account_id,
            "deviceId": device_id,
            "conversationType": "direct",
            "sourceConversationId": "wx_conv_smoke",
            "sourceMessageId": "wx_msg_smoke_001",
            "contact": {"externalUid": "wx_user_smoke", "displayName": "李四"},
            "message": {"messageType": "text", "contentText": "报价多少", "sentAt": "2026-07-12T16:30:00+08:00"},
        },
    )
    assert ib.status_code == 202, ib.text
    ev = _data(ib)
    assert ev["accepted"] is True
    assert ev["conversationId"] and ev["sessionRuntimeId"] and ev["dispatchMode"] == "sync_orchestrate"
    conversation_id = ev["conversationId"]

    # 5) Conversation list / detail / messages / runtime
    lst = client.get("/api/control/conversations", params={"projectId": "01JPROJECT"})
    assert lst.status_code == 200
    assert _data(lst)["total"] >= 1

    det = client.get(f"/api/control/conversations/{conversation_id}")
    assert det.status_code == 200
    dd = _data(det)
    assert dd["handoffStatus"] == "none"
    assert dd["currentBot"] is not None

    msgs = client.get(f"/api/control/conversations/{conversation_id}/messages")
    assert msgs.status_code == 200
    assert len(_data(msgs)["items"]) >= 1

    rt = client.get(f"/api/control/conversations/{conversation_id}/runtime")
    assert rt.status_code == 200
    assert _data(rt)["sessionState"] == "WAITING_DEVICE_ACK"

    # 6) Device pulls pending command
    pull = client.get("/api/device/commands/pending", headers=device_h, params={"deviceId": device_id})
    assert pull.status_code == 200, pull.text
    items = _data(pull)["items"]
    assert len(items) == 1, items
    cmd = items[0]
    assert cmd["commandType"] == "send_message"
    command_id = cmd["commandId"]

    # 7) ACK + complete
    ack = client.post(f"/api/device/commands/{command_id}/ack", headers=device_h, json={"deviceId": device_id, "ackedAt": "2026-07-12T16:31:00+08:00"})
    assert ack.status_code == 200 and _data(ack)["status"] == "acked"
    comp = client.post(f"/api/device/commands/{command_id}/complete", headers=device_h, json={"deviceId": device_id, "doneAt": "2026-07-12T16:31:05+08:00", "result": {"ok": True}})
    assert comp.status_code == 200 and _data(comp)["status"] == "done"
    # idempotent repeat -> no error
    comp2 = client.post(f"/api/device/commands/{command_id}/complete", headers=device_h, json={"deviceId": device_id, "doneAt": "2026-07-12T16:31:06+08:00"})
    assert comp2.status_code == 200 and _data(comp2)["status"] == "done"

    # 8) Run detail + node executions + audit
    run_id = _data(rt)["activeRunId"]
    rd = client.get(f"/api/control/workflow-runs/{run_id}")
    assert rd.status_code == 200
    assert _data(rd)["status"] == "completed"

    ne = client.get(f"/api/control/workflow-runs/{run_id}/node-executions")
    assert ne.status_code == 200
    node_items = _data(ne)["items"]
    assert len(node_items) >= 3  # start, agent, device_command (+end)

    pd = client.get(f"/api/control/workflow-runs/{run_id}/policy-decisions")
    assert pd.status_code == 200

    ai = client.get(f"/api/control/workflow-runs/{run_id}/agent-invocations")
    assert ai.status_code == 200
    assert len(_data(ai)["items"]) >= 1

    # 9) Handoff + return
    ho = client.post(
        f"/api/control/conversations/{conversation_id}/handoff",
        json={"projectId": "01JPROJECT", "operatorId": "op_001", "reason": "customer request"},
    )
    assert ho.status_code == 200 and _data(ho)["handoffStatus"] == "active"
    # concurrent handoff -> conflict
    ho2 = client.post(
        f"/api/control/conversations/{conversation_id}/handoff",
        json={"projectId": "01JPROJECT", "operatorId": "op_002", "reason": "dup"},
    )
    assert ho2.status_code == 409, ho2.text
    # during handoff, pending pull must not return proactive send_message
    pull2 = client.get("/api/device/commands/pending", headers=device_h, params={"deviceId": device_id})
    assert pull2.status_code == 200
    assert all(c["commandType"] != "send_message" for c in _data(pull2)["items"])

    ret = client.post(
        f"/api/control/conversations/{conversation_id}/handoff/return",
        json={"projectId": "01JPROJECT", "operatorId": "op_001", "resumeMode": "continue"},
    )
    assert ret.status_code == 200 and _data(ret)["handoffStatus"] == "none"

    # 10) Internal endpoints
    pe = client.post(
        "/internal/policy-router/evaluate",
        headers=INTERNAL_H,
        json={
            "projectId": "01JPROJECT",
            "conversationId": conversation_id,
            "sessionRuntimeId": _data(rt)["sessionRuntimeId"],
            "eventType": "inbound_message",
            "eventPayload": {"message": {"contentText": "hi"}},
            "context": {},
        },
    )
    assert pe.status_code == 200 and _data(pe)["handoffDecision"] in ("stay_ai", "suggest_human", "force_human")

    ag = client.post(
        "/internal/agent-executor/invoke",
        headers=INTERNAL_H,
        json={"runId": run_id, "nodeExecutionId": "ne_x", "agentType": "qa", "modelProfile": "stub", "structuredInput": {"q": "1"}},
    )
    assert ag.status_code == 200 and _data(ag)["summary"]

    sv = client.post(
        "/internal/agent-executor/supervisor",
        headers=INTERNAL_H,
        json={"runId": run_id, "conversationId": conversation_id, "triggerReason": "test", "structuredContext": {}},
    )
    assert sv.status_code == 200 and _data(sv)["confidence"] >= 0

    # 11) Idempotency: duplicate inbound same sourceMessageId -> accepted false, no new run
    ib2 = client.post(
        "/api/runtime/inbound-events/messages",
        headers=RUNTIME_H,
        json={
            "projectId": "01JPROJECT",
            "channelAccountId": channel_account_id,
            "deviceId": device_id,
            "conversationType": "direct",
            "sourceConversationId": "wx_conv_smoke",
            "sourceMessageId": "wx_msg_smoke_001",
            "contact": {"externalUid": "wx_user_smoke", "displayName": "李四"},
            "message": {"messageType": "text", "contentText": "报价多少", "sentAt": "2026-07-12T16:30:00+08:00"},
        },
    )
    assert ib2.status_code == 202
    assert _data(ib2)["accepted"] is False


def test_auth_rejections():
    # no auth -> 401 on runtime
    r = client.post("/api/runtime/inbound-events/messages", json={"projectId": "01JPROJECT"})
    assert r.status_code == 401, r.text

    # invalid device token -> 401
    r2 = client.get("/api/device/commands/pending", headers={"X-Device-Token": "bogus"}, params={"deviceId": "dev_x"})
    assert r2.status_code == 401, r2.text

    # register with unknown project -> 404
    r3 = client.post(
        "/api/device/registrations",
        headers=PROVISION_H,
        json={"bindCode": "BIND-404", "projectId": "nope", "channelType": "wechat", "accountType": "personal", "installFingerprint": "x", "deviceMeta": {"brand": "b", "model": "m", "osVersion": "o", "appVersion": "v"}},
    )
    assert r3.status_code == 404, r3.text

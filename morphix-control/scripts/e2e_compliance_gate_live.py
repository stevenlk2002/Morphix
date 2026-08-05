"""Live end-to-end verification that A8 compliance gate truly blocks in morphix-control runtime.

Drives the running backend (default http://127.0.0.1:8000) through:
  project -> workflow-version(published, with compliance gate) -> bot -> inbound
and asserts the send node is suppressed when the draft hits a B1-B8 red line,
and emitted when clean.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CTRL_H = {"X-Control-Token": "ctrl_dev", "X-Role": "owner", "Content-Type": "application/json"}
RT_H = {"X-Runtime-Token": "rt_dev", "Content-Type": "application/json"}


def post(path, body, headers=CTRL_H):
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(path, headers=CTRL_H):
    req = urllib.request.Request(BASE + path, headers=headers)
    r = urllib.request.urlopen(req, timeout=15)
    return r.status, json.loads(r.read())


def run_case(tag, send_text):
    s, b = post("/api/control/projects", {"req": {"name": f"cg_{tag}", "description": "e2e"}, "allowed": ["owner"]})
    assert s == 201, (s, b)
    pid = b["data"]["id"]
    defn = {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "a", "type": "agent", "position": {"x": 200, "y": 0}, "data": {"agentType": "qa"}},
            {"id": "g", "type": "policy", "position": {"x": 400, "y": 0}, "data": {"gate": "compliance"}},
            {"id": "s", "type": "send_message", "position": {"x": 600, "y": 0},
             "data": {"commandType": "send_message", "payload": {"channel": "wecom", "text": send_text}}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "a"},
            {"id": "e2", "source": "a", "target": "g"},
            {"id": "e3", "source": "g", "target": "s"},
        ],
    }
    s, b = post(f"/api/control/projects/{pid}/workflow-versions",
                {"req": {"projectId": pid, "name": f"wf_{tag}", "definition": defn}, "allowed": ["owner"]})
    assert s == 201, (s, b)
    wfvid = b["data"]["id"]
    s, b = post(f"/api/control/projects/{pid}/workflow-versions/{wfvid}/publish", ["owner"])
    assert s == 200, (s, b)
    s, b = post(f"/api/control/projects/{pid}/bots", {"req": {"projectId": pid, "name": f"bot_{tag}"}, "allowed": ["owner"]})
    assert s == 201, (s, b)
    ib = {
        "projectId": pid, "channelAccountId": f"ca_{tag}", "deviceId": f"dev_{tag}",
        "conversationType": "direct", "sourceConversationId": f"wx_{tag}", "sourceMessageId": f"wx_{tag}_1",
        "contact": {"externalUid": f"u_{tag}", "displayName": "测试用户"},
        "message": {"messageType": "text", "contentText": "你好", "sentAt": "2026-08-04T10:00:00+08:00"},
    }
    s, b = post("/api/runtime/inbound-events/messages", ib, RT_H)
    assert s == 202, (s, b)
    conv_id = b["data"]["conversationId"]
    s, b = get(f"/api/control/conversations/{conv_id}/runtime")
    run_id = b["data"]["activeRunId"]
    s, b = get(f"/api/control/workflow-runs/{run_id}/node-executions")
    node_ids = [n["nodeId"] for n in b["data"]["items"]]
    s, b = get(f"/api/control/workflow-runs/{run_id}/policy-decisions")
    comp = [pd for pd in b["data"]["items"] if pd.get("decisionType") == "compliance_gate"]
    comp_decision = comp[0]["decision"] if comp else None
    s, b = get(f"/api/control/workflow-runs/{run_id}")
    run_status = b["data"]["status"]
    print(f"\n=== CASE {tag} ===")
    print(f"  project={pid} wfv={wfvid}")
    print(f"  run_status={run_status}")
    print(f"  node_executions={node_ids}")
    print(f"  compliance_gate={comp_decision}  | send node executed={'s' in node_ids}")
    return comp_decision, ("s" in node_ids)


def main():
    blk = run_case("block", "久鸣必聋，久聋必呆，您再拖下去一定会耳聋，赶紧买疗程！")
    alw = run_case("allow", "您好，这里是河马健康。耳部不适建议尽早到线下机构评估，平时注意休息。")
    print("\n=== ASSERTIONS ===")
    assert blk[0] == "blocked" and blk[1] is False, blk
    assert alw[0] == "allowed" and alw[1] is True, alw
    print("PASS: A8 守门在真实运行时引擎中真正拦截/放行 ✓")


if __name__ == "__main__":
    main()

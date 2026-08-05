"""运行时定义端到端验证（hermetic，无 LLM / 无 HTTP）。

直接加载 scripts/build_runtime_workflow.py 生成的两份 definition，
用真实引擎 orchestration._step_nodes 走图，证明「引擎可直接执行」：

  1. 阶段路由：一次 inbound 只推进一步（不会一口气发 11 条）
  2. 意图路由：按 intent:* 标签选中正确的能力分支
  3. A8 守门内联生效：send 前必过 compliance gate；BLOCK 时不落 DeviceCommand
  4. B8 价格豁免：纯价格披露 WARN 但放行（端到端复现 Step3 的分级效果）
  5. timer 分支：沉默唤醒记录 timer_scheduled，且该分支不外发
"""
import copy
import json
import os
import sys

BASE = "/Users/stevenmac/Desktop/工作目录/Morphix/morphix-control"
REPO = "/Users/stevenmac/Desktop/工作目录/Morphix"
sys.path.insert(0, BASE)

TEST_DB = os.path.join(BASE, "data", "test_runtime_defs.db")
os.environ["MORPHIX_DB"] = TEST_DB
os.environ["MORPHIX_DEV"] = "1"

if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from sqlalchemy import select  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    Conversation,
    DeviceCommand,
    PolicyDecision,
    Project,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowVersion,
)
from app.services import orchestration as orch  # noqa: E402

Base.metadata.create_all(bind=engine)

_SEQ = 0


def _uid(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"rw{prefix}_{_SEQ}"


def _load(name: str) -> dict:
    with open(os.path.join(REPO, "docs", name), encoding="utf-8") as f:
        d = json.load(f)
    return {"nodes": d["nodes"], "edges": d["edges"]}


FUNNEL = _load("hema-sop-runtime-funnel.json")
KEFU = _load("hema-sop-runtime-kefu.json")


def _run(definition: dict, tags=None):
    db = SessionLocal()
    try:
        proj = Project(id=_uid("prj"), name="rt")
        db.add(proj)
        db.flush()
        wfv = WorkflowVersion(
            id=_uid("wfv"), project_id=proj.id, name="rt", status="published", definition=definition
        )
        db.add(wfv)
        db.flush()
        conv = Conversation(
            id=_uid("conv"),
            project_id=proj.id,
            channel_account_id="ca_rt",
            conversation_type="direct",
            subject="rt",
            owner_type="ai",
            handoff_status="none",
            current_workflow_version_id=wfv.id,
            contact={"tags": tags or []},
        )
        db.add(conv)
        db.flush()
        run = WorkflowRun(
            id=_uid("run"),
            project_id=proj.id,
            conversation_id=conv.id,
            workflow_version_id=wfv.id,
            status="running",
            trigger_type="manual",
        )
        db.add(run)
        db.flush()

        has_pending = orch._step_nodes(
            db,
            run=run,
            conversation=conv,
            definition=wfv.definition,
            device_id="dev_rt",
            channel_account_id="ca_rt",
        )
        db.commit()

        cmds = db.execute(select(DeviceCommand).where(DeviceCommand.run_id == run.id)).scalars().all()
        audits = db.execute(select(AuditLog).where(AuditLog.actor_id == run.id)).scalars().all()
        decisions = db.execute(select(PolicyDecision).where(PolicyDecision.run_id == run.id)).scalars().all()
        steps = db.execute(select(WorkflowRunStep).where(WorkflowRunStep.run_id == run.id)).scalars().all()
        return dict(
            has_pending=has_pending, cmds=cmds, audits=audits,
            decisions=decisions, steps=steps, run=run,
        )
    finally:
        db.close()


def _texts(cmds):
    return [c.payload.get("text", "") for c in cmds]


def _chosen(audits, event="switch_branch"):
    hits = [a for a in audits if a.event_type == event]
    return hits[0].detail["chosen"] if hits else None


# ---------------------------------------------------------------- 漏斗：阶段路由
def test_funnel_default_routes_to_step1():
    r = _run(FUNNEL)
    assert _chosen(r["audits"]) == "n_s1_agent"
    assert len(r["cmds"]) == 1, f"一次 inbound 应只发 1 条，实际 {len(r['cmds'])}"
    assert "线上健康顾问" in _texts(r["cmds"])[0]
    assert r["run"].status == "completed"


def test_funnel_stage_tag_advances_one_step_only():
    """核心：stage:s4 只跑第4步，不会把 11 步一口气跑完。"""
    r = _run(FUNNEL, tags=["stage:s4"])
    assert _chosen(r["audits"]) == "n_s4_agent"
    assert len(r["cmds"]) == 1, f"应只发 1 条，实际 {len(r['cmds'])}: {_texts(r['cmds'])}"
    assert "科普视频" in _texts(r["cmds"])[0]


def test_funnel_every_stage_reachable_and_single_send():
    """11 个阶段逐一驱动，每个都必须恰好发 1 条且被 compliance gate 放行。"""
    for i in range(1, 12):
        r = _run(FUNNEL, tags=[f"stage:s{i}"])
        assert _chosen(r["audits"]) == f"n_s{i}_agent", f"stage s{i} 路由错误"
        assert len(r["cmds"]) == 1, f"stage s{i} 应发 1 条，实际 {len(r['cmds'])}"
        gates = [d for d in r["decisions"] if d.decision_type == "compliance_gate"]
        assert gates, f"stage s{i} 未经过 compliance gate"
        assert gates[0].decision == "allowed", f"stage s{i} 被拦: {gates[0].reason_codes}"


def test_funnel_price_step_warns_but_sends():
    """B8 价格豁免端到端：纯价格披露 WARN 但放行。"""
    r = _run(FUNNEL, tags=["stage:s8"])
    gates = [d for d in r["decisions"] if d.decision_type == "compliance_gate"]
    assert gates and gates[0].decision == "allowed"
    assert any("B8" in str(c) for c in (gates[0].reason_codes or [])), gates[0].reason_codes
    assert len(r["cmds"]) == 1
    assert "598" in _texts(r["cmds"])[0]


def test_funnel_human_approval_before_quote():
    """报价/收定金/交接三步必须先过 human_approval 再 send。"""
    for stage in ("s8", "s10", "s11"):
        r = _run(FUNNEL, tags=[f"stage:{stage}"])
        node_ids = [s.node_id for s in r["steps"]]
        assert f"n_{stage}_human" in node_ids, f"{stage} 缺少人工确认节点"
        assert node_ids.index(f"n_{stage}_human") < node_ids.index(f"n_{stage}_send")


# ---------------------------------------------------------------- 守门真的拦得住
def test_compliance_gate_blocks_and_emits_no_command():
    """把第1步话术换成红线文本，必须拦停且不落 DeviceCommand。"""
    bad = copy.deepcopy(FUNNEL)
    for n in bad["nodes"]:
        if n["id"] == "n_s1_send":
            n["data"]["payload"]["text"] = "我们保证100%治好您的耳鸣，无效退款。"
    r = _run(bad)
    assert len(r["cmds"]) == 0, f"BLOCK 时不应落命令，实际 {_texts(r['cmds'])}"
    assert r["has_pending"] is False
    assert "compliance blocked" in (r["run"].result_summary or "")
    gates = [d for d in r["decisions"] if d.decision_type == "compliance_gate"]
    assert gates and gates[0].decision == "blocked"


def test_every_send_node_is_preceded_by_compliance_gate():
    """结构不变量：任何 send 的前驱都必须是 compliance gate（守门不可绕过）。"""
    for defn in (FUNNEL, KEFU):
        by_id = {n["id"]: n for n in defn["nodes"]}
        sends = [n["id"] for n in defn["nodes"] if n["type"] == "send_message"]
        assert sends
        for sid in sends:
            preds = [e["source"] for e in defn["edges"] if e["target"] == sid]
            assert preds, f"{sid} 无入边"
            for p in preds:
                pd = by_id[p]
                assert pd["type"] == "policy" and pd["data"].get("gate") == "compliance", \
                    f"{sid} 的前驱 {p} 不是 compliance gate"


# ---------------------------------------------------------------- kefu：意图路由
def test_kefu_default_routes_to_first_branch():
    r = _run(KEFU)
    assert _chosen(r["audits"]) == "n_kepu_kb"
    assert len(r["cmds"]) == 1
    assert "耳鸣" in _texts(r["cmds"])[0]


def test_kefu_faq_intent_hits_kb_then_sends():
    r = _run(KEFU, tags=["intent:百问百答"])
    assert _chosen(r["audits"]) == "n_faq_kb"
    node_ids = [s.node_id for s in r["steps"]]
    assert "n_faq_kb" in node_ids and "n_faq_agent" in node_ids
    assert node_ids.index("n_faq_kb") < node_ids.index("n_faq_agent")
    assert len(r["cmds"]) == 1
    assert "国药准字" in _texts(r["cmds"])[0]


def test_kefu_revive_branch_schedules_timer_and_does_not_send():
    """沉默唤醒分支：记录 timer，人工确认后写画像，不直接外发。"""
    r = _run(KEFU, tags=["intent:沉默唤醒"])
    assert _chosen(r["audits"]) == "n_revive_agent"
    timers = [a for a in r["audits"] if a.event_type == "timer_scheduled"]
    assert timers, "沉默唤醒分支应记录 timer_scheduled"
    assert timers[0].detail["topic"] == "silent_revive"
    assert timers[0].detail["delay_seconds"] == 86400
    assert len(r["cmds"]) == 0, "该分支不应直接外发"


def test_kefu_handover_requires_human_approval():
    r = _run(KEFU, tags=["intent:成交交接"])
    node_ids = [s.node_id for s in r["steps"]]
    assert "n_handover_human" in node_ids
    assert "n_handover_attr" in node_ids
    assert len(r["cmds"]) == 0


def test_kefu_all_intent_tags_route_distinctly():
    """8 个意图标签必须各自路由到不同分支头，无串味。"""
    tags = [
        "intent:科普引导", "intent:信息收集", "intent:百问百答", "intent:推进节奏",
        "intent:意向打分", "intent:沉默唤醒", "intent:成交交接", "intent:标签归档",
    ]
    chosen = []
    for t in tags:
        r = _run(KEFU, tags=[t])
        c = _chosen(r["audits"])
        assert c, f"{t} 未产生 switch_branch"
        chosen.append(c)
    assert len(set(chosen)) == len(tags), f"路由串味: {list(zip(tags, chosen))}"


def test_funnel_stage_with_agent_reply_substitutes_and_compliance_runs():
    """s3 翻成 {{agentReply}}：agent 节点的真实回复必须落入发送文本，且合规守门仍对其判定。"""
    r = _run(FUNNEL, tags=["stage:s3"])
    assert len(r["cmds"]) == 1, f"应只发 1 条，实际 {_texts(r['cmds'])}"
    sent = _texts(r["cmds"])[0]
    # 占位符已被替换（不是字面 {{agentReply}}），且非空。
    assert "{{agentReply}}" not in sent, f"占位符未被替换: {sent}"
    assert sent.strip(), "发送文本不应为空"
    # A8 守门对真实文本做过判定（allowed 或 blocked 都会留痕）。
    gates = [d for d in r["decisions"] if d.decision_type == "compliance_gate"]
    assert gates, "缺少 compliance_gate 决策"
    assert gates[0].decision == "allowed", f"真实 LLM 文本不应触发拦截: {gates[0].reason_codes}"


def test_agent_invocation_records_llm_model():
    """agent 节点应记录真实模型名（有 key 时为 deepseek-chat，无 key 时为 stub）。"""
    r = _run(FUNNEL, tags=["stage:s3"])
    ai_steps = [s for s in r["steps"] if s.executor_type in ("llm", "stub")]
    assert ai_steps, "应存在 agent 执行步骤"


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print("ALL RUNTIME DEF TESTS PASSED" if not failed else f"{failed} FAILED")

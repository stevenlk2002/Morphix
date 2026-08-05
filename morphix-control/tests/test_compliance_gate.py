"""A8 compliance gate test (P0-ish, hermetic).

Proves the runtime policy node with gate=="compliance" actually evaluates the
downstream send text against B1-B8 and BLOCKS the DeviceCommand when a red line
is hit, while clean text flows through and emits the command.
"""
import os
import sys

BASE = "/Users/stevenmac/Desktop/工作目录/Morphix/morphix-control"
sys.path.insert(0, BASE)

TEST_DB = os.path.join(BASE, "data", "test_compliance_gate.db")
os.environ["MORPHIX_DB"] = TEST_DB
os.environ["MORPHIX_DEV"] = "1"

if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from sqlalchemy import select  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Conversation,
    DeviceCommand,
    PolicyDecision,
    Project,
    WorkflowRun,
    WorkflowVersion,
)
from app.services import orchestration as orch  # noqa: E402
from app.services import policy as policy_svc  # noqa: E402

Base.metadata.create_all(bind=engine)

CLEAN_TEXT = "您好，这里是河马健康。耳部不适建议尽早到线下机构评估，平时注意休息。"
BLOCK_TEXT = "久鸣必聋，久聋必呆，您再拖下去一定会耳聋，赶紧买我们的疗程！"

_SEQ = 0


def _uid(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"{prefix}_{_SEQ}"


def _def(send_text: str) -> dict:
    return {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "a", "type": "agent", "position": {"x": 200, "y": 0}, "data": {"agentType": "qa"}},
            {"id": "g", "type": "policy", "position": {"x": 400, "y": 0}, "data": {"gate": "compliance"}},
            {
                "id": "s",
                "type": "send_message",
                "position": {"x": 600, "y": 0},
                "data": {"commandType": "send_message", "payload": {"channel": "wecom", "text": send_text}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "a"},
            {"id": "e2", "source": "a", "target": "g"},
            {"id": "e3", "source": "g", "target": "s"},
        ],
    }


def _seed(db, send_text: str):
    proj = Project(id=_uid("prj"), name="cg")
    db.add(proj)
    db.flush()
    wfv = WorkflowVersion(id=_uid("wfv"), project_id=proj.id, name="cg", status="published", definition=_def(send_text))
    db.add(wfv)
    db.flush()
    conv = Conversation(
        id=_uid("conv"),
        project_id=proj.id,
        channel_account_id="ca_cg",
        conversation_type="direct",
        subject="t",
        owner_type="ai",
        handoff_status="none",
        current_bot_id=None,
        current_workflow_version_id=wfv.id,
        contact={},
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
    return proj, wfv, conv, run


def _run_case(send_text: str):
    db = SessionLocal()
    try:
        proj, wfv, conv, run = _seed(db, send_text)
        has_pending = orch._step_nodes(
            db,
            run=run,
            conversation=conv,
            definition=wfv.definition,
            device_id="dev_cg",
            channel_account_id="ca_cg",
        )
        db.commit()
        cmds = db.execute(select(DeviceCommand).where(DeviceCommand.run_id == run.id)).scalars().all()
        pd = db.execute(
            select(PolicyDecision).where(
                PolicyDecision.run_id == run.id, PolicyDecision.decision_type == "compliance_gate"
            )
        ).scalars().all()
        return has_pending, cmds, pd, run
    finally:
        db.close()


def test_evaluate_compliance_unit():
    # clean
    assert policy_svc.evaluate_compliance(text=CLEAN_TEXT)["allow_send"] is True
    # hard BLOCK (B2 恐吓)
    r = policy_svc.evaluate_compliance(text=BLOCK_TEXT)
    assert r["allow_send"] is False
    assert r["severity"] == "BLOCK"
    codes = {v["code"] for v in r["violations"]}
    assert "B2" in codes
    # B8 + efficacy bundle => BLOCK
    b8 = policy_svc.evaluate_compliance(text="一个疗程598元保证见效，无效退款")
    assert b8["allow_send"] is False and b8["severity"] == "BLOCK"
    assert "B8" in {v["code"] for v in b8["violations"]}
    # B8 pure price disclosure => WARN (not blocked)
    p = policy_svc.evaluate_compliance(text="原价1280元，优惠价598元，定金48元货到付款")
    assert p["allow_send"] is True and p["severity"] == "WARN"
    # B2 科普 risk reminder => WARN (not blocked)
    w = policy_svc.evaluate_compliance(text="症状会越拖越严重，建议尽早到线下评估")
    assert w["allow_send"] is True and w["severity"] == "WARN"
    # B7 self-disclosure => allowed (no impersonation)
    d = policy_svc.evaluate_compliance(text="我不是医生，我是健康顾问，负责收集情况")
    assert d["allow_send"] is True and "B7" not in {v["code"] for v in d["violations"]}
    # B1 negation => WARN (not blocked)
    n = policy_svc.evaluate_compliance(text="我们不保证有效，先看是否适合")
    assert n["allow_send"] is True
    # empty text passes
    assert policy_svc.evaluate_compliance(text="")["allow_send"] is True


def test_allowed_emits_command():
    has_pending, cmds, pd, run = _run_case(CLEAN_TEXT)
    assert len(cmds) == 1, f"expected 1 command, got {len(cmds)}"
    assert cmds[0].command_type == "send_message"
    assert has_pending is True
    assert pd and pd[0].decision == "allowed", [p.decision for p in pd]
    assert run.status == "completed"


def test_blocked_suppresses_command():
    has_pending, cmds, pd, run = _run_case(BLOCK_TEXT)
    assert len(cmds) == 0, f"blocked must not emit command, got {len(cmds)}"
    assert has_pending is False
    assert pd and pd[0].decision == "blocked", [p.decision for p in pd]
    assert run.status == "completed"
    assert "B2" in run.result_summary


def test_warn_price_emits_command():
    has_pending, cmds, pd, run = _run_case("原价1280元，优惠价598元，货到付款550元")
    assert len(cmds) == 1, f"WARN price must still emit command, got {len(cmds)}"
    assert has_pending is True
    assert pd and pd[0].decision == "allowed", [p.decision for p in pd]


def test_b8_efficacy_blocks_command():
    has_pending, cmds, pd, run = _run_case("一个疗程598元保证见效，无效退款")
    assert len(cmds) == 0, f"B8+efficacy must suppress command, got {len(cmds)}"
    assert has_pending is False
    assert pd and pd[0].decision == "blocked", [p.decision for p in pd]


if __name__ == "__main__":
    test_evaluate_compliance_unit()
    test_allowed_emits_command()
    test_blocked_suppresses_command()
    print("ALL COMPLIANCE GATE TESTS PASSED")

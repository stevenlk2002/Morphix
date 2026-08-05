"""Timer + Switch node test (hermetic, no LLM/HTTP).

Proves:
  - timer node records a `timer_scheduled` AuditLog (topic/delay/downstream) AND
    the engine continues synchronously to the downstream send node.
  - switch node records a `switch_branch` AuditLog with the chosen target and
    routes traversal to the chosen branch (default when no case matches).
"""
import os
import sys

BASE = "/Users/stevenmac/Desktop/工作目录/Morphix/morphix-control"
sys.path.insert(0, BASE)

TEST_DB = os.path.join(BASE, "data", "test_timer_switch.db")
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
    Project,
    WorkflowRun,
    WorkflowVersion,
)
from app.services import orchestration as orch  # noqa: E402

Base.metadata.create_all(bind=engine)

_SEQ = 0


def _uid(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"{prefix}_{_SEQ}"


def _timer_def():
    return {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {
                "id": "t",
                "type": "timer",
                "position": {"x": 200, "y": 0},
                "data": {"config": {"delaySeconds": 3600, "topic": "nurture_day3"}},
            },
            {
                "id": "s",
                "type": "send_message",
                "position": {"x": 400, "y": 0},
                "data": {"commandType": "send_message", "payload": {"channel": "wecom", "text": "三天后温馨提醒"}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "t"},
            {"id": "e2", "source": "t", "target": "s"},
        ],
    }


def _switch_def():
    return {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {
                "id": "sw",
                "type": "switch",
                "position": {"x": 200, "y": 0},
                "data": {
                    "config": {
                        "switchOn": "tag",
                        "default": "n_normal",
                        "cases": [{"equals": "vip", "target": "n_vip"}],
                    }
                },
            },
            {
                "id": "n_vip",
                "type": "send_message",
                "position": {"x": 400, "y": 0},
                "data": {"commandType": "send_message", "payload": {"channel": "wecom", "text": "VIP 专属复查方案"}},
            },
            {
                "id": "n_normal",
                "type": "send_message",
                "position": {"x": 400, "y": 120},
                "data": {"commandType": "send_message", "payload": {"channel": "wecom", "text": "普通跟进话术"}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "sw"},
            {"id": "e2", "source": "sw", "target": "n_vip"},
            {"id": "e3", "source": "sw", "target": "n_normal"},
        ],
    }


def _seed(db, definition: dict, tags=None):
    proj = Project(id=_uid("tsprj"), name="ts")
    db.add(proj)
    db.flush()
    wfv = WorkflowVersion(id=_uid("tswfv"), project_id=proj.id, name="ts", status="published", definition=definition)
    db.add(wfv)
    db.flush()
    conv = Conversation(
        id=_uid("tsconv"),
        project_id=proj.id,
        channel_account_id="ca_ts",
        conversation_type="direct",
        subject="t",
        owner_type="ai",
        handoff_status="none",
        current_bot_id=None,
        current_workflow_version_id=wfv.id,
        contact={"tags": tags or []},
    )
    db.add(conv)
    db.flush()
    run = WorkflowRun(
        id=_uid("tsrun"),
        project_id=proj.id,
        conversation_id=conv.id,
        workflow_version_id=wfv.id,
        status="running",
        trigger_type="manual",
    )
    db.add(run)
    db.flush()
    return proj, wfv, conv, run


def _run(definition, tags=None):
    db = SessionLocal()
    try:
        proj, wfv, conv, run = _seed(db, definition, tags)
        has_pending = orch._step_nodes(
            db,
            run=run,
            conversation=conv,
            definition=wfv.definition,
            device_id="dev_ts",
            channel_account_id="ca_ts",
        )
        db.commit()
        cmds = db.execute(select(DeviceCommand).where(DeviceCommand.run_id == run.id)).scalars().all()
        audits = db.execute(select(AuditLog).where(AuditLog.actor_id == run.id)).scalars().all()
        return has_pending, cmds, audits, run
    finally:
        db.close()


def _chosen_of(audits):
    hits = [a for a in audits if a.event_type == "switch_branch"]
    return hits[0].detail["chosen"] if hits else None


def test_timer_records_auditlog_and_continues():
    has_pending, cmds, audits, run = _run(_timer_def())
    timers = [a for a in audits if a.event_type == "timer_scheduled"]
    assert timers, "timer node must record a timer_scheduled AuditLog"
    detail = timers[0].detail
    assert detail["topic"] == "nurture_day3"
    assert detail["delay_seconds"] == 3600
    assert detail["downstream"] == "s"
    assert detail["scheduled_at"]
    # engine continues synchronously to the downstream send node
    assert len(cmds) == 1, f"expected 1 downstream command, got {len(cmds)}"
    assert cmds[0].payload.get("text") == "三天后温馨提醒"
    assert has_pending is True
    assert run.status == "completed"


def test_switch_routes_to_case_branch():
    has_pending, cmds, audits, run = _run(_switch_def(), tags=["vip"])
    branches = [a for a in audits if a.event_type == "switch_branch"]
    assert branches, "switch node must record a switch_branch AuditLog"
    assert branches[0].detail["chosen"] == "n_vip", branches[0].detail
    assert len(cmds) == 1
    assert cmds[0].payload.get("text") == "VIP 专属复查方案"
    assert run.status == "completed"


def test_switch_default_when_no_case_matches():
    has_pending, cmds, audits, run = _run(_switch_def(), tags=["new"])
    branches = [a for a in audits if a.event_type == "switch_branch"]
    assert branches
    assert branches[0].detail["chosen"] == "n_normal", branches[0].detail
    assert len(cmds) == 1
    assert cmds[0].payload.get("text") == "普通跟进话术"


def _prefix_def():
    """stage:s1 是 stage:s10 的前缀——子串匹配会误路由，精确匹配才对。"""
    return {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {
                "id": "sw",
                "type": "switch",
                "data": {
                    "config": {
                        "switchOn": "tag",
                        "default": "n_fallback",
                        "cases": [
                            {"equals": "stage:s1", "target": "n_s1"},
                            {"equals": "stage:s10", "target": "n_s10"},
                        ],
                    }
                },
            },
            {"id": "n_s1", "type": "send_message", "data": {"commandType": "send_message", "payload": {"text": "第1步"}}},
            {"id": "n_s10", "type": "send_message", "data": {"commandType": "send_message", "payload": {"text": "第10步"}}},
            {"id": "n_fallback", "type": "send_message", "data": {"commandType": "send_message", "payload": {"text": "兜底"}}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "sw"},
            {"id": "e2", "source": "sw", "target": "n_s1"},
            {"id": "e3", "source": "sw", "target": "n_s10"},
            {"id": "e4", "source": "sw", "target": "n_fallback"},
        ],
    }


def test_switch_tag_exact_match_avoids_prefix_collision():
    """回归：标签走精确匹配，stage:s10 不得被 stage:s1 抢走。"""
    _, cmds, audits, _ = _run(_prefix_def(), tags=["stage:s10"])
    assert _chosen_of(audits) == "n_s10", _chosen_of(audits)
    assert cmds[0].payload.get("text") == "第10步"

    _, cmds1, audits1, _ = _run(_prefix_def(), tags=["stage:s1"])
    assert _chosen_of(audits1) == "n_s1"
    assert cmds1[0].payload.get("text") == "第1步"


def test_switch_tag_no_partial_match():
    """精确匹配下，'stage:s1x' 这类近似标签应落到 default。"""
    _, cmds, audits, _ = _run(_prefix_def(), tags=["stage:s1x"])
    assert _chosen_of(audits) == "n_fallback"
    assert cmds[0].payload.get("text") == "兜底"


def _last_text_def():
    return {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "a", "type": "agent", "data": {"agentType": "sales_progress"}},
            {
                "id": "sw",
                "type": "switch",
                "data": {
                    "config": {
                        "switchOn": "last_text",
                        "default": "n_other",
                        "cases": [{"equals": "报价", "target": "n_quote"}],
                    }
                },
            },
            {"id": "n_quote", "type": "send_message", "data": {"commandType": "send_message", "payload": {"text": "走报价分支"}}},
            {"id": "n_other", "type": "send_message", "data": {"commandType": "send_message", "payload": {"text": "走其他分支"}}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "a"},
            {"id": "e2", "source": "a", "target": "sw"},
            {"id": "e3", "source": "sw", "target": "n_quote"},
            {"id": "e4", "source": "sw", "target": "n_other"},
        ],
    }


def test_switch_last_text_uses_contains_matching():
    """自由文本仍走包含匹配：sales_progress stub 回复里含「报价」即命中。"""
    _, cmds, audits, _ = _run(_last_text_def())
    assert _chosen_of(audits) == "n_quote", _chosen_of(audits)
    assert cmds[0].payload.get("text") == "走报价分支"


def test_switch_handles_null_contact():
    """contact 为 NULL 时不得抛 AttributeError，应落 default。"""
    db = SessionLocal()
    try:
        proj = Project(id=_uid("tsprj"), name="ts")
        db.add(proj)
        db.flush()
        wfv = WorkflowVersion(
            id=_uid("tswfv"), project_id=proj.id, name="ts", status="published", definition=_switch_def()
        )
        db.add(wfv)
        db.flush()
        conv = Conversation(
            id=_uid("tsconv"), project_id=proj.id, channel_account_id="ca_ts",
            conversation_type="direct", subject="t", owner_type="ai",
            handoff_status="none", current_workflow_version_id=wfv.id,
            contact=None,  # 关键：NULL
        )
        db.add(conv)
        db.flush()
        run = WorkflowRun(
            id=_uid("tsrun"), project_id=proj.id, conversation_id=conv.id,
            workflow_version_id=wfv.id, status="running", trigger_type="manual",
        )
        db.add(run)
        db.flush()
        orch._step_nodes(
            db, run=run, conversation=conv, definition=wfv.definition,
            device_id="dev_ts", channel_account_id="ca_ts",
        )
        db.commit()
        cmds = db.execute(select(DeviceCommand).where(DeviceCommand.run_id == run.id)).scalars().all()
        assert cmds and cmds[0].payload.get("text") == "普通跟进话术"
    finally:
        db.close()


if __name__ == "__main__":
    test_timer_records_auditlog_and_continues()
    test_switch_routes_to_case_branch()
    test_switch_default_when_no_case_matches()
    test_switch_tag_exact_match_avoids_prefix_collision()
    test_switch_tag_no_partial_match()
    test_switch_last_text_uses_contains_matching()
    test_switch_handles_null_contact()
    print("ALL TIMER/SWITCH TESTS PASSED")

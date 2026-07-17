"""Demo seed data so the P0 chain is runnable out of the box.

Creates a demo project (id matching the Bruno collection's projectId
"01JPROJECT"), a bot, and one published workflow version ("wf_v1") whose node
graph the orchestration engine walks on every inbound message:

    start -> agent(qa) -> device_command(send_message) -> end

Idempotent: safe to call on every startup.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    AgentInvocation,
    Bot,
    Conversation,
    Device,
    DeviceCommand,
    Message,
    PolicyDecision,
    Project,
    SessionRuntime,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowVersion,
)

DEMO_PROJECT_ID = "01JPROJECT"
DEMO_WORKFLOW_ID = "wf_v1"
DEMO_CONVERSATION_ID = "conv_demo"
DEMO_DEVICE_ID = "dev_demo"
DEMO_BOT_ID = "bot_demo"

DEMO_DEFINITION = {
    "nodes": [
        {"id": "n_start", "type": "start", "data": {}},
        {"id": "n_qa", "type": "agent", "data": {"agentType": "qa"}},
        {
            "id": "n_cmd",
            "type": "device_command",
            "data": {
                "commandType": "send_message",
                "payload": {
                    "messageType": "text",
                    "contentText": "您好，我是您的专属顾问，很高兴为您服务～",
                },
            },
        },
        {"id": "n_end", "type": "end", "data": {}},
    ],
    "edges": [
        {"source": "n_start", "target": "n_qa"},
        {"source": "n_qa", "target": "n_cmd"},
        {"source": "n_cmd", "target": "n_end"},
    ],
}


def seed_demo(db: Session) -> None:
    existing = db.get(Project, DEMO_PROJECT_ID)
    if existing is not None:
        return

    project = Project(id=DEMO_PROJECT_ID, name="Demo Project", description="Morphix MVP demo project", status="active")
    db.add(project)
    db.flush()

    bot = Bot(id="bot_demo", project_id=DEMO_PROJECT_ID, name="Demo Bot", status="active")
    db.add(bot)
    db.flush()

    wfv = WorkflowVersion(
        id=DEMO_WORKFLOW_ID,
        project_id=DEMO_PROJECT_ID,
        name="Demo Workflow v1",
        version=1,
        status="published",
        definition=DEMO_DEFINITION,
        published_at=datetime.now(timezone.utc),
    )
    db.add(wfv)
    db.flush()

    # Stable device so the conversation can issue a device_command seed.
    db.add(
        Device(
            id=DEMO_DEVICE_ID,
            project_id=DEMO_PROJECT_ID,
            channel_account_id="wa_demo",
            channel_type="whatsapp",
            account_type="business",
            device_token="seed-token-demo",
            token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            status="online",
            device_meta={"label": "Demo Device"},
            last_heartbeat_at=datetime.now(timezone.utc),
        )
    )
    db.flush()

    _seed_conversation(db)

    db.commit()


def _seed_conversation(db: Session) -> None:
    if db.get(Conversation, DEMO_CONVERSATION_ID) is not None:
        return

    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=DEMO_CONVERSATION_ID,
        project_id=DEMO_PROJECT_ID,
        channel_account_id="wa_demo",
        conversation_type="direct",
        subject="WhatsApp 客户咨询",
        owner_type="ai",
        handoff_status="none",
        current_bot_id=DEMO_BOT_ID,
        current_workflow_version_id=DEMO_WORKFLOW_ID,
        contact={
            "displayName": "张三",
            "avatarUrl": "",
            "channel": "whatsapp",
            "phone": "+8613800000000",
        },
    )
    db.add(conv)
    db.flush()

    db.add(
        SessionRuntime(
            conversation_id=DEMO_CONVERSATION_ID,
            hosting_status="enabled",
            session_state="AUTO_HOSTING",
            handoff_status="none",
            interrupt_policy="DROP_NEW",
            current_bot_id=DEMO_BOT_ID,
            current_workflow_version_id=DEMO_WORKFLOW_ID,
        )
    )

    # Messages: one inbound customer text, one outbound agent reply.
    db.add(
        Message(
            conversation_id=DEMO_CONVERSATION_ID,
            seq_no=1,
            sender_type="customer",
            message_type="text",
            content_text="你好，我的订单什么时候发货？",
            sent_at=now,
        )
    )
    db.add(
        Message(
            conversation_id=DEMO_CONVERSATION_ID,
            seq_no=2,
            sender_type="ai",
            message_type="text",
            content_text="您好，我是您的专属顾问，很高兴为您服务～",
            sent_at=now,
        )
    )

    # Workflow run walking the published graph: n_start -> n_qa -> n_cmd -> n_end.
    run_id = "run_demo"
    run = WorkflowRun(
        id=run_id,
        project_id=DEMO_PROJECT_ID,
        conversation_id=DEMO_CONVERSATION_ID,
        workflow_version_id=DEMO_WORKFLOW_ID,
        status="completed",
        trigger_type="message",
        current_node_id="n_end",
        started_at=now,
        ended_at=now,
        result_summary="会话已按工作流完成自动应答。",
        root_run_id=run_id,
    )
    db.add(run)
    db.flush()

    steps = [
        WorkflowRunStep(
            run_id=run_id,
            node_execution_id="exec_start",
            node_id="n_start",
            node_type="start",
            status="succeeded",
            duration_ms=1,
        ),
        WorkflowRunStep(
            run_id=run_id,
            node_execution_id="exec_qa",
            node_id="n_qa",
            node_type="agent",
            status="succeeded",
            duration_ms=820,
            executor_type="agent",
        ),
        WorkflowRunStep(
            run_id=run_id,
            node_execution_id="exec_cmd",
            node_id="n_cmd",
            node_type="device_command",
            status="succeeded",
            duration_ms=45,
            executor_type="device",
        ),
        WorkflowRunStep(
            run_id=run_id,
            node_execution_id="exec_end",
            node_id="n_end",
            node_type="end",
            status="succeeded",
            duration_ms=0,
        ),
    ]
    for s in steps:
        db.add(s)

    db.add(
        AgentInvocation(
            run_id=run_id,
            node_execution_id="exec_qa",
            agent_type="qa",
            model_name="stub",
            latency_ms=820,
            estimated_cost=0.0,
            status="succeeded",
            confidence=0.92,
        )
    )

    db.add(
        DeviceCommand(
            project_id=DEMO_PROJECT_ID,
            device_id=DEMO_DEVICE_ID,
            channel_account_id="wa_demo",
            conversation_id=DEMO_CONVERSATION_ID,
            run_id=run_id,
            command_type="send_message",
            payload={
                "messageType": "text",
                "contentText": "您好，我是您的专属顾问，很高兴为您服务～",
            },
            status="done",
            issued_at=now,
            done_at=now,
            idempotency_key="seed-demo-cmd-1",
        )
    )

    db.add(
        PolicyDecision(
            project_id=DEMO_PROJECT_ID,
            conversation_id=DEMO_CONVERSATION_ID,
            run_id=run_id,
            decision_type="interrupt",
            decision="allow",
            reason_codes=["auto_reply_allowed"],
            model_profile="stub",
        )
    )

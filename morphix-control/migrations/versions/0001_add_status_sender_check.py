"""add check constraints for workflow_runs.status, messages.sender_type,
and agent_invocations.status

Revision ID: 0001_add_status_sender_check
Revises: 0000_baseline_tables
Create Date: 2026-07-17 23:30:00.000000

Baseline migration for morphix-control. Adds CHECK constraints previously
enforced only by an ad-hoc script.

Allowed value sets are sourced from the API schema (app/schemas/__init__.py):
  - WorkflowRunStatus: pending, running, waiting, interrupted, failed,
    cancelled, completed  (note: "succeeded" is NOT valid here)
  - SenderType: customer, ai, human, system, device
  - AgentStatus: pending, succeeded, failed, blocked

The upgrade first normalizes known historical dirty values:
  - workflow_runs.status:  "succeeded"  -> "completed"
  - messages.sender_type:  "bot"        -> "ai"
Then it guards against any remaining unexpected values via _check_clean,
and finally creates the constraints.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_add_status_sender_check"
down_revision: Union[str, None] = "0000_baseline_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RUN_STATUSES = (
    "pending",
    "running",
    "waiting",
    "interrupted",
    "failed",
    "cancelled",
    "completed",
)
SENDER_TYPES = ("customer", "ai", "human", "system", "device")
AGENT_STATUSES = ("pending", "succeeded", "failed", "blocked")

MESSAGE = (
    "Found {count} row(s) in {table}.{column} with a value outside the allowed "
    "set {allowed}. Fix the data before running this migration. "
    "Offending values: {values}."
)


def _in_list(values: Sequence[str]) -> str:
    # SQLite does not support arrays; build an IN (...) list of literals.
    return ", ".join(f"'{v}'" for v in values)


def _check_clean(connection, table: str, column: str, allowed: Sequence[str]) -> None:
    placeholders = _in_list(allowed)
    result = connection.execute(
        sa.text(
            f"SELECT DISTINCT {column} FROM {table} "
            f"WHERE {column} IS NOT NULL AND {column} NOT IN ({placeholders})"
        )
    )
    bad = [row[0] for row in result]
    if bad:
        count_result = connection.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} "
                f"WHERE {column} IS NOT NULL AND {column} NOT IN ({placeholders})"
            )
        )
        count = count_result.scalar() or 0
        raise RuntimeError(
            MESSAGE.format(
                count=count,
                table=table,
                column=column,
                allowed=tuple(allowed),
                values=bad,
            )
        )


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Normalize known historical dirty values before constraining.
    connection.execute(
        sa.text(
            "UPDATE workflow_runs SET status = 'completed' "
            "WHERE status = 'succeeded'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE messages SET sender_type = 'ai' WHERE sender_type = 'bot'"
        )
    )

    # 2. Guard against any remaining unexpected values.
    _check_clean(connection, "workflow_runs", "status", RUN_STATUSES)
    _check_clean(connection, "messages", "sender_type", SENDER_TYPES)
    _check_clean(connection, "agent_invocations", "status", AGENT_STATUSES)

    # 3. Create the constraints.
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.create_check_constraint(
            "ck_workflow_runs_status",
            sa.text(
                "status IN ('pending','running','waiting','interrupted',"
                "'failed','cancelled','completed')"
            ),
        )

    with op.batch_alter_table("messages") as batch_op:
        batch_op.create_check_constraint(
            "ck_messages_sender_type",
            sa.text("sender_type IN ('customer','ai','human','system','device')"),
        )

    with op.batch_alter_table("agent_invocations") as batch_op:
        batch_op.create_check_constraint(
            "ck_agent_invocations_status",
            sa.text("status IN ('pending','succeeded','failed','blocked')"),
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_invocations") as batch_op:
        batch_op.drop_constraint("ck_agent_invocations_status", type_="check")

    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_constraint("ck_messages_sender_type", type_="check")

    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint("ck_workflow_runs_status", type_="check")

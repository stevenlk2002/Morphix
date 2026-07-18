from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import json
import sqlite3
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[3]
DATABASE_PATH = ROOT_DIR / "database" / "morphix_mvp.db"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Morphix MVP API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1181", "http://127.0.0.1:1181"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HandoffRequest(BaseModel):
    operator: str = "运营人员"
    reason: str = "manual_takeover"


class SopCreateRequest(BaseModel):
    name: str
    trigger: str


class BotCreateRequest(BaseModel):
    name: str
    project: str = "GlowLab"
    workflow: str = "销售接待主流程"
    tone: str = "亲切专业"
    trainingPrompt: str = ""


class ChannelAccountCreateRequest(BaseModel):
    channel: str
    accountName: str
    boundBot: str
    dailyQuota: int = 200


class TagCreateRequest(BaseModel):
    name: str
    color: str = "blue"
    rule: str = ""


class WorkflowNodeUpdateRequest(BaseModel):
    label: str
    nodeType: str = "action"
    config: dict = {}


def get_conn() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              action TEXT NOT NULL,
              target TEXT NOT NULL,
              detail TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bots (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              project TEXT NOT NULL,
              status TEXT NOT NULL,
              workflow TEXT NOT NULL,
              tone TEXT NOT NULL,
              training_prompt TEXT NOT NULL DEFAULT '',
              score INTEGER NOT NULL DEFAULT 70,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS channel_accounts (
              id TEXT PRIMARY KEY,
              channel TEXT NOT NULL,
              account_name TEXT NOT NULL,
              status TEXT NOT NULL,
              bound_bot TEXT NOT NULL,
              daily_quota INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS customer_tags (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              color TEXT NOT NULL DEFAULT 'blue',
              rule TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS workflow_nodes (
              id TEXT PRIMARY KEY,
              workflow_id TEXT NOT NULL,
              node_order INTEGER NOT NULL,
              node_type TEXT NOT NULL,
              label TEXT NOT NULL,
              config TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sops (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              trigger_rule TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        seed_defaults(conn)


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def seed_defaults(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0] == 0:
        for bot in dashboard_payload()["bots"]:
            conn.execute(
                "INSERT INTO bots(id, name, project, status, workflow, tone, training_prompt, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (bot["id"], bot["name"], bot["project"], bot["status"], bot["workflow"], bot["tone"], "围绕客户意图生成专业、合规、可转人工的话术。", bot["score"]),
            )
    if conn.execute("SELECT COUNT(*) FROM channel_accounts").fetchone()[0] == 0:
        rows = [
            ("ch-1", "企业微信", "企微-华东01", "online", "美妆销售顾问", 600),
            ("ch-2", "WhatsApp", "WA-Biz-02", "online", "WhatsApp 成交助理", 300),
            ("ch-3", "微信群", "宝妈护肤交流群", "warning", "群聊识别 Agent", 120),
        ]
        conn.executemany("INSERT INTO channel_accounts(id, channel, account_name, status, bound_bot, daily_quota) VALUES (?, ?, ?, ?, ?, ?)", rows)
    if conn.execute("SELECT COUNT(*) FROM customer_tags").fetchone()[0] == 0:
        rows = [("tag-1", "高意向", "green", "最近 7 天主动咨询价格或预约"), ("tag-2", "价格咨询", "gold", "消息包含价格、套餐、费用"), ("tag-3", "预约演示", "blue", "明确表达希望看演示")]
        conn.executemany("INSERT INTO customer_tags(id, name, color, rule) VALUES (?, ?, ?, ?)", rows)
    if conn.execute("SELECT COUNT(*) FROM workflow_nodes WHERE workflow_id = 'w-1'").fetchone()[0] == 0:
        nodes = ["开始触发", "客户筛选", "知识检索", "AI 生成话术", "渠道发送", "标签沉淀"]
        for index, label in enumerate(nodes, start=1):
            conn.execute(
                "INSERT INTO workflow_nodes(id, workflow_id, node_order, node_type, label, config) VALUES (?, ?, ?, ?, ?, ?)",
                (f"wn-{index}", "w-1", index, "action" if index > 1 else "trigger", label, json.dumps({"enabled": True}, ensure_ascii=False)),
            )


def dashboard_payload() -> dict:
    return {
        "stats": {
            "activeProjects": 4,
            "channelAccounts": 28,
            "aiSessions": 1264,
            "conversionRate": "18.7%",
        },
        "bots": [
            {"id": "bot-1", "name": "美妆销售顾问", "project": "GlowLab", "status": "online", "workflow": "销售接待主流程", "tone": "亲切专业", "score": 92},
            {"id": "bot-2", "name": "企微售后助手", "project": "Morphix Demo", "status": "training", "workflow": "售后问题处理", "tone": "耐心清晰", "score": 81},
            {"id": "bot-3", "name": "WhatsApp 成交助理", "project": "Global Fit", "status": "online", "workflow": "海外询盘跟进", "tone": "国际化", "score": 88},
        ],
        "sessions": [
            {"id": "s-1", "name": "张先生", "channel": "企业微信", "bot": "美妆销售顾问", "state": "AI托管", "intent": "价格咨询", "last": "标准版支持多少个账号？", "time": "2分钟前"},
            {"id": "s-2", "name": "Alicia", "channel": "WhatsApp", "bot": "WhatsApp 成交助理", "state": "人工接管", "intent": "预约演示", "last": "Can we schedule a demo?", "time": "8分钟前"},
            {"id": "s-3", "name": "宝妈护肤交流群", "channel": "微信群", "bot": "群聊识别 Agent", "state": "AI托管", "intent": "群内意向", "last": "有人问优惠活动", "time": "14分钟前"},
        ],
        "customers": [
            {"id": "c-1", "name": "张先生", "level": "高意向", "tags": ["价格咨询", "预约演示"], "stage": "需求挖掘", "owner": "企微-华东01"},
            {"id": "c-2", "name": "Alicia", "level": "中意向", "tags": ["海外客户", "WhatsApp"], "stage": "产品推荐", "owner": "WA-Biz-02"},
            {"id": "c-3", "name": "林女士", "level": "高意向", "tags": ["敏感肌", "复购"], "stage": "逼单促销", "owner": "微信-美妆03"},
        ],
        "workflows": [
            {"id": "w-1", "name": "销售接待主流程", "nodes": 9, "status": "已发布", "updatedAt": "今天 10:24"},
            {"id": "w-2", "name": "知识库严格问答", "nodes": 6, "status": "草稿", "updatedAt": "昨天 19:02"},
            {"id": "w-3", "name": "群聊意向转私聊", "nodes": 11, "status": "灰度中", "updatedAt": "周一 15:40"},
        ],
    }


def row_to_bot(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "project": row["project"], "status": row["status"], "workflow": row["workflow"], "tone": row["tone"], "trainingPrompt": row["training_prompt"], "score": row["score"]}


def row_to_channel(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "channel": row["channel"], "accountName": row["account_name"], "status": row["status"], "boundBot": row["bound_bot"], "dailyQuota": row["daily_quota"]}


def row_to_tag(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "color": row["color"], "rule": row["rule"]}


def workflow_node_rows(workflow_id: str) -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM workflow_nodes WHERE workflow_id = ? ORDER BY node_order", (workflow_id,)).fetchall()
    return [{"id": row["id"], "workflowId": row["workflow_id"], "order": row["node_order"], "nodeType": row["node_type"], "label": row["label"], "config": json.loads(row["config"] or "{}")} for row in rows]


@app.get("/api/health")
def health() -> dict:
    return {"status": "healthy", "service": "morphix-backend", "database": str(DATABASE_PATH)}


@app.get("/api/dashboard")
def dashboard() -> dict:
    payload = dashboard_payload()
    init_db()
    with get_conn() as conn:
        payload["bots"] = [row_to_bot(row) for row in conn.execute("SELECT * FROM bots ORDER BY created_at, id").fetchall()]
        payload["channels"] = [row_to_channel(row) for row in conn.execute("SELECT * FROM channel_accounts ORDER BY created_at, id").fetchall()]
        payload["tags"] = [row_to_tag(row) for row in conn.execute("SELECT * FROM customer_tags ORDER BY created_at, id").fetchall()]
    return payload


@app.get("/api/conversations")
def conversations() -> list[dict]:
    return dashboard_payload()["sessions"]


@app.get("/api/conversations/{conversation_id}")
def conversation_detail(conversation_id: str) -> dict:
    session = next((item for item in dashboard_payload()["sessions"] if item["id"] == conversation_id), None)
    return session or {"id": conversation_id, "name": "未知会话", "state": "unknown"}


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, page: int = 1) -> dict:
    messages = [
        {"id": "m-1", "senderType": "customer", "content": "标准版支持多少个账号？"},
        {"id": "m-2", "senderType": "ai", "content": "标准版适合小团队使用，支持基础渠道托管和知识库问答。"},
        {"id": "m-3", "senderType": "system", "content": "已完成需求分析、知识检索、表达控制。"},
    ]
    if page > 1:
        messages.insert(0, {"id": "m-0", "senderType": "customer", "content": "我想先了解价格和部署周期。"})
    return {"conversationId": conversation_id, "page": page, "items": messages, "hasMore": page < 2}


@app.post("/api/conversations/{conversation_id}/handoff")
def handoff(conversation_id: str, payload: HandoffRequest) -> dict:
    init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)",
            ("handoff", conversation_id, f"{payload.operator}:{payload.reason}"),
        )
    return {"conversationId": conversation_id, "handoffStatus": "human", "operator": payload.operator}


@app.get("/api/audit-events")
def audit_events() -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 50").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/workflows")
def workflows() -> list[dict]:
    return dashboard_payload()["workflows"]


@app.get("/api/workflows/{workflow_id}")
def workflow_detail(workflow_id: str) -> dict:
    workflow = next((item for item in dashboard_payload()["workflows"] if item["id"] == workflow_id), None)
    return {
        **(workflow or {"id": workflow_id, "name": "临时工作流", "nodes": 0, "status": "草稿", "updatedAt": "刚刚"}),
        "definition": workflow_node_rows(workflow_id),
    }


@app.patch("/api/workflows/{workflow_id}/nodes/{node_id}")
def update_workflow_node(workflow_id: str, node_id: str, payload: WorkflowNodeUpdateRequest) -> dict:
    init_db()
    config_json = json.dumps(payload.config, ensure_ascii=False)
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM workflow_nodes WHERE workflow_id = ? AND id = ?", (workflow_id, node_id)).fetchone()
        if existing:
            conn.execute("UPDATE workflow_nodes SET label = ?, node_type = ?, config = ? WHERE workflow_id = ? AND id = ?", (payload.label, payload.nodeType, config_json, workflow_id, node_id))
        else:
            next_order = conn.execute("SELECT COALESCE(MAX(node_order), 0) + 1 FROM workflow_nodes WHERE workflow_id = ?", (workflow_id,)).fetchone()[0]
            conn.execute("INSERT INTO workflow_nodes(id, workflow_id, node_order, node_type, label, config) VALUES (?, ?, ?, ?, ?, ?)", (node_id, workflow_id, next_order, payload.nodeType, payload.label, config_json))
        conn.execute("INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)", ("update_workflow_node", node_id, payload.label))
    return {"id": node_id, "workflowId": workflow_id, "label": payload.label, "nodeType": payload.nodeType, "config": payload.config}


@app.post("/api/sops")
def create_sop(payload: SopCreateRequest) -> dict:
    init_db()
    with get_conn() as conn:
        sop_id = make_id("sop")
        conn.execute("INSERT INTO sops(id, name, trigger_rule, status) VALUES (?, ?, ?, ?)", (sop_id, payload.name, payload.trigger, "enabled"))
        conn.execute(
            "INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)",
            ("create_sop", payload.name, payload.trigger),
        )
    return {"id": sop_id, "name": payload.name, "trigger": payload.trigger, "status": "enabled"}


@app.get("/api/bots")
def list_bots() -> list[dict]:
    init_db()
    with get_conn() as conn:
        return [row_to_bot(row) for row in conn.execute("SELECT * FROM bots ORDER BY created_at, id").fetchall()]


@app.post("/api/bots")
def create_bot(payload: BotCreateRequest) -> dict:
    init_db()
    bot_id = make_id("bot")
    with get_conn() as conn:
        conn.execute("INSERT INTO bots(id, name, project, status, workflow, tone, training_prompt, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (bot_id, payload.name, payload.project, "training", payload.workflow, payload.tone, payload.trainingPrompt, 76))
        conn.execute("INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)", ("create_bot", bot_id, payload.name))
    return {"id": bot_id, "name": payload.name, "project": payload.project, "status": "training", "workflow": payload.workflow, "tone": payload.tone, "trainingPrompt": payload.trainingPrompt, "score": 76}


@app.post("/api/bots/{bot_id}/train")
def train_bot(bot_id: str) -> dict:
    init_db()
    with get_conn() as conn:
        conn.execute("UPDATE bots SET status = ?, score = MIN(score + 8, 99) WHERE id = ?", ("online", bot_id))
        conn.execute("INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)", ("train_bot", bot_id, "training completed"))
    return {"id": bot_id, "status": "online", "message": "训练完成"}


@app.get("/api/channel-accounts")
def list_channel_accounts() -> list[dict]:
    init_db()
    with get_conn() as conn:
        return [row_to_channel(row) for row in conn.execute("SELECT * FROM channel_accounts ORDER BY created_at, id").fetchall()]


@app.post("/api/channel-accounts")
def create_channel_account(payload: ChannelAccountCreateRequest) -> dict:
    init_db()
    channel_id = make_id("ch")
    with get_conn() as conn:
        conn.execute("INSERT INTO channel_accounts(id, channel, account_name, status, bound_bot, daily_quota) VALUES (?, ?, ?, ?, ?, ?)", (channel_id, payload.channel, payload.accountName, "online", payload.boundBot, payload.dailyQuota))
        conn.execute("INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)", ("create_channel_account", channel_id, payload.accountName))
    return {"id": channel_id, "channel": payload.channel, "accountName": payload.accountName, "status": "online", "boundBot": payload.boundBot, "dailyQuota": payload.dailyQuota}


@app.get("/api/customer-tags")
def list_customer_tags() -> list[dict]:
    init_db()
    with get_conn() as conn:
        return [row_to_tag(row) for row in conn.execute("SELECT * FROM customer_tags ORDER BY created_at, id").fetchall()]


@app.post("/api/customer-tags")
def create_customer_tag(payload: TagCreateRequest) -> dict:
    init_db()
    tag_id = make_id("tag")
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO customer_tags(id, name, color, rule) VALUES (?, ?, ?, ?)", (tag_id, payload.name, payload.color, payload.rule))
        conn.execute("INSERT INTO audit_events(action, target, detail) VALUES (?, ?, ?)", ("create_customer_tag", payload.name, payload.rule))
    return {"id": tag_id, "name": payload.name, "color": payload.color, "rule": payload.rule}

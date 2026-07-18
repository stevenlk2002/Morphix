"""数据库 schema 与索引定义。

集中管理建表语句与索引，保证：
- 建表语句与 database/init_morphix_mvp.sql 保持一致（幂等 CREATE IF NOT EXISTS）。
- 为高频查询列建立索引，兑现「分页/索引规范」性能落地要求。
- 种子数据仅在表为空时写入，避免重复。
"""
from __future__ import annotations

import json

from .database import DatabaseBackend

# ---- 建表语句（与 database/init_morphix_mvp.sql 对齐）----
SCHEMA_SQL = """
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
CREATE TABLE IF NOT EXISTS knowledge_base (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]',
  source TEXT NOT NULL DEFAULT '手动录入',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS materials (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  size INTEGER NOT NULL,
  category TEXT NOT NULL DEFAULT '未分类',
  url TEXT,
  usage_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  workflow_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  trigger TEXT NOT NULL DEFAULT 'manual',
  config TEXT NOT NULL DEFAULT '{}',
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  channel TEXT NOT NULL,
  bot_id TEXT NOT NULL,
  state TEXT NOT NULL,
  intent TEXT NOT NULL DEFAULT '',
  last_message TEXT NOT NULL DEFAULT '',
  last_time TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  sender_type TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bot_subscriptions (
  bot_id TEXT PRIMARY KEY,
  hosted_sessions INTEGER NOT NULL DEFAULT 0,
  expire_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS channel_seats (
  channel_account_id TEXT PRIMARY KEY,
  seats_left INTEGER NOT NULL DEFAULT 0,
  online_sessions INTEGER NOT NULL DEFAULT 0
);
"""

# ---- 索引定义（性能落地：高频查询列 + 排序列）----
# bots / channel_accounts / customer_tags 均按 created_at, id 排序分页，建立复合索引。
# workflow_nodes 按 workflow_id 过滤 + node_order 排序，建立复合索引。
# audit_events 按 id DESC 取最新，主键已覆盖；额外按 created_at 便于时间范围查询。
# knowledge_base / materials 按 bot_id 过滤 + created_at 排序分页，建立复合索引。
INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_bots_created ON bots(created_at, id);
CREATE INDEX IF NOT EXISTS idx_bots_project ON bots(project);
CREATE INDEX IF NOT EXISTS idx_bots_status ON bots(status);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_created ON channel_accounts(created_at, id);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_status ON channel_accounts(status);
CREATE INDEX IF NOT EXISTS idx_customer_tags_created ON customer_tags(created_at, id);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow ON workflow_nodes(workflow_id, node_order);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_bot ON knowledge_base(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_materials_bot ON materials(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_conversation ON workflow_runs(conversation_id, started_at);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_conversations_bot ON conversations(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_subscriptions_bot ON bot_subscriptions(bot_id);
CREATE INDEX IF NOT EXISTS idx_channel_seats_account ON channel_seats(channel_account_id);
"""


def dashboard_seed() -> dict:
    """种子数据源（与原实现保持一致，保证 contract 不变）。"""
    return {
        "bots": [
            {"id": "bot-1", "name": "美妆销售顾问", "project": "GlowLab", "status": "online", "workflow": "销售接待主流程", "tone": "亲切专业", "score": 92},
            {"id": "bot-2", "name": "企微售后助手", "project": "Morphix Demo", "status": "training", "workflow": "售后问题处理", "tone": "耐心清晰", "score": 81},
            {"id": "bot-3", "name": "WhatsApp 成交助理", "project": "Global Fit", "status": "online", "workflow": "海外询盘跟进", "tone": "国际化", "score": 88},
        ],
    }


def init_schema(backend: DatabaseBackend) -> None:
    """建表 + 建索引 + 种子数据（幂等）。"""
    backend.executescript(SCHEMA_SQL)
    backend.executescript(INDEX_SQL)
    seed_defaults(backend)


def _count(backend: DatabaseBackend, sql: str, params: tuple = ()) -> int:
    """安全取 COUNT(*) 结果，COUNT 查询恒返回一行。"""
    row = backend.query_one(sql, params)
    return int(row["c"]) if row is not None else 0


def seed_defaults(backend: DatabaseBackend) -> None:
    """仅在空表时写入种子数据。"""
    if _count(backend, "SELECT COUNT(*) AS c FROM bots") == 0:
        for bot in dashboard_seed()["bots"]:
            backend.execute(
                "INSERT INTO bots(id, name, project, status, workflow, tone, training_prompt, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (bot["id"], bot["name"], bot["project"], bot["status"], bot["workflow"], bot["tone"], "围绕客户意图生成专业、合规、可转人工的话术。", bot["score"]),
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM channel_accounts") == 0:
        rows = [
            ("ch-1", "企业微信", "企微-华东01", "online", "美妆销售顾问", 600),
            ("ch-2", "WhatsApp", "WA-Biz-02", "online", "WhatsApp 成交助理", 300),
            ("ch-3", "微信群", "宝妈护肤交流群", "warning", "群聊识别 Agent", 120),
        ]
        for row in rows:
            backend.execute(
                "INSERT INTO channel_accounts(id, channel, account_name, status, bound_bot, daily_quota) VALUES (?, ?, ?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_tags") == 0:
        rows = [
            ("tag-1", "高意向", "green", "最近 7 天主动咨询价格或预约"),
            ("tag-2", "价格咨询", "gold", "消息包含价格、套餐、费用"),
            ("tag-3", "预约演示", "blue", "明确表达希望看演示"),
        ]
        for row in rows:
            backend.execute(
                "INSERT INTO customer_tags(id, name, color, rule) VALUES (?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM workflow_nodes WHERE workflow_id = 'w-1'") == 0:
        nodes = ["开始触发", "客户筛选", "知识检索", "AI 生成话术", "渠道发送", "标签沉淀"]
        for index, label in enumerate(nodes, start=1):
            backend.execute(
                "INSERT INTO workflow_nodes(id, workflow_id, node_order, node_type, label, config) VALUES (?, ?, ?, ?, ?, ?)",
                (f"wn-{index}", "w-1", index, "action" if index > 1 else "trigger", label, json.dumps({"enabled": True}, ensure_ascii=False)),
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM workflow_runs") == 0:
        runs = [
            ("run-1", "c-1", "wf-1", "finished", "auto", '{"mode": "auto"}', "2024-01-15 09:12:00", "2024-01-15 09:14:32"),
            ("run-2", "c-1", "wf-1", "running", "manual", '{"mode": "manual"}', "2024-01-15 10:01:11", None),
            ("run-3", "c-2", "wf-2", "interrupted", "manual", '{"mode": "manual"}', "2024-01-15 11:20:45", "2024-01-15 11:22:10"),
        ]
        for row in runs:
            backend.execute(
                "INSERT INTO workflow_runs(id, conversation_id, workflow_id, status, trigger, config, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM conversations") == 0:
        sessions = [
            ("s-1", "张先生", "企业微信", "bot-1", "AI托管", "价格咨询", "标准版支持多少个账号？", "2分钟前"),
            ("s-2", "Alicia", "WhatsApp", "bot-2", "人工接管", "预约演示", "Can we schedule a demo?", "8分钟前"),
            ("s-3", "宝妈护肤交流群", "微信群", "bot-3", "AI托管", "群内意向", "有人问优惠活动", "14分钟前"),
        ]
        for row in sessions:
            backend.execute(
                "INSERT INTO conversations(id, name, channel, bot_id, state, intent, last_message, last_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM messages") == 0:
        for conv_id, msgs in (
            ("s-1", [
                ("m-1", "customer", "标准版支持多少个账号？"),
                ("m-2", "ai", "标准版适合小团队使用，支持基础渠道托管和知识库问答。"),
                ("m-3", "system", "已完成需求分析、知识检索、表达控制。"),
            ]),
            ("s-2", [
                ("m-1", "customer", "Can we schedule a demo?"),
                ("m-2", "ai", "Sure, I can arrange a demo for your team this week."),
                ("m-3", "system", "已转人工接管，等待销售跟进。"),
            ]),
            ("s-3", [
                ("m-1", "customer", "有人问优惠活动"),
                ("m-2", "ai", "已识别群内意向，准备私聊引导。"),
                ("m-3", "system", "群聊意向转私聊流程已触发。"),
            ]),
        ):
            order = 0
            for msg_id, sender_type, content in msgs:
                order += 1
                backend.execute(
                    "INSERT INTO messages(id, conversation_id, sender_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (msg_id, conv_id, sender_type, content, f"2024-01-15 09:{10 + order:02d}:00"),
                )
    if _count(backend, "SELECT COUNT(*) AS c FROM bot_subscriptions") == 0:
        subs = [
            ("bot-1", 120, "2027-06-30 23:59:59"),
            ("bot-2", 300, "2027-12-31 23:59:59"),
            ("bot-3", 80, "2026-12-31 23:59:59"),
        ]
        for row in subs:
            backend.execute(
                "INSERT INTO bot_subscriptions(bot_id, hosted_sessions, expire_at) VALUES (?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM channel_seats") == 0:
        seats = [
            ("ch-1", 580, 20),
            ("ch-2", 285, 15),
            ("ch-3", 110, 10),
        ]
        for row in seats:
            backend.execute(
                "INSERT INTO channel_seats(channel_account_id, seats_left, online_sessions) VALUES (?, ?, ?)",
                row,
            )

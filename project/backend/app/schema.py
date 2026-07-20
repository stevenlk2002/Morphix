"""数据库 schema 与索引定义。

集中管理建表语句与索引，保证：
- 建表语句与 database/init_morphix_mvp.sql 保持一致（幂等 CREATE IF NOT EXISTS）。
- 为高频查询列建立索引，兑现「分页/索引规范」性能落地要求。
- 种子数据仅在表为空时写入，避免重复。
"""
from __future__ import annotations

import json

from .database import DatabaseBackend

# bot_id -> 显示名映射（前端「所属机器人」下拉与列表 robot 列共用）
BOT_NAMES: dict[str, str] = {
    "yefengqiu": "野风秋大健康机器人",
    "fanfuni": "梵芙尼美妆销售机器人",
}

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
  team_id TEXT NOT NULL DEFAULT '',
  channel_type TEXT NOT NULL DEFAULT '',
  protocol TEXT NOT NULL DEFAULT '',
  sessions_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS customer_tags (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT 'blue',
  rule TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, name)
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
  kind TEXT NOT NULL DEFAULT 'common',
  creator TEXT NOT NULL DEFAULT 'system',
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
  source TEXT NOT NULL DEFAULT '上传',
  usage_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS training_records (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  good_count INTEGER NOT NULL DEFAULT 0,
  bad_count INTEGER NOT NULL DEFAULT 0,
  total_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS training_messages (
  id TEXT PRIMARY KEY,
  record_id TEXT NOT NULL,
  bot_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  record_ref TEXT NOT NULL DEFAULT '',
  feedback TEXT,
  msg_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
CREATE TABLE IF NOT EXISTS orchestration_workflows (
  bot_id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS message_logs (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL,
  content_json TEXT NOT NULL DEFAULT '{}',
  question TEXT NOT NULL DEFAULT '',
  account TEXT NOT NULL DEFAULT '',
  session TEXT NOT NULL DEFAULT '',
  channel TEXT NOT NULL DEFAULT '',
  reply_time TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT '成功'
);
CREATE TABLE IF NOT EXISTS message_log_traces (
  id TEXT PRIMARY KEY,
  log_id TEXT NOT NULL,
  node_order INTEGER NOT NULL,
  node_key TEXT NOT NULL DEFAULT '',
  node_name TEXT NOT NULL DEFAULT '',
  node_type TEXT NOT NULL DEFAULT '',
  runtime TEXT NOT NULL DEFAULT '',
  input_json TEXT NOT NULL DEFAULT '{}',
  output_json TEXT NOT NULL DEFAULT '{}',
  code TEXT NOT NULL DEFAULT ''
);

-- ---- 渠道会话管理域（新增表，与资源域 conversations 解耦） ----
CREATE TABLE IF NOT EXISTS teams (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  seats_left  INTEGER NOT NULL DEFAULT 0,
  energy_value INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_contacts (
  id          TEXT PRIMARY KEY,
  account_id  TEXT NOT NULL,
  channel     TEXT NOT NULL DEFAULT '',
  channel_type TEXT NOT NULL DEFAULT 'wechat',
  name        TEXT NOT NULL,
  nickname    TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'customer',
  status      TEXT NOT NULL DEFAULT 'online',
  remark      TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  add_time    TEXT NOT NULL DEFAULT '',
  source      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS customer_profiles (
  id          TEXT PRIMARY KEY,
  contact_id  TEXT NOT NULL,
  phone       TEXT NOT NULL DEFAULT '',
  email       TEXT NOT NULL DEFAULT '',
  company     TEXT NOT NULL DEFAULT '',
  position    TEXT NOT NULL DEFAULT '',
  region      TEXT NOT NULL DEFAULT '',
  age         INTEGER,
  birthday    TEXT NOT NULL DEFAULT '',
  remark      TEXT NOT NULL DEFAULT '',
  add_time    TEXT NOT NULL DEFAULT '',
  add_channel TEXT NOT NULL DEFAULT '',
  signature   TEXT NOT NULL DEFAULT '',
  ai_summary_enabled INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS communication_records (
  id          TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  content     TEXT NOT NULL DEFAULT '',
  ai_summary  TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'note',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_attributes (
  id          TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  name        TEXT NOT NULL DEFAULT '',
  value       TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_sessions (
  id            TEXT PRIMARY KEY,
  account_id    TEXT NOT NULL,
  contact_id    TEXT,
  name          TEXT NOT NULL,
  channel       TEXT NOT NULL DEFAULT '',
  channel_type  TEXT NOT NULL DEFAULT 'wechat',
  last_message  TEXT NOT NULL DEFAULT '',
  last_time     TEXT NOT NULL DEFAULT '',
  unread_count  INTEGER NOT NULL DEFAULT 0,
  read_status   TEXT NOT NULL DEFAULT 'unread',
  hosted_status TEXT NOT NULL DEFAULT 'unhosted',
  hosted_bot_id TEXT,
  owner         TEXT NOT NULL DEFAULT '',
  online_status TEXT NOT NULL DEFAULT 'online',
  session_type  TEXT NOT NULL DEFAULT '外部联系人',
  external_tag  TEXT NOT NULL DEFAULT '外部',
  add_time      TEXT NOT NULL DEFAULT '',
  hosting_chain TEXT NOT NULL DEFAULT '-'
);

CREATE TABLE IF NOT EXISTS hosting_sessions (
  id             TEXT PRIMARY KEY,
  session_key    TEXT NOT NULL DEFAULT '',
  account_id     TEXT NOT NULL,
  customer_name  TEXT NOT NULL DEFAULT '',
  customer_remark TEXT NOT NULL DEFAULT '',
  add_time       TEXT NOT NULL DEFAULT '',
  hosted_status  TEXT NOT NULL DEFAULT 'unhosted',
  hosting_chain  TEXT NOT NULL DEFAULT '-'
);

CREATE TABLE IF NOT EXISTS hosting_rules (
  id                  TEXT PRIMARY KEY,
  account_id          TEXT,
  auto_resume_seconds INTEGER,
  auto_cancel_enabled INTEGER NOT NULL DEFAULT 0,
  created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wechat_subjects (
  id          TEXT PRIMARY KEY,
  full_name   TEXT NOT NULL,
  short_name  TEXT NOT NULL,
  corp_id     TEXT NOT NULL,
  config_json TEXT NOT NULL DEFAULT '{}'
);

-- ---- 客户管理域新增表 ----
CREATE TABLE IF NOT EXISTS customer_tag_groups (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  is_hot      INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_tag_relations (
  customer_id TEXT NOT NULL,
  tag_id      TEXT NOT NULL,
  PRIMARY KEY (customer_id, tag_id)
);

CREATE TABLE IF NOT EXISTS customer_groups (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  type        TEXT NOT NULL DEFAULT 'custom',
  count       INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  editor      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS customer_group_members (
  group_id    TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  PRIMARY KEY (group_id, customer_id)
);

-- ---- 运营任务域 ----
CREATE TABLE IF NOT EXISTS operation_tasks (
  id               TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  task_type        TEXT NOT NULL,
  channel_type     TEXT NOT NULL DEFAULT '',
  session_type     TEXT NOT NULL DEFAULT '',
  content_blocks   TEXT NOT NULL DEFAULT '[]',
  hosting_action   TEXT NOT NULL DEFAULT '保持不变',
  run_frequency    TEXT NOT NULL DEFAULT '一次',
  run_time         TEXT NOT NULL DEFAULT '',
  effective_start  TEXT NOT NULL DEFAULT '',
  effective_end    TEXT NOT NULL DEFAULT '',
  cron_expression  TEXT NOT NULL DEFAULT '',
  schedule_type    TEXT NOT NULL DEFAULT '',
  schedule_config  TEXT NOT NULL DEFAULT '',
  run_status       TEXT NOT NULL DEFAULT '未运行',
  enabled          INTEGER NOT NULL DEFAULT 1,
  next_run_time    TEXT NOT NULL DEFAULT '',
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_task_targets (
  id            TEXT PRIMARY KEY,
  task_id       TEXT NOT NULL,
  target_type   TEXT NOT NULL DEFAULT 'static',
  session_id    TEXT NOT NULL,
  filter_rules  TEXT NOT NULL DEFAULT '{}',
  created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (task_id) REFERENCES operation_tasks(id) ON DELETE CASCADE
);

-- ---- 运营SOP域 ----
CREATE TABLE IF NOT EXISTS operation_sops (
  id               TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  type             TEXT NOT NULL DEFAULT 'customer',
  channel          TEXT NOT NULL DEFAULT '',
  enabled          INTEGER NOT NULL DEFAULT 1,
  status           TEXT NOT NULL DEFAULT 'stopped',
  trigger_type     TEXT NOT NULL DEFAULT '',
  trigger_config   TEXT NOT NULL DEFAULT '{}',
  nodes_json       TEXT NOT NULL DEFAULT '[]',
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_sop_records (
  id               TEXT PRIMARY KEY,
  sop_id           TEXT NOT NULL,
  run_time         TEXT NOT NULL DEFAULT '',
  run_status       TEXT NOT NULL DEFAULT 'success',
  error_message    TEXT NOT NULL DEFAULT '',
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
CREATE INDEX IF NOT EXISTS idx_knowledge_base_bot_kind ON knowledge_base(bot_id, kind, created_at);
CREATE INDEX IF NOT EXISTS idx_materials_bot ON materials(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_materials_bot_source ON materials(bot_id, source, created_at);
CREATE INDEX IF NOT EXISTS idx_training_records_bot ON training_records(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_training_messages_record ON training_messages(record_id, msg_order);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_conversation ON workflow_runs(conversation_id, started_at);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_conversations_bot ON conversations(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_subscriptions_bot ON bot_subscriptions(bot_id);
CREATE INDEX IF NOT EXISTS idx_channel_seats_account ON channel_seats(channel_account_id);
CREATE INDEX IF NOT EXISTS idx_orch_wf_bot ON orchestration_workflows(bot_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_bot ON message_logs(bot_id, reply_time);
CREATE INDEX IF NOT EXISTS idx_message_log_traces_log ON message_log_traces(log_id, node_order);

-- ---- 渠道会话管理域索引 ----
CREATE INDEX IF NOT EXISTS idx_channel_accounts_team      ON channel_accounts(team_id);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_ctype    ON channel_accounts(channel_type, status);
CREATE INDEX IF NOT EXISTS idx_channel_contacts_account  ON channel_contacts(account_id, type, status);
CREATE INDEX IF NOT EXISTS idx_channel_sessions_account  ON channel_sessions(account_id, read_status, hosted_status, online_status);
CREATE INDEX IF NOT EXISTS idx_hosting_sessions_account  ON hosting_sessions(account_id, hosted_status);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_contact ON customer_profiles(contact_id);
CREATE INDEX IF NOT EXISTS idx_communication_records_cust ON communication_records(customer_id);
CREATE INDEX IF NOT EXISTS idx_custom_attributes_cust    ON custom_attributes(customer_id);

-- ---- 客户管理域索引 ----
CREATE INDEX IF NOT EXISTS idx_customer_tag_groups_name  ON customer_tag_groups(name);
CREATE INDEX IF NOT EXISTS idx_customer_tags_group       ON customer_tags(group_id);
CREATE INDEX IF NOT EXISTS idx_customer_tag_relations_cust ON customer_tag_relations(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_tag_relations_tag  ON customer_tag_relations(tag_id);
CREATE INDEX IF NOT EXISTS idx_customer_groups_type       ON customer_groups(type);
CREATE INDEX IF NOT EXISTS idx_customer_group_members_g   ON customer_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_customer_group_members_c   ON customer_group_members(customer_id);

-- ---- 运营任务域索引 ----
CREATE INDEX IF NOT EXISTS idx_operation_tasks_type   ON operation_tasks(task_type, enabled);
CREATE INDEX IF NOT EXISTS idx_operation_tasks_status ON operation_tasks(run_status);
CREATE INDEX IF NOT EXISTS idx_operation_tasks_enabled ON operation_tasks(enabled, next_run_time);
CREATE INDEX IF NOT EXISTS idx_op_task_targets_task    ON operation_task_targets(task_id);
CREATE INDEX IF NOT EXISTS idx_op_task_targets_session ON operation_task_targets(session_id);

-- ---- 运营SOP域索引 ----
CREATE INDEX IF NOT EXISTS idx_operation_sops_type   ON operation_sops(type, enabled);
CREATE INDEX IF NOT EXISTS idx_operation_sops_status ON operation_sops(status);
CREATE INDEX IF NOT EXISTS idx_operation_sops_enabled ON operation_sops(enabled);
CREATE INDEX IF NOT EXISTS idx_operation_sop_records_sop ON operation_sop_records(sop_id, created_at);
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
    """建表 + 幂等迁移 + 建索引 + 种子数据。"""
    backend.executescript(SCHEMA_SQL)
    migrate_schema(backend)
    backend.executescript(INDEX_SQL)
    seed_defaults(backend)


def _has_column(backend: DatabaseBackend, table: str, column: str) -> bool:
    """检测表中是否存在某列（用于幂等迁移）。"""
    rows = backend.query(f"PRAGMA table_info({table})")
    return any((r.get("name") or "") == column for r in rows)


def migrate_schema(backend: DatabaseBackend) -> None:
    """为已存在的旧表追加新列（幂等；新库由 CREATE 语句直接带列，这里不重复）。

    旧库执行 CREATE TABLE IF NOT EXISTS 时不会为已存在的表补列，
    因此用 PRAGMA table_info 检测缺列后 ALTER TABLE ADD COLUMN。
    """
    kb_cols = {
        "kind": "TEXT NOT NULL DEFAULT 'common'",
        "creator": "TEXT NOT NULL DEFAULT 'system'",
    }
    for col, ddl in kb_cols.items():
        if not _has_column(backend, "knowledge_base", col):
            backend.execute(f"ALTER TABLE knowledge_base ADD COLUMN {col} {ddl}")
    if not _has_column(backend, "materials", "source"):
        backend.execute("ALTER TABLE materials ADD COLUMN source TEXT NOT NULL DEFAULT '上传'")
    # 渠道会话管理域：为已存在的旧 channel_accounts 追加新列（幂等 ALTER）
    _channel_account_cols = {
        "team_id": "TEXT NOT NULL DEFAULT ''",
        "channel_type": "TEXT NOT NULL DEFAULT ''",
        "protocol": "TEXT NOT NULL DEFAULT ''",
        "sessions_count": "INTEGER NOT NULL DEFAULT 0",
    }
    for col, ddl in _channel_account_cols.items():
        if not _has_column(backend, "channel_accounts", col):
            backend.execute(f"ALTER TABLE channel_accounts ADD COLUMN {col} {ddl}")
    # 训练表为全新表，CREATE IF NOT EXISTS 同时覆盖新库与旧库，无需 ALTER。

    # ---- 客户管理域迁移 ----
    # customer_profiles.ai_summary_enabled
    if not _has_column(backend, "customer_profiles", "ai_summary_enabled"):
        backend.execute("ALTER TABLE customer_profiles ADD COLUMN ai_summary_enabled INTEGER NOT NULL DEFAULT 0")

    # customer_tags: v1 → v2（增加 group_id + UNIQUE(group_id, name)）
    if not _has_column(backend, "customer_tags", "group_id"):
        # 先加列让旧数据有默认值
        backend.execute("ALTER TABLE customer_tags ADD COLUMN group_id TEXT NOT NULL DEFAULT ''")
        # SQLite 不支持直接修改约束，通过新建表→迁移→删旧表→重命名完成
        try:
            backend.execute("""
                CREATE TABLE customer_tags_v2 (
                  id TEXT PRIMARY KEY,
                  group_id TEXT NOT NULL DEFAULT '',
                  name TEXT NOT NULL,
                  color TEXT NOT NULL DEFAULT 'blue',
                  rule TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(group_id, name)
                )
            """)
            backend.execute("INSERT INTO customer_tags_v2 SELECT id, group_id, name, color, rule, created_at FROM customer_tags")
            backend.execute("DROP TABLE customer_tags")
            backend.execute("ALTER TABLE customer_tags_v2 RENAME TO customer_tags")
        except Exception:
            pass  # 字段已存在或迁移已完成
        # 为旧标签创建默认标签组「默认组」
        if _count(backend, "SELECT COUNT(*) AS c FROM customer_tag_groups WHERE id = 'tg-default'") == 0:
            backend.execute(
                "INSERT INTO customer_tag_groups(id, name, is_hot) VALUES (?, ?, ?)",
                ("tg-default", "默认组", 0),
            )
        # 将旧标签的 group_id 设为 tg-default
        backend.execute("UPDATE customer_tags SET group_id = 'tg-default' WHERE group_id = ''")


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
            # 对齐原型：竹绿-健康 / 恒康倍力 / 福寿康
            ("acc-zhulu", "企业微信", "竹绿-健康", "online", "yefengqiu", 600, "team-initial", "wecom", "ipad", 181),
            ("acc-hengkang", "企业微信", "恒康倍力", "online", "yangqicheng", 300, "team-initial", "wecom", "ipad", 73),
            ("acc-fushou", "微信", "福寿康", "offline", "yefengqiu", 120, "team-initial", "wechat", "", 12),
        ]
        for row in rows:
            backend.execute(
                "INSERT INTO channel_accounts(id, channel, account_name, status, bound_bot, daily_quota, team_id, channel_type, protocol, sessions_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_tags") == 0:
        rows = [
            ("tag-1", "tg-default", "高意向", "green", "最近 7 天主动咨询价格或预约"),
            ("tag-2", "tg-default", "价格咨询", "gold", "消息包含价格、套餐、费用"),
            ("tag-3", "tg-default", "预约演示", "blue", "明确表达希望看演示"),
        ]
        for row in rows:
            backend.execute(
                "INSERT INTO customer_tags(id, group_id, name, color, rule) VALUES (?, ?, ?, ?, ?)",
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
                # 消息 id 全局唯一：前缀会话 id，避免跨会话复用 m-1/m-2/m-3 触发 UNIQUE 冲突
                backend.execute(
                    "INSERT INTO messages(id, conversation_id, sender_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (f"{conv_id}-{msg_id}", conv_id, sender_type, content, f"2024-01-15 09:{10 + order:02d}:00"),
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
            ("acc-zhulu", 580, 20),
            ("acc-hengkang", 285, 15),
            ("acc-fushou", 110, 10),
        ]
        for row in seats:
            backend.execute(
                "INSERT INTO channel_seats(channel_account_id, seats_left, online_sessions) VALUES (?, ?, ?)",
                row,
            )

    # ---- 渠道会话管理域种子（teams / contacts / sessions / hosting / wechat_subjects） ----
    if _count(backend, "SELECT COUNT(*) AS c FROM teams") == 0:
        backend.execute(
            "INSERT INTO teams(id, name, seats_left, energy_value) VALUES (?, ?, ?, ?)",
            ("team-initial", "初始团队", 1, 908),
        )

    if _count(backend, "SELECT COUNT(*) AS c FROM channel_contacts") == 0:
        contacts = [
            # 客户 (7)
            ("c-cloud", "acc-zhulu", "@微信", "wechat", "Cloud", "Cloud", "customer", "online", "", "", "2026-06-30 18:27:31", "扫码"),
            ("c-shiqi", "acc-zhulu", "@微信", "wechat", "拾柒", "拾柒", "customer", "online", "", "", "2026-06-30 18:27:32", "扫码"),
            ("c-didi", "acc-zhulu", "@微信", "wechat", "didi", "didi", "customer", "online", "", "", "2026-06-30 18:27:33", "扫码"),
            ("c-xiaoxingxing", "acc-zhulu", "@微信", "wechat", "小星星", "小星星", "customer", "offline", "", "", "2026-06-30 18:27:34", "扫码"),
            ("c-changsheng", "acc-zhulu", "@微信", "wechat", "常胜将军", "常胜将军", "customer", "offline", "", "", "2026-06-30 18:27:35", "扫码"),
            ("c-kuaile", "acc-zhulu", "@微信", "wechat", "快乐的小可爱", "快乐的小可爱", "customer", "offline", "", "", "2026-06-30 18:27:36", "扫码"),
            ("c-kaixin", "acc-zhulu", "@微信", "wechat", "开心", "开心", "customer", "offline", "", "", "2026-06-30 18:27:37", "扫码"),
            # 内部成员 (2)
            ("c-zhangsan", "acc-zhulu", "@企业微信", "wecom", "张三", "张三", "internal", "online", "", "", "2026-06-30 18:27:38", "手动添加"),
            ("c-lisi", "acc-zhulu", "@企业微信", "wecom", "李四", "李四", "internal", "offline", "", "", "2026-06-30 18:27:39", "手动添加"),
            # 客户群聊 (2)
            ("c-group1", "acc-zhulu", "@企业微信", "wecom", "远志-洪创鑫、竹绿-健康、DA星语...", "远志-洪创鑫、竹绿-健康、DA星语...", "customer_group", "online", "", "", "2026-06-30 18:27:40", "扫码"),
            ("c-group2", "acc-zhulu", "@企业微信", "wecom", "中医流体学入门会员", "中医流体学入门会员", "customer_group", "online", "", "", "2026-06-30 18:27:41", "扫码"),
            # 内部群聊 (1)
            ("c-igroup1", "acc-zhulu", "@企业微信", "wecom", "内部运营群", "内部运营群", "internal_group", "offline", "", "", "2026-06-30 18:27:42", "手动添加"),
        ]
        for row in contacts:
            backend.execute(
                "INSERT INTO channel_contacts(id, account_id, channel, channel_type, name, nickname, type, status, remark, description, add_time, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

    if _count(backend, "SELECT COUNT(*) AS c FROM customer_profiles") == 0:
        profiles = [
            ("cp-cloud", "c-cloud", "13800001234", "cloud@example.com", "云康科技", "产品经理", "华东", 28, "1998-03-12", "重点跟进客户", "2026-06-30 18:29:18", "@微信", "健康生活，从今天开始", 1),
            ("cp-didi", "c-didi", "", "", "", "", "", None, "", "已添加微信，待沟通", "2026-07-03 15:35:45", "@微信", "", 0),
            ("cp-zhangsan", "c-zhangsan", "13900005678", "zhangsan@corp.com", "竹绿-健康", "运营专员", "总部", 32, "1994-11-02", "内部成员", "2026-06-30 18:29:20", "@企业微信", "", 0),
            ("cp-changsheng", "c-changsheng", "", "", "", "", "", None, "", "中奖用户", "2026-07-03 11:20:00", "@微信", "", 1),
            ("cp-kaixin", "c-kaixin", "", "", "", "", "", None, "", "新添加客户", "2026-07-03 09:05:00", "@微信", "", 0),
        ]
        for row in profiles:
            backend.execute(
                "INSERT INTO customer_profiles(id, contact_id, phone, email, company, position, region, age, birthday, remark, add_time, add_channel, signature, ai_summary_enabled) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

    if _count(backend, "SELECT COUNT(*) AS c FROM communication_records") == 0:
        backend.execute(
            "INSERT INTO communication_records(id, customer_id, content, ai_summary, type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("cr-1", "cp-didi", "客户咨询了产品使用方式，已发送使用手册链接，客户表示满意。", "客户咨询产品使用方法，已提供使用手册。", "note", "2026-07-03 16:00:00"),
        )

    if _count(backend, "SELECT COUNT(*) AS c FROM custom_attributes") == 0:
        backend.execute(
            "INSERT INTO custom_attributes(id, customer_id, name, value, created_at) VALUES (?, ?, ?, ?, ?)",
            ("ca-1", "cp-didi", "客户等级", "VIP", "2026-07-03 16:10:00"),
        )

    if _count(backend, "SELECT COUNT(*) AS c FROM channel_sessions") == 0:
        sessions = [
            ("ses-drjack", "acc-zhulu", "Dr.Jack 恒康倍力", "@微信", "wechat", "可以的，后续可以用", "10:36", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-06-30 18:29:18", "-"),
            ("ses-tongtian", "acc-zhulu", "通天草-林瞰", "@微信", "wechat", "竹绿-健康：亲爱的您好呀...", "10:41", 2, "unread", "unhosted", None, "竹", "online", "外部联系人", "外部", "2026-06-30 18:29:19", "-"),
            ("ses-zhizu", "acc-zhulu", "知足常乐【中奖】", "@微信", "wechat", "感谢参与本次活动", "09:12", 0, "read", "hosted", "yefengqiu", "竹", "offline", "外部联系人", "外部", "2026-06-30 18:29:20", "-"),
            ("ses-fushou", "acc-zhulu", "福寿康VIP", "@微信", "wechat", "您好，想咨询一下产品", "昨天", 0, "read", "unhosted", None, "竹", "offline", "外部联系人", "外部", "2026-06-30 18:29:21", "-"),
        ]
        for row in sessions:
            backend.execute(
                "INSERT INTO channel_sessions(id, account_id, name, channel, channel_type, last_message, last_time, unread_count, read_status, hosted_status, hosted_bot_id, owner, online_status, session_type, external_tag, add_time, hosting_chain) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

    if _count(backend, "SELECT COUNT(*) AS c FROM messages WHERE conversation_id LIKE 'ses-%'") == 0:
        # 为 4 个 channel_sessions 各写 2-6 条消息（conversation_id = session id）。
        # 注意：不能用 channel_sessions 是否为空做闸门，否则上文写入会话后此处永远被跳过。
        # messages 表另有 s-1/2/3 的演示消息（属于 legacy conversations），会话 id 前缀不同不会冲突。
        session_messages = [
            ("msg-drjack-1", "ses-drjack", "bot", "林总，有事吗", "2026-07-09 18:58:50"),
            ("msg-drjack-2", "ses-drjack", "user", "竹绿-健康：曹医生，不好意思，刚刚是机器人发送的。", "2026-07-09 18:58:52"),
            ("msg-drjack-3", "ses-drjack", "user", "我最近在用AI机器人，替代销售。在训练中", "2026-07-09 18:58:54"),
            ("msg-drjack-4", "ses-drjack", "bot", "哦，好呀。", "2026-07-09 18:58:55"),
            ("msg-drjack-5", "ses-drjack", "user", "我现在在训练的这个机器人很强，可以自动接待无限多个客户，取代人工销售。", "2026-07-09 18:58:56"),
            ("msg-drjack-6", "ses-drjack", "bot", "行，咱以后可以用", "2026-07-09 18:58:57"),
            ("msg-tongtian-1", "ses-tongtian", "user", "竹绿-健康：亲爱的您好呀...", "2026-07-09 18:40:10"),
            ("msg-tongtian-2", "ses-tongtian", "bot", "您好，通天草的库存已经帮您确认啦~", "2026-07-09 18:40:12"),
            ("msg-zhizu-1", "ses-zhizu", "user", "感谢参与本次活动", "2026-07-09 09:12:00"),
            ("msg-zhizu-2", "ses-zhizu", "bot", "恭喜中奖！奖品将于3个工作日内寄出~", "2026-07-09 09:12:05"),
            ("msg-fushou-1", "ses-fushou", "user", "您好，想咨询一下产品", "2026-07-08 20:00:00"),
            ("msg-fushou-2", "ses-fushou", "bot", "您好，福寿康VIP客服为您服务~", "2026-07-08 20:00:03"),
        ]
        for msg_id, conv_id, sender_type, content, ts in session_messages:
            backend.execute(
                "INSERT INTO messages(id, conversation_id, sender_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (msg_id, conv_id, sender_type, content, ts),
            )

    if _count(backend, "SELECT COUNT(*) AS c FROM hosting_sessions") == 0:
        hosting = [
            ("hs-yangyang", "", "acc-zhulu", "洋洋", "", "2026-06-30 18:29:12", "unhosted", "-"),
            ("hs-min", "", "acc-zhulu", "Min", "", "2026-06-30 18:27:09", "unhosted", "-"),
            ("hs-xingyue", "", "acc-zhulu", "xıngyue", "", "2026-06-30 18:27:10", "unhosted", "-"),
            ("hs-wen", "", "acc-zhulu", "文", "", "2026-06-30 18:27:10", "unhosted", "-"),
            ("hs-lili", "", "acc-zhulu", "丽丽", "", "2026-06-30 18:27:13", "unhosted", "-"),
            ("hs-cloud", "", "acc-zhulu", "Cloud", "", "2026-06-30 18:27:14", "unhosted", "-"),
        ]
        for row in hosting:
            backend.execute(
                "INSERT INTO hosting_sessions(id, session_key, account_id, customer_name, customer_remark, add_time, hosted_status, hosting_chain) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

    if _count(backend, "SELECT COUNT(*) AS c FROM hosting_rules") == 0:
        backend.execute(
            "INSERT INTO hosting_rules(id, account_id, auto_resume_seconds, auto_cancel_enabled) VALUES (?, ?, ?, ?)",
            ("hr-1", None, None, 0),
        )

    if _count(backend, "SELECT COUNT(*) AS c FROM wechat_subjects") == 0:
        backend.execute(
            "INSERT INTO wechat_subjects(id, full_name, short_name, corp_id, config_json) VALUES (?, ?, ?, ?, ?)",
            ("wx-subj-1", "医林通健康科技", "医林通", "ww8f2a1c3d4e5", "{}"),
        )

    if _count(backend, "SELECT COUNT(*) AS c FROM orchestration_workflows") == 0:
        import datetime as _dt
        now = _dt.datetime.utcnow().isoformat() + "Z"
        # 野风秋大健康机器人 的默认工作流
        wf1 = {
            "botId": "yefengqiu",
            "version": 1,
            "lastEdited": now,
            "nodes": [
                {"id":"node-1","type":"userInput","position":{"x":60,"y":80},
                 "data":{"label":"用户输入","inputs":{},"config":{}},"selected":False},
                {"id":"node-2","type":"aiChat","position":{"x":320,"y":80},
                 "data":{"label":"AI对话","inputs":{"question":"","history":"","knowledge":""},
                 "config":{"model":"DeepSeek","prompt":"你是一个专业的大健康顾问，请根据用户问题提供科学、合规的建议。\\n用户问题：{userChatInput}"}},"selected":False},
                {"id":"node-3","type":"msgOutput","position":{"x":580,"y":80},
                 "data":{"label":"消息输出","inputs":{"message":""},
                 "config":{"splitMode":"不切分"}},"selected":False}
            ],
            "edges": [
                {"id":"e-1","source":"node-1","target":"node-2",
                 "sourceHandle":"userChatInput","targetHandle":"question"},
                {"id":"e-2","source":"node-2","target":"node-3",
                 "sourceHandle":"aiReply","targetHandle":"message"}
            ]
        }
        # 梵芙尼美妆销售机器人 的默认工作流
        wf2 = {
            "botId": "fanfuni",
            "version": 1,
            "lastEdited": now,
            "nodes": [
                {"id":"node-1","type":"userInput","position":{"x":60,"y":80},
                 "data":{"label":"用户输入","inputs":{},"config":{}},"selected":False},
                {"id":"node-2","type":"kbSearch","position":{"x":320,"y":80},
                 "data":{"label":"知识库搜索","inputs":{"query":""},
                 "config":{"kb":"美妆产品知识库","searchMode":"混合搜索","topK":5}},"selected":False},
                {"id":"node-3","type":"aiChat","position":{"x":320,"y":220},
                 "data":{"label":"AI对话","inputs":{"question":"","history":"","knowledge":""},
                 "config":{"model":"DeepSeek","prompt":"你是梵芙尼高端美妆销售顾问，请根据用户问题和知识库内容，提供专业、个性化的护肤与彩妆建议。\\n用户问题：{userChatInput}\\n知识库引用：{knowledges}"}},"selected":False},
                {"id":"node-4","type":"msgOutput","position":{"x":580,"y":150},
                 "data":{"label":"消息输出","inputs":{"message":""},
                 "config":{"splitMode":"不切分"}},"selected":False}
            ],
            "edges": [
                {"id":"e-1","source":"node-1","target":"node-2",
                 "sourceHandle":"userChatInput","targetHandle":"query"},
                {"id":"e-2","source":"node-2","target":"node-3",
                 "sourceHandle":"knowledges","targetHandle":"knowledge"},
                {"id":"e-3","source":"node-3","target":"node-4",
                 "sourceHandle":"aiReply","targetHandle":"message"}
            ]
        }
        for wf in (wf1, wf2):
            backend.execute(
                "INSERT INTO orchestration_workflows(bot_id, data) VALUES (?, ?)",
                (wf["botId"], json.dumps(wf, ensure_ascii=False)),
            )

    # ---- 客户管理域种子 ----
    _seed_customer_domain(backend)

    # ---- 训练调整三 Tab 的种子数据（仅 yefengqiu / fanfuni 两个前端 bot_id）----
    # 这两个 bot_id 不在 bots 种子（bot-1/2/3）中，但无外键约束，按 bot_id 过滤即可。
    if _count(backend, "SELECT COUNT(*) AS c FROM knowledge_base") == 0:
        knowledge_seed = _seed_knowledge()
        for row in knowledge_seed:
            backend.execute(
                "INSERT INTO knowledge_base(id, bot_id, question, answer, tags, source, kind, creator, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM materials") == 0:
        materials_seed = _seed_materials()
        for row in materials_seed:
            backend.execute(
                "INSERT INTO materials(id, bot_id, name, type, size, category, url, source, usage_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    if _count(backend, "SELECT COUNT(*) AS c FROM training_records") == 0:
        for rec in _seed_training_records():
            record_id, bot_id, title, created_at, good, bad, total = rec
            backend.execute(
                "INSERT INTO training_records(id, bot_id, title, created_at, good_count, bad_count, total_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record_id, bot_id, title, created_at, good, bad, total),
            )
        for msg in _seed_training_messages():
            backend.execute(
                "INSERT INTO training_messages(id, record_id, bot_id, role, content, record_ref, feedback, msg_order, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                msg,
            )

    # ---- 托管消息日志种子（message_logs + message_log_traces）----
    if _count(backend, "SELECT COUNT(*) AS c FROM message_logs") == 0:
        _seed_message_logs(backend)
    if _count(backend, "SELECT COUNT(*) AS c FROM message_log_traces") == 0:
        _seed_message_log_traces(backend)

    # ---- 运营任务域种子（4 个任务 + 关联 targets） ----
    if _count(backend, "SELECT COUNT(*) AS c FROM operation_tasks") == 0:
        _seed_operation_tasks(backend)

    # ---- 运营SOP域种子 ----
    if _count(backend, "SELECT COUNT(*) AS c FROM operation_sops") == 0:
        _seed_operation_sops(backend)

    if _count(backend, "SELECT COUNT(*) AS c FROM operation_sop_records") == 0:
        _seed_operation_sop_records(backend)


def _seed_operation_sops(backend: DatabaseBackend) -> None:
    """运营SOP种子数据（2 条客户SOP + 1 条群聊SOP）。"""
    import json as _json

    sops = [
        {
            "id": "sop-1",
            "name": "新客首单关怀",
            "type": "customer",
            "channel": "企业微信",
            "enabled": 1,
            "status": "running",
            "trigger_type": "attribute_change",
            "trigger_config": _json.dumps({
                "type": "attribute_change",
                "conditions": [{"field": "add_time", "op": "within_days", "value": "7"}],
                "stopWhenNotMatch": True,
            }, ensure_ascii=False),
            "nodes_json": _json.dumps([
                {
                    "id": "node-sop1-1", "type": "settings", "x": 60, "y": 80,
                    "config": {
                        "channel": "企业微信",
                        "filterType": "dynamic",
                        "dynamicFilter": {
                            "hostingAccountId": "acc-zhulu",
                            "hostingBotId": "yefengqiu",
                            "tagRelation": "and",
                            "tagIds": ["tag-1", "tag-2"],
                        },
                        "stopWhenNotMatch": True,
                        "triggerType": "attribute_change",
                        "triggerConfig": {
                            "conditions": [{"field": "add_time", "op": "within_days", "value": "7"}],
                        },
                    },
                },
                {
                    "id": "node-sop1-2", "type": "message", "x": 340, "y": 80,
                    "config": {
                        "contentType": "text",
                        "content": "您好！感谢您首次下单，我们为您准备了专属新人礼包，请查收～",
                    },
                },
                {
                    "id": "node-sop1-3", "type": "delay", "x": 620, "y": 80,
                    "config": {"hours": 24},
                },
                {
                    "id": "node-sop1-4", "type": "message", "x": 900, "y": 80,
                    "config": {
                        "contentType": "text",
                        "content": "距离您上次下单已经24小时了，有任何使用上的问题可以随时咨询我哦～",
                    },
                },
            ], ensure_ascii=False),
        },
        {
            "id": "sop-2",
            "name": "复购唤醒流程",
            "type": "customer",
            "channel": "企业微信",
            "enabled": 1,
            "status": "stopped",
            "trigger_type": "periodic",
            "trigger_config": _json.dumps({
                "type": "periodic",
                "period": "weekly",
                "dayOfWeek": 1,
                "runTime": "10:00",
            }, ensure_ascii=False),
            "nodes_json": _json.dumps([
                {
                    "id": "node-sop2-1", "type": "settings", "x": 60, "y": 80,
                    "config": {
                        "channel": "企业微信",
                        "filterType": "dynamic",
                        "dynamicFilter": {
                            "hostingAccountId": "acc-zhulu",
                            "hostingBotId": "yefengqiu",
                            "tagRelation": "or",
                            "tagIds": ["tag-intent-1"],
                        },
                        "stopWhenNotMatch": False,
                        "triggerType": "periodic",
                        "triggerConfig": {
                            "period": "weekly",
                            "dayOfWeek": 1,
                            "runTime": "10:00",
                        },
                    },
                },
                {
                    "id": "node-sop2-2", "type": "message", "x": 340, "y": 80,
                    "config": {
                        "contentType": "text",
                        "content": "亲爱的客户，本周新品已上线，限时优惠进行中，快来选购吧！",
                    },
                },
            ], ensure_ascii=False),
        },
        {
            "id": "sop-3",
            "name": "社群打卡激励",
            "type": "group",
            "channel": "企业微信",
            "enabled": 0,
            "status": "stopped",
            "trigger_type": "periodic",
            "trigger_config": _json.dumps({
                "type": "periodic",
                "period": "daily",
                "runTime": "09:00",
            }, ensure_ascii=False),
            "nodes_json": _json.dumps([
                {
                    "id": "node-sop3-1", "type": "group-settings", "x": 60, "y": 80,
                    "config": {
                        "channel": "企业微信",
                        "filterType": "dynamic",
                        "dynamicFilter": {
                            "hostingAccountId": "acc-zhulu",
                            "hostingBotId": "yefengqiu",
                        },
                        "stopWhenNotMatch": False,
                        "triggerType": "periodic",
                        "triggerConfig": {
                            "period": "daily",
                            "runTime": "09:00",
                        },
                    },
                },
                {
                    "id": "node-sop3-2", "type": "message", "x": 340, "y": 80,
                    "config": {
                        "contentType": "text",
                        "content": "早安打卡！坚持打卡第N天，今日健康小贴士：每天一杯温水，开启元气满满的一天！",
                    },
                },
            ], ensure_ascii=False),
        },
    ]

    for sop in sops:
        backend.execute(
            "INSERT INTO operation_sops(id, name, type, channel, enabled, status, trigger_type, trigger_config, nodes_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sop["id"], sop["name"], sop["type"], sop["channel"],
             sop["enabled"], sop["status"], sop["trigger_type"],
             sop["trigger_config"], sop["nodes_json"]),
        )


def _seed_operation_sop_records(backend: DatabaseBackend) -> None:
    """SOP 运行记录种子（5 条，关联 3 个种子 SOP）。"""
    records = [
        ("rec-1", "sop-1", "2026-07-10 09:00:00", "success", ""),
        ("rec-2", "sop-1", "2026-07-09 09:00:00", "failed", "触发条件不匹配：客户标签不满足筛选条件"),
        ("rec-3", "sop-1", "2026-07-08 09:00:00", "success", ""),
        ("rec-4", "sop-2", "2026-07-07 10:00:00", "success", ""),
        ("rec-5", "sop-3", "2026-07-06 09:00:00", "failed", "渠道账号离线，消息发送失败"),
    ]
    for rec in records:
        backend.execute(
            "INSERT INTO operation_sop_records(id, sop_id, run_time, run_status, error_message) "
            "VALUES (?, ?, ?, ?, ?)",
            rec,
        )


def _seed_customer_domain(backend: DatabaseBackend) -> None:
    """客户管理域种子数据（9 个守卫块，均仅在空表时写入）。"""
    # 1. 标签分组（4 组，严格按原型 tagGroups 2202-2206）
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_tag_groups WHERE id != 'tg-default'") == 0:
        groups = [
            ("tg-stage", "沟通阶段", 1),
            ("tg-intent", "意向程度", 1),
            ("tg-satisfaction", "满意度", 1),
            ("tg-sales", "销售阶段", 0),
        ]
        for gid, name, is_hot in groups:
            backend.execute(
                "INSERT INTO customer_tag_groups(id, name, is_hot) VALUES (?, ?, ?)",
                (gid, name, is_hot),
            )

    # 2. 标签（12 个，关联对应分组）
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_tags WHERE group_id != '' AND group_id != 'tg-default'") == 0:
        tags = [
            # 沟通阶段
            ("tag-stage-1", "tg-stage", "未沟通", "blue", ""),
            ("tag-stage-2", "tg-stage", "单方沟通", "blue", ""),
            ("tag-stage-3", "tg-stage", "沟通中", "blue", ""),
            ("tag-stage-4", "tg-stage", "沟通中自定义", "blue", ""),
            # 意向程度
            ("tag-intent-1", "tg-intent", "高", "green", ""),
            ("tag-intent-2", "tg-intent", "中", "orange", ""),
            ("tag-intent-3", "tg-intent", "低", "red", ""),
            # 满意度
            ("tag-sat-1", "tg-satisfaction", "非常满意", "green", ""),
            ("tag-sat-2", "tg-satisfaction", "满意", "blue", ""),
            ("tag-sat-3", "tg-satisfaction", "一般", "gray", ""),
            ("tag-sat-4", "tg-satisfaction", "不满意", "orange", ""),
            ("tag-sat-5", "tg-satisfaction", "非常不满意", "red", ""),
            # 销售阶段
            ("tag-sales-1", "tg-sales", "售前调研", "blue", ""),
            ("tag-sales-2", "tg-sales", "报价中", "orange", ""),
            ("tag-sales-3", "tg-sales", "签约", "green", ""),
        ]
        for tid, gid, name, color, rule in tags:
            backend.execute(
                "INSERT INTO customer_tags(id, group_id, name, color, rule) VALUES (?, ?, ?, ?, ?)",
                (tid, gid, name, color, rule),
            )

    # 3. 扩展 channel_contacts（从 12 → ~35：新增 ~23 外部客户 + 19 内部成员）
    _seed_ext_contacts(backend)

    # 4. 扩展 customer_profiles + 5. communication_records + 6. custom_attributes
    _seed_ext_profiles(backend)

    # 7. 标签关系（~30 条）
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_tag_relations") == 0:
        _seed_tag_relations(backend)

    # 8. 客户分组（4 组）
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_groups") == 0:
        groups_data = [
            ("g-high-intent", "高意向客户", "system", 128, "2026-06-01 10:22:00", "2026-07-08 14:03:00", "江南竹绿"),
            ("g-618", "618大促触达", "custom", 56, "2026-06-20 09:11:00", "2026-07-10 18:40:00", "林瞰"),
            ("g-sleep", "沉睡唤醒", "custom", 312, "2026-05-12 16:45:00", "2026-07-09 11:20:00", "通天草"),
            ("g-repurchase", "复购潜力", "system", 89, "2026-06-05 13:30:00", "2026-07-11 09:05:00", "江南竹绿"),
        ]
        for gid, name, gtype, cnt, cat, uat, editor in groups_data:
            backend.execute(
                "INSERT INTO customer_groups(id, name, type, count, created_at, updated_at, editor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (gid, name, gtype, cnt, cat, uat, editor),
            )

    # 9. 客户分组成员（~30 条）
    if _count(backend, "SELECT COUNT(*) AS c FROM customer_group_members") == 0:
        # 获取所有 customer_profiles id
        profiles = backend.query("SELECT id FROM customer_profiles ORDER BY id")
        all_cp_ids = [r["id"] for r in profiles]
        # 4 个分组各关联若干客户
        # 高意向客户(system): 前 6 个
        for cid in all_cp_ids[:6]:
            backend.execute("INSERT INTO customer_group_members(group_id, customer_id) VALUES (?, ?)", ("g-high-intent", cid))
        # 618大促(custom): 2-8
        for cid in all_cp_ids[2:8]:
            backend.execute("INSERT INTO customer_group_members(group_id, customer_id) VALUES (?, ?)", ("g-618", cid))
        # 沉睡唤醒(custom): 5-13
        for cid in all_cp_ids[5:13]:
            backend.execute("INSERT INTO customer_group_members(group_id, customer_id) VALUES (?, ?)", ("g-sleep", cid))
        # 复购潜力(system): 8-14
        for cid in all_cp_ids[8:14]:
            backend.execute("INSERT INTO customer_group_members(group_id, customer_id) VALUES (?, ?)", ("g-repurchase", cid))


def _seed_ext_contacts(backend: DatabaseBackend) -> None:
    """扩展 channel_contacts（保留现有 12 条 + 新增 ~23 外部客户 + 19 内部成员）。"""
    existing = _count(backend, "SELECT COUNT(*) AS c FROM channel_contacts")
    if existing >= 12 and _count(backend, "SELECT COUNT(*) AS c FROM channel_contacts WHERE type = 'internal'") >= 3:
        # 内部成员已扩展，跳过
        pass
    else:
        # 新增外部客户（原型 8535-8544 的 10 个 + 额外 13 个）
        ext_customers = [
            ("c-tongtian", "acc-zhulu", "@微信", "wechat", "通天草-林瞰", "通天草-林瞰", "customer", "online", "重点健康客户", "通天草 · 林瞰@微信", "2026-07-03 15:35:45", "扫码"),
            ("c-zhizu", "acc-zhulu", "@微信", "wechat", "知足常乐【中奖】", "知足常乐", "customer", "online", "", "知足常乐@微信", "2026-06-30 18:29:34", "扫码"),
            ("c-gaoxing", "acc-zhulu", "@微信", "wechat", "高-星", "高-星", "customer", "online", "", "高-星@微信", "2026-06-30 18:29:33", "扫码"),
            ("c-kejie", "acc-zhulu", "@微信", "wechat", "客姐", "客姐", "customer", "online", "", "客姐@微信", "2026-06-30 18:29:33", "扫码"),
            ("c-qingxian", "acc-zhulu", "@微信", "wechat", "清闲自在", "清闲自在", "customer", "offline", "", "清闲自在@微信", "2026-06-30 18:29:30", "扫码"),
            ("c-xiao", "acc-zhulu", "@微信", "wechat", "小", "小", "customer", "offline", "", "小@微信", "2026-06-30 18:29:30", "扫码"),
            ("c-maoxiaorui", "acc-zhulu", "@微信", "wechat", "毛小瑞", "毛小瑞", "customer", "online", "", "毛小瑞@微信", "2026-06-30 18:29:29", "扫码"),
            ("c-mali", "acc-zhulu", "@微信", "wechat", "玛丽", "玛丽", "customer", "offline", "", "玛丽@微信", "2026-06-30 18:29:29", "扫码"),
            ("c-yaoyao", "acc-zhulu", "@微信", "wechat", "瑶瑶【中奖】", "瑶瑶", "customer", "online", "中奖用户", "瑶瑶@微信", "2026-06-30 18:29:26", "扫码"),
            ("c-kafei", "acc-zhulu", "@微信", "wechat", "咖啡~我行！我秀！", "咖啡", "customer", "offline", "", "咖啡@微信", "2026-06-30 18:29:26", "扫码"),
            ("c-yangyang", "acc-hengkang", "@企业微信", "wecom", "洋洋", "洋洋", "customer", "online", "", "", "2026-06-30 18:29:12", "扫码"),
            ("c-min", "acc-hengkang", "@企业微信", "wecom", "Min", "Min", "customer", "online", "", "", "2026-06-30 18:27:09", "扫码"),
            ("c-xingyue", "acc-hengkang", "@企业微信", "wecom", "xıngyue", "xıngyue", "customer", "online", "", "", "2026-06-30 18:27:10", "扫码"),
            ("c-wen", "acc-hengkang", "@企业微信", "wecom", "文", "文", "customer", "offline", "", "", "2026-06-30 18:27:10", "扫码"),
            ("c-lili", "acc-hengkang", "@企业微信", "wecom", "丽丽", "丽丽", "customer", "offline", "", "", "2026-06-30 18:27:13", "扫码"),
            ("c-chenwei", "acc-hengkang", "@企业微信", "wecom", "陈薇", "陈薇", "customer", "online", "", "", "2026-07-01 10:15:20", "扫码"),
            ("c-lina", "acc-fushou", "@微信", "wechat", "李娜", "李娜", "customer", "online", "", "", "2026-07-02 14:22:30", "扫码"),
            ("c-wangfang", "acc-fushou", "@微信", "wechat", "王芳", "王芳", "customer", "offline", "", "", "2026-07-03 09:10:00", "扫码"),
            ("c-zhaoyun", "acc-fushou", "@微信", "wechat", "赵云龙", "赵云龙", "customer", "online", "", "", "2026-07-04 16:45:12", "扫码"),
            ("c-sunli", "acc-fushou", "@微信", "wechat", "孙丽", "孙丽", "customer", "offline", "", "", "2026-07-05 11:30:00", "扫码"),
            ("c-zhoujie", "acc-hengkang", "@企业微信", "wecom", "周杰", "周杰", "customer", "online", "", "", "2026-07-06 08:20:00", "扫码"),
            ("c-wuqiang", "acc-hengkang", "@企业微信", "wecom", "吴强", "吴强", "customer", "offline", "", "", "2026-07-07 13:15:00", "扫码"),
            ("c-liumei", "acc-fushou", "@微信", "wechat", "刘美玲", "刘美玲", "customer", "online", "", "", "2026-07-08 10:05:00", "扫码"),
        ]
        for row in ext_customers:
            cid = row[0]
            if _count(backend, "SELECT COUNT(*) AS c FROM channel_contacts WHERE id = ?", (cid,)) == 0:
                backend.execute(
                    "INSERT INTO channel_contacts(id, account_id, channel, channel_type, name, nickname, type, status, remark, description, add_time, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )

        # 新增内部成员（19 个，对齐原型 8575-8593）
        internal_members = [
            ("c-sanqi", "acc-zhulu", "@企业微信", "wecom", "三七-彭佳英", "三七", "internal", "online", "", "", "2026-06-30 18:27:38", "手动添加"),
            ("c-tongtian-internal", "acc-zhulu", "@企业微信", "wecom", "通天草-林瞰", "通天草", "internal", "online", "", "", "2026-06-30 18:27:39", "手动添加"),
            ("c-qixingcao", "acc-zhulu", "@企业微信", "wecom", "七星草-陈晓", "七星草", "internal", "online", "", "", "2026-06-30 18:27:40", "手动添加"),
            ("c-guanyi", "acc-zhulu", "@企业微信", "wecom", "管医-许小玲", "管医", "internal", "online", "", "", "2026-06-30 18:27:41", "手动添加"),
            ("c-jibin", "acc-zhulu", "@企业微信", "wecom", "纪斌", "纪斌", "internal", "online", "", "", "2026-06-30 18:27:42", "手动添加"),
            ("c-fuxiuxuan", "acc-zhulu", "@企业微信", "wecom", "福秀萱", "福秀萱", "internal", "online", "", "", "2026-06-30 18:27:43", "手动添加"),
            ("c-kefu-meigui", "acc-zhulu", "@企业微信", "wecom", "客服-玫瑰", "玫瑰", "internal", "offline", "", "", "2026-06-30 18:27:44", "手动添加"),
            ("c-chenyurong", "acc-zhulu", "@企业微信", "wecom", "陈语荣", "陈语荣", "internal", "online", "", "", "2026-06-30 18:27:45", "手动添加"),
            ("c-wuhailong", "acc-zhulu", "@企业微信", "wecom", "吴海龙(灯心草)", "吴海龙", "internal", "online", "", "", "2026-06-30 18:27:46", "手动添加"),
            ("c-yiyirui", "acc-zhulu", "@企业微信", "wecom", "依医瑞健康客服", "依医瑞", "internal", "online", "", "", "2026-06-30 18:27:47", "手动添加"),
            ("c-guolao", "acc-zhulu", "@企业微信", "wecom", "国老-于成龙", "国老", "internal", "online", "", "", "2026-06-30 18:27:48", "手动添加"),
            ("c-huangbodong", "acc-zhulu", "@企业微信", "wecom", "黄博栋", "黄博栋", "internal", "online", "", "", "2026-06-30 18:27:49", "手动添加"),
            ("c-sudonglong", "acc-zhulu", "@企业微信", "wecom", "苏东龙", "苏东龙", "internal", "online", "", "", "2026-06-30 18:27:50", "手动添加"),
            ("c-juemingzi", "acc-zhulu", "@企业微信", "wecom", "决明子-刘荣享", "决明子", "internal", "offline", "", "", "2026-06-30 18:27:51", "手动添加"),
            ("c-baizhi", "acc-zhulu", "@企业微信", "wecom", "白芷-谢玉婷", "白芷", "internal", "online", "", "", "2026-06-30 18:27:52", "手动添加"),
            ("c-jiaoshou", "acc-zhulu", "@企业微信", "wecom", "教授助理-张贤", "张贤", "internal", "online", "", "", "2026-06-30 18:27:53", "手动添加"),
            ("c-situmin", "acc-zhulu", "@企业微信", "wecom", "司徒敏瑜", "司徒敏瑜", "internal", "online", "", "", "2026-06-30 18:27:54", "手动添加"),
            ("c-zhulv", "acc-zhulu", "@企业微信", "wecom", "竹绿-健康", "竹绿", "internal", "online", "", "", "2026-06-30 18:27:55", "手动添加"),
            ("c-yuanzhi", "acc-zhulu", "@企业微信", "wecom", "远志-洪恒鑫", "远志", "internal", "online", "", "", "2026-06-30 18:27:56", "手动添加"),
        ]
        for row in internal_members:
            cid = row[0]
            if _count(backend, "SELECT COUNT(*) AS c FROM channel_contacts WHERE id = ?", (cid,)) == 0:
                backend.execute(
                    "INSERT INTO channel_contacts(id, account_id, channel, channel_type, name, nickname, type, status, remark, description, add_time, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )


def _seed_ext_profiles(backend: DatabaseBackend) -> None:
    """扩展 customer_profiles + communication_records + custom_attributes。"""
    # 获取所有 type='customer' 的 contacts
    contacts = backend.query("SELECT id, name, add_time FROM channel_contacts WHERE type = 'customer' ORDER BY add_time")
    # 获取已有 profiles
    existing_profiles = _count(backend, "SELECT COUNT(*) AS c FROM customer_profiles")

    profile_batch: list[tuple] = []
    comm_batch: list[tuple] = []
    attr_batch: list[tuple] = []

    import random as _r
    _r.seed(42)

    profile_prefixes = [
        ("138", "example.com", "", "", "华东", "健康生活每一天"),
        ("139", "corp.com", "医林通健康科技", "健康顾问", "华南", ""),
        ("150", "health.cn", "", "", "华北", "养生从我做起"),
        ("186", "qq.com", "康源集团", "产品经理", "西南", ""),
        ("137", "163.com", "", "", "华东", ""),
        ("152", "gmail.com", "瑞康科技", "运营主管", "华中", "热爱中医"),
        ("189", "sina.com", "", "", "华北", ""),
        ("133", "yeah.net", "恒康倍力", "销售总监", "华南", ""),
        ("158", "outlook.com", "", "", "西北", ""),
        ("176", "foxmail.com", "福寿康", "客服经理", "华东", "服务至上"),
    ]

    for i, c in enumerate(contacts):
        cid = c["id"]
        name = c["name"]
        add_time = c["add_time"] or "2026-07-01 00:00:00"
        cp_id = f"cp-{cid.replace('c-', '')}"

        if _count(backend, "SELECT COUNT(*) AS c FROM customer_profiles WHERE contact_id = ?", (cid,)) > 0:
            continue

        pf = profile_prefixes[i % len(profile_prefixes)]
        phone = f"{pf[0]}{_r.randint(1000, 9999):04d}{_r.randint(1000, 9999):04d}"[:11]
        profile_batch.append((
            cp_id, cid,
            phone if i % 3 != 0 else "",
            f"{name[:2].lower()}{i}@{pf[1]}" if i % 2 == 0 else "",
            pf[2], pf[3], pf[4],
            _r.randint(20, 55) if i % 3 != 0 else None,
            f"{_r.randint(1980, 2005)}-{_r.randint(1,12):02d}-{_r.randint(1,28):02d}" if i % 4 != 0 else "",
            "" if i % 5 == 0 else ("重点跟进客户" if i % 7 == 0 else ""),
            add_time, pf[0][:2] == "15" and "@企业微信" or "@微信",
            pf[5],
            int(i % 3 == 0),  # ai_summary_enabled: 约 1/3 开启
        ))

        # 沟通记录：每客户 1-3 条
        comm_count = _r.randint(1, 3)
        for j in range(comm_count):
            cr_id = f"cr-{cid}-{j+1}"
            if _count(backend, "SELECT COUNT(*) AS c FROM communication_records WHERE id = ?", (cr_id,)) > 0:
                continue
            day_offset = (3 - j) * _r.randint(1, 10)
            from datetime import datetime as _dt, timedelta as _td
            ts = (_dt(2026, 7, 14) - _td(days=day_offset)).strftime("%Y-%m-%d %H:%M:%S")
            comm_batch.append((
                cr_id, cp_id,
                f"与客户{name}进行了{'产品咨询' if j % 2 == 0 else '售后服务'}沟通，客户{'满意' if _r.random() > 0.3 else '需跟进'}。" if j == 0 else f"第{j+1}次沟通记录：{'发送产品资料' if j % 2 == 0 else '确认订单信息'}",
                f"AI总结：客户{name}{'对产品表示满意' if _r.random() > 0.4 else '需要进一步跟进'}，建议{'定期回访' if _r.random() > 0.5 else '推送优惠信息'}" if j == 0 and _r.random() > 0.3 else "",
                "note",
                ts,
            ))

        # 自定义属性：每客户 0-2 条
        attr_count = _r.randint(0, 2)
        for j in range(attr_count):
            ca_id = f"ca-{cid}-{j+1}"
            if _count(backend, "SELECT COUNT(*) AS c FROM custom_attributes WHERE id = ?", (ca_id,)) > 0:
                continue
            attr_pairs = [("客户等级", "VIP"), ("来源渠道", "扫码"), ("偏好产品", "大健康"), ("意向程度", "高"), ("跟进状态", "待回访")]
            aname, aval = attr_pairs[(i + j) % len(attr_pairs)]
            attr_batch.append((ca_id, cp_id, aname, aval))

    for row in profile_batch:
        backend.execute(
            "INSERT INTO customer_profiles(id, contact_id, phone, email, company, position, region, age, birthday, remark, add_time, add_channel, signature, ai_summary_enabled) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )

    for row in comm_batch:
        backend.execute(
            "INSERT INTO communication_records(id, customer_id, content, ai_summary, type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            row,
        )

    for row in attr_batch:
        backend.execute(
            "INSERT INTO custom_attributes(id, customer_id, name, value, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            row,
        )


def _seed_tag_relations(backend: DatabaseBackend) -> None:
    """为客户关联标签（~30 条）。"""
    profiles = backend.query("SELECT id FROM customer_profiles ORDER BY id")
    tags = backend.query("SELECT id, group_id FROM customer_tags WHERE group_id != '' AND group_id != 'tg-default'")
    if not profiles or not tags:
        return

    import random as _r
    _r.seed(42)
    tag_ids = [t["id"] for t in tags]

    for i, p in enumerate(profiles[:15]):
        count = _r.randint(1, 3)
        chosen = _r.sample(tag_ids, min(count, len(tag_ids)))
        for tid in chosen:
            backend.execute(
                "INSERT OR IGNORE INTO customer_tag_relations(customer_id, tag_id) VALUES (?, ?)",
                (p["id"], tid),
            )


def _seed_knowledge() -> list[tuple]:
    """知识库种子（yefengqiu / fanfuni 各 常见问题4 + 纠偏知识3）。

    返回元组：(id, bot_id, question, answer, tags_json, source, kind, creator, created_at, updated_at)
    """
    raw = [
        # ---- 野风秋大健康（yefengqiu）----
        ("yefengqiu", "common", "野风秋运营", "官网FAQ", "2026-07-09 22:14:00",
         "耳鸣患者日常饮食注意什么？", "建议低盐低脂、减少咖啡因与酒精摄入，多补充富含镁与锌的食物（如坚果、深绿色蔬菜），并避免噪音持续暴露。", ["耳鸣", "饮食"]),
        ("yefengqiu", "common", "李医生", "客服知识库", "2026-07-09 22:15:00",
         "高血压人群可以服用银杏叶提取物吗？", "银杏叶提取物可能辅助改善微循环，但可能与降压药相互作用，服用前请咨询医生并按医嘱使用。", ["高血压", "用药"]),
        ("yefengqiu", "common", "王营养", "运营配置", "2026-07-09 22:16:00",
         "长期失眠有哪些非药物调理方式？", "固定作息、睡前避免屏幕蓝光、温水泡脚、冥想放松，必要时进行认知行为治疗（CBT-I）。", ["失眠", "调理"]),
        ("yefengqiu", "common", "王营养", "官网FAQ", "2026-07-09 22:17:00",
         "糖尿病患者如何科学运动？", "推荐每周150分钟中等强度有氧（快走、游泳），运动前后监测血糖，避免空腹运动以防低血糖。", ["糖尿病", "运动"]),
        ("yefengqiu", "correction", "李医生", "纠偏记录", "2026-07-09 22:18:00",
         "喝某偏方茶可根治糖尿病？", "误区：目前糖尿病无法根治，偏方茶不能替代规范治疗，规范用药与生活方式管理才是关键。", ["糖尿病", "纠偏"]),
        ("yefengqiu", "correction", "李医生", "纠偏记录", "2026-07-09 22:19:00",
         "耳鸣一定是肾虚引起的？", "误区：耳鸣成因复杂（噪音、耳疾、血管、药物等），未必与肾虚相关，需专业检查甄别。", ["耳鸣", "纠偏"]),
        ("yefengqiu", "correction", "李医生", "纠偏记录", "2026-07-09 22:20:00",
         "保健品可以替代降压药？", "误区：保健品不能替代降压药物，擅自停药可能导致血压反弹，存在卒中风险。", ["高血压", "纠偏"]),
        # ---- 梵芙尼美妆（fanfuni）----
        ("fanfuni", "common", "梵芙尼运营", "官网FAQ", "2026-07-10 21:02:00",
         "这款精华适合敏感肌吗？", "舒缓修护精华含积雪草与神经酰胺，成分温和，专为敏感肌设计，首次使用建议耳后测试。", ["敏感肌", "精华"]),
        ("fanfuni", "common", "梵芙尼运营", "客服知识库", "2026-07-10 21:03:00",
         "购买后多久发货？", "现货商品在付款后48小时内发出，预售商品以商品页标注为准。", ["物流", "售后"]),
        ("fanfuni", "common", "小美", "官网FAQ", "2026-07-10 21:04:00",
         "如何办理退换货？", "支持7天无理由退换，商品需吊牌齐全、不影响二次销售，可在订单页发起申请。", ["售后", "退换货"]),
        ("fanfuni", "common", "小美", "运营配置", "2026-07-10 21:05:00",
         "会员有哪些权益？", "会员享专属折扣、生日礼遇与积分加倍，可在「我的-会员中心」查看。", ["会员", "权益"]),
        ("fanfuni", "correction", "小美", "纠偏记录", "2026-07-10 21:06:00",
         "护肤越贵越好？", "误区：护肤效果取决于成分与肤质匹配，而非价格，平价有效成分同样可达好效果。", ["护肤", "纠偏"]),
        ("fanfuni", "correction", "小美", "纠偏记录", "2026-07-10 21:07:00",
         "天天敷面膜皮肤更好？", "误区：频繁敷面膜易破坏屏障、引发敏感，建议每周2-3次即可。", ["面膜", "纠偏"]),
        ("fanfuni", "correction", "梵芙尼运营", "纠偏记录", "2026-07-10 21:08:00",
         "防晒只在夏天需要？", "误区：紫外线四季存在，室内靠窗与冬季也需防晒，日常以SPF30+ PA+++为宜。", ["防晒", "纠偏"]),
    ]
    rows: list[tuple] = []
    for index, (bot_id, kind, creator, source, ts, question, answer, tags) in enumerate(raw, start=1):
        rows.append((
            f"know-{bot_id[:2]}-{index:02d}",
            bot_id,
            question,
            answer,
            json.dumps(tags, ensure_ascii=False),
            source,
            kind,
            creator,
            ts,
            ts,
        ))
    return rows


def _seed_materials() -> list[tuple]:
    """素材库种子（yefengqiu / fanfuni 各 6 条，含 source/type/category/size/usage_count）。

    返回元组：(id, bot_id, name, type, size, category, url, source, usage_count, created_at, updated_at)
    """
    raw = [
        # ---- 野风秋大健康（yefengqiu）----
        ("yefengqiu", "大健康产品手册.pdf", "document", "产品文档", "知识中心", 1342177, 23, "2026-07-08 10:12:00"),
        ("yefengqiu", "耳鸣科普长图.png", "image", "科普图片", "知识中心", 2516582, 41, "2026-07-08 14:30:00"),
        ("yefengqiu", "节气养生短视频.mp4", "video", "品牌视频", "上传", 19503514, 12, "2026-07-09 09:05:00"),
        ("yefengqiu", "糖尿病饮食指南.docx", "document", "产品文档", "知识中心", 552960, 8, "2026-07-09 16:20:00"),
        ("yefengqiu", "会员日活动海报.png", "image", "活动素材", "上传", 3250585, 5, "2026-07-10 11:40:00"),
        ("yefengqiu", "助眠白噪音.mp3", "audio", "音频素材", "上传", 9227469, 3, "2026-07-10 20:15:00"),
        # ---- 梵芙尼美妆（fanfuni）----
        ("fanfuni", "春季新品宣传图.png", "image", "产品图片", "知识中心", 2726298, 34, "2026-07-08 10:00:00"),
        ("fanfuni", "品牌宣传视频.mp4", "video", "品牌视频", "上传", 22544384, 19, "2026-07-08 15:20:00"),
        ("fanfuni", "成分说明文档.pdf", "document", "产品文档", "知识中心", 737280, 27, "2026-07-09 09:30:00"),
        ("fanfuni", "妆容教程短片.mp4", "video", "教程视频", "上传", 13841203, 14, "2026-07-09 17:45:00"),
        ("fanfuni", "会员专享礼遇图.png", "image", "活动素材", "上传", 1992294, 6, "2026-07-10 11:10:00"),
        ("fanfuni", "防晒科普长图.png", "image", "科普图片", "知识中心", 2202009, 22, "2026-07-10 20:30:00"),
    ]
    rows: list[tuple] = []
    for index, (bot_id, name, type_, category, source, size, usage, ts) in enumerate(raw, start=1):
        rows.append((
            f"mat-{bot_id[:2]}-{index:02d}",
            bot_id,
            name,
            type_,
            size,
            category,
            None,
            source,
            usage,
            ts,
            ts,
        ))
    return rows


def _seed_training_records() -> list[tuple]:
    """训练记录种子（yefengqiu 3 条 / fanfuni 2 条；统计与消息 feedback 一致）。

    返回元组：(id, bot_id, title, created_at, good_count, bad_count, total_count)
    """
    return [
        ("rec-yf-1", "yefengqiu", "训练历史1", "2026-07-09 22:27:48", 2, 1, 3),
        ("rec-yf-2", "yefengqiu", "训练历史2", "2026-07-10 20:55:49", 0, 0, 0),
        ("rec-yf-3", "yefengqiu", "训练历史3", "2026-07-10 21:09:50", 1, 0, 2),
        ("rec-ff-1", "fanfuni", "训练历史1", "2026-07-09 22:14:00", 1, 1, 2),
        ("rec-ff-2", "fanfuni", "训练历史2", "2026-07-10 20:30:00", 0, 1, 1),
    ]


def _seed_training_messages() -> list[tuple]:
    """训练消息种子（每记录 1-3 条；AI 消息带 record_ref 与初始 feedback）。

    返回元组：(id, record_id, bot_id, role, content, record_ref, feedback, msg_order, created_at)
    """
    raw = [
        ("rec-yf-1", "yefengqiu", 1, "user", "糖尿病患者能吃西瓜吗？", "", None),
        ("rec-yf-1", "yefengqiu", 2, "ai", "可以适量食用。西瓜升糖指数中等，建议两餐之间吃一小片（约200g），并相应减少主食；血糖不稳时先测餐后血糖。", "msg-20260709-101", "like"),
        ("rec-yf-1", "yefengqiu", 3, "user", "那荔枝呢？", "", None),
        ("rec-yf-1", "yefengqiu", 4, "ai", "荔枝含糖量高（约16%），降血糖药期间更要节制，建议每天不超过5颗，避免空腹食用引发低血糖。", "msg-20260709-102", "like"),
        ("rec-yf-1", "yefengqiu", 5, "user", "有没有食疗方子？", "", None),
        ("rec-yf-1", "yefengqiu", 6, "ai", "可用苦瓜、山药、燕麦、木耳等辅助控糖；推荐山药排骨汤、凉拌木耳，少油少盐、规律进餐。", "msg-20260709-103", "dislike"),
        ("rec-yf-3", "yefengqiu", 1, "user", "耳鸣一直嗡嗡响，睡不好怎么办？", "", None),
        ("rec-yf-3", "yefengqiu", 2, "ai", "建议睡前白噪音掩蔽、避免咖啡因与熬夜，并做耳鸣习服训练；持续超过一周请到耳鼻喉科排查。", "msg-20260710-201", "like"),
        ("rec-yf-3", "yefengqiu", 3, "user", "有什么放松的方法？", "", None),
        ("rec-yf-3", "yefengqiu", 4, "ai", "可尝试4-7-8呼吸法（吸气4秒、屏息7秒、呼气8秒），配合温水泡脚，帮助入睡。", "msg-20260710-202", None),
        ("rec-ff-1", "fanfuni", 1, "user", "混油皮夏天容易脱妆，怎么定妆？", "", None),
        ("rec-ff-1", "fanfuni", 2, "ai", "建议妆前控油、用哑光粉底，定妆散粉叠加定妆喷雾；T区局部补散粉，随身吸油纸按压。", "msg-20260709-301", "like"),
        ("rec-ff-1", "fanfuni", 3, "user", "敏感期能刷酸吗？", "", None),
        ("rec-ff-1", "fanfuni", 4, "ai", "敏感期不建议刷酸，先修复屏障（神经酰胺、积雪草），待稳定后再从低浓度开始。", "msg-20260709-302", "dislike"),
        ("rec-ff-2", "fanfuni", 1, "user", "孕妇能用美白精华吗？", "", None),
        ("rec-ff-2", "fanfuni", 2, "ai", "孕期不建议使用含视黄醇、高浓度烟酰胺、氢醌等美白成分，优先基础保湿与防晒。", "msg-20260710-401", "dislike"),
    ]
    rows: list[tuple] = []
    for record_id, bot_id, order, role, content, ref, feedback in raw:
        # 同一记录内按 msg_order 递增时间，保证展示顺序稳定
        base = {"rec-yf-1": "2026-07-09 22:27:48", "rec-yf-3": "2026-07-10 21:09:50",
                "rec-ff-1": "2026-07-09 22:14:00", "rec-ff-2": "2026-07-10 20:30:00"}[record_id]
        rows.append((
            f"msg-{record_id}-{order:02d}",
            record_id,
            bot_id,
            role,
            content,
            ref,
            feedback,
            order,
            base,
        ))
    return rows


# ---- 托管消息日志种子（message_logs + message_log_traces）----

# 节点源码片段模板（合成样例，非真实 LLM/网关调用）
_CODE_USER_INPUT = '''# 用户输入预处理
import json

def parse_user_input(raw):
    chat_id = raw.get("chatId")
    text = raw.get("userChatInput", "")
    return {
        "chatId": chat_id,
        "messageType": "TEXT",
        "userChatInput": text
    }

result = parse_user_input(event.payload)'''

_CODE_CHAT_HISTORY = '''# 获取历史对话记录
import requests

def fetch_chat_history(chat_id, url):
    resp = requests.get(url, params={"chatId": chat_id, "limit": 100})
    return resp.json()

history = fetch_chat_history(event.input["chatId"], event.input["chatHistoryUrl"])'''

_CODE_AI_CHAT = '''# AI 对话生成
from openai import OpenAI

client = OpenAI()
resp = client.chat.completions.create(
    model=event.input["model"],
    messages=build_messages(event.input),
    temperature=0.7
)
result = {
    "text": resp.choices[0].message.content,
    "type": "text",
    "finish_reason": resp.choices[0].finish_reason
}'''

_CODE_KB_SEARCH = '''# 知识库混合检索
from vector_store import HybridSearch

searcher = HybridSearch(index="美妆产品知识库")
results = searcher.search(
    query=event.input["query"],
    top_k=event.input["topK"],
    mode=event.input["searchMode"],
)
knowledges = [{"title": r.title, "content": r.content, "score": r.score} for r in results]
result = {"knowledges": knowledges, "total": len(knowledges)}'''

_CODE_MSG_OUTPUT = '''# 渠道发送消息
import os
from channel_sdk import WeComClient

client = WeComClient(corp_id=os.getenv("WECOM_CORP_ID"))
resp = client.message.send(
    to_user=event.input["chatId"],
    msg_type="text",
    content=event.input["message"],
)
result = {
    "delivered": resp.ok,
    "messageId": resp.msg_id,
    "sentAt": now()
}'''


def _seed_message_logs(backend: DatabaseBackend) -> None:
    """托管消息日志主表种子（yefengqiu 3 + fanfuni 3）。"""
    rows = [
        ("AI2075172858125025280", "yefengqiu", '{"text":"行，咱以后可以用","type":"text"}', "-", "竹绿-健康", "Dr.Jack 恒康倍力 曹医生", "企业微信", "2026-07-09 18:58:59", "成功"),
        ("AI2075167178402115584", "yefengqiu", '{"text":"林总，有事吗","type":"text"}', "-", "竹绿-健康", "Dr.Jack 恒康倍力 曹医生", "企业微信", "2026-07-09 18:36:25", "成功"),
        ("AI2074999876543210002", "yefengqiu", '{"text":"林总，今天的通天草库存已补货完成，可继续上架。","type":"text"}', "库存补好了吗？", "通天草-林瞰", "通天草-林瞰", "企业微信", "2026-07-07 20:45:11", "处理中"),
        ("AI2075001234567890001", "fanfuni", '{"text":"您好，这款精华适合敏感肌使用，可放心购买～","type":"text"}', "这个精华敏感肌能用吗？", "梵芙尼旗舰店", "MenHM VIP 用户群", "企业微信", "2026-07-08 10:12:03", "失败"),
        ("AI2075888000000000003", "fanfuni", '{"text":"会员专享8折，今晚24点前下单有效哦～","type":"text"}', "会员有什么优惠？", "梵芙尼旗舰店", "健康陪伴群 01", "企业微信", "2026-07-09 21:30:18", "成功"),
        ("AI2075888000000000004", "fanfuni", '{"text":"防晒建议每天使用SPF30+，室内靠窗也需防护。","type":"text"}', "夏天还需要防晒吗？", "梵芙尼旗舰店", "恒康倍力客户群", "企业微信", "2026-07-10 09:05:42", "成功"),
    ]
    for row in rows:
        backend.execute(
            "INSERT INTO message_logs(id, bot_id, content_json, question, account, session, channel, reply_time, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )


def _demo_trace_nodes(
    log_id: str,
    chat_id: str,
    user_input: str,
    chat_msg_count: str,
    history_time: str,
    ai_prompt: str,
    ai_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    runtime_user: str,
    runtime_chat: str,
    runtime_ai: str,
) -> list[tuple]:
    """两个 demo id 的逐字三段（用户输入 / 对话记录获取 / AI对话），对齐原型 6319-6343 / 6355-6379。"""
    return [
        (
            f"trace-{log_id}-1", log_id, 1, "node-1", "用户输入", "userInput", runtime_user,
            json.dumps({
                "chatId": chat_id,
                "messageType": "TEXT",
                "AIAnalyzeChatInput": user_input,
                "userChatInput": user_input,
            }, ensure_ascii=False),
            json.dumps({
                "messageType": "文本",
                "AIAnalyzeChatInput": user_input,
                "finish": True,
                "userChatInput": user_input,
            }, ensure_ascii=False),
            _CODE_USER_INPUT,
        ),
        (
            f"trace-{log_id}-2", log_id, 2, "node-2", "对话记录获取", "chatHistory", runtime_chat,
            json.dumps({
                "chatId": chat_id,
                "chatMsgCount": chat_msg_count,
                "chatHistoryUrl": "http://chat-client-proxy-platform/message/flow/",
            }, ensure_ascii=False),
            json.dumps({
                "messages": [{"role": "user", "content": user_input, "time": history_time}],
                "total": 1,
            }, ensure_ascii=False),
            _CODE_CHAT_HISTORY,
        ),
        (
            f"trace-{log_id}-3", log_id, 3, "node-3", "AI对话", "aiChat", runtime_ai,
            json.dumps({
                "prompt": ai_prompt,
                "history": [{"role": "user", "content": user_input}],
                "model": "gpt-4o-mini",
            }, ensure_ascii=False),
            json.dumps({
                "text": ai_text,
                "type": "text",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            }, ensure_ascii=False),
            _CODE_AI_CHAT,
        ),
    ]


def _yefengqiu_trace_nodes(
    log_id: str,
    chat_id: str,
    user_input: str,
    ai_text: str,
    sent_at: str,
    msg_id: str,
) -> list[tuple]:
    """yefengqiu 工作流 [userInput, aiChat, msgOutput] 三节点。"""
    return [
        (
            f"trace-{log_id}-1", log_id, 1, "node-1", "用户输入", "userInput", "0.005s",
            json.dumps({
                "chatId": chat_id,
                "messageType": "TEXT",
                "AIAnalyzeChatInput": user_input,
                "userChatInput": user_input,
            }, ensure_ascii=False),
            json.dumps({
                "messageType": "文本",
                "AIAnalyzeChatInput": user_input,
                "finish": True,
                "userChatInput": user_input,
            }, ensure_ascii=False),
            _CODE_USER_INPUT,
        ),
        (
            f"trace-{log_id}-2", log_id, 2, "node-2", "AI对话", "aiChat", "2.871s",
            json.dumps({
                "prompt": f"用户说：{user_input}。请友好回复。",
                "history": [{"role": "user", "content": user_input}],
                "model": "gpt-4o-mini",
            }, ensure_ascii=False),
            json.dumps({
                "text": ai_text,
                "type": "text",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 31, "completion_tokens": 18},
            }, ensure_ascii=False),
            _CODE_AI_CHAT,
        ),
        (
            f"trace-{log_id}-3", log_id, 3, "node-3", "消息输出", "msgOutput", "0.017s",
            json.dumps({
                "message": ai_text,
                "splitMode": "不切分",
            }, ensure_ascii=False),
            json.dumps({
                "delivered": True,
                "channel": "企业微信",
                "messageId": msg_id,
                "sentAt": sent_at,
            }, ensure_ascii=False),
            _CODE_MSG_OUTPUT,
        ),
    ]


def _fanfuni_trace_nodes(
    log_id: str,
    chat_id: str,
    user_input: str,
    ai_text: str,
    sent_at: str,
    msg_id: str,
    kb_content: str,
    kb_score: float,
) -> list[tuple]:
    """fanfuni 工作流 [userInput, kbSearch, aiChat, msgOutput] 四节点。"""
    return [
        (
            f"trace-{log_id}-1", log_id, 1, "node-1", "用户输入", "userInput", "0.006s",
            json.dumps({
                "chatId": chat_id,
                "messageType": "TEXT",
                "AIAnalyzeChatInput": user_input,
                "userChatInput": user_input,
            }, ensure_ascii=False),
            json.dumps({
                "messageType": "文本",
                "AIAnalyzeChatInput": user_input,
                "finish": True,
                "userChatInput": user_input,
            }, ensure_ascii=False),
            _CODE_USER_INPUT,
        ),
        (
            f"trace-{log_id}-2", log_id, 2, "node-2", "知识库搜索", "kbSearch", "0.062s",
            json.dumps({
                "query": user_input,
                "kb": "美妆产品知识库",
                "searchMode": "混合搜索",
                "topK": 5,
            }, ensure_ascii=False),
            json.dumps({
                "knowledges": [{"title": "知识库命中", "content": kb_content, "score": kb_score}],
                "total": 1,
            }, ensure_ascii=False),
            _CODE_KB_SEARCH,
        ),
        (
            f"trace-{log_id}-3", log_id, 3, "node-3", "AI对话", "aiChat", "2.431s",
            json.dumps({
                "prompt": f"用户说：{user_input}。请结合知识库回复。\n知识库引用：{kb_content}",
                "history": [{"role": "user", "content": user_input}],
                "model": "gpt-4o-mini",
            }, ensure_ascii=False),
            json.dumps({
                "text": ai_text,
                "type": "text",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 58, "completion_tokens": 21},
            }, ensure_ascii=False),
            _CODE_AI_CHAT,
        ),
        (
            f"trace-{log_id}-4", log_id, 4, "node-4", "消息输出", "msgOutput", "0.021s",
            json.dumps({
                "message": ai_text,
                "splitMode": "不切分",
            }, ensure_ascii=False),
            json.dumps({
                "delivered": True,
                "channel": "企业微信",
                "messageId": msg_id,
                "sentAt": sent_at,
            }, ensure_ascii=False),
            _CODE_MSG_OUTPUT,
        ),
    ]


def _seed_message_log_traces(backend: DatabaseBackend) -> None:
    """编排工作流节点执行追踪种子（两个 demo 逐字三段 + yefengqiu 三节点 + fanfuni 四节点）。"""
    nodes: list[tuple] = []
    # 两个 demo id：原型逐字三段
    nodes += _demo_trace_nodes(
        "AI2075172858125025280",
        "1688855390789285_7881300706932694",
        "行，咱以后可以用",
        "100",
        "2026-07-09 18:58:54",
        "用户说：行，咱以后可以用。请友好回复。",
        "行，咱以后可以用",
        24, 9,
        "0.005s", "0.042s", "2.956s",
    )
    nodes += _demo_trace_nodes(
        "AI2075167178402115584",
        "1688855390789285_7881300706932695",
        "林总，有事吗",
        "98",
        "2026-07-09 18:36:20",
        "用户说：林总，有事吗。请友好回复。",
        "林总，有事吗",
        22, 7,
        "0.004s", "0.038s", "2.843s",
    )
    # yefengqiu 其余日志：三节点
    nodes += _yefengqiu_trace_nodes(
        "AI2074999876543210002",
        "1688855390789285_7000000000000003",
        "库存补好了吗？",
        "林总，今天的通天草库存已补货完成，可继续上架。",
        "2026-07-07 20:45:11",
        "msg-20260707-204511",
    )
    # fanfuni 其余日志：四节点
    nodes += _fanfuni_trace_nodes(
        "AI2075001234567890001",
        "1688855390789285_7000000000000011",
        "这个精华敏感肌能用吗？",
        "您好，这款精华适合敏感肌使用，可放心购买～",
        "2026-07-08 10:12:03",
        "msg-20260708-101203",
        "舒缓修护精华含积雪草与神经酰胺，成分温和，专为敏感肌设计，首次使用建议耳后测试。",
        0.92,
    )
    nodes += _fanfuni_trace_nodes(
        "AI2075888000000000003",
        "1688855390789285_7000000000000012",
        "会员有什么优惠？",
        "会员专享8折，今晚24点前下单有效哦～",
        "2026-07-09 21:30:18",
        "msg-20260709-213018",
        "会员享专属折扣、生日礼遇与积分加倍，可在「我的-会员中心」查看。",
        0.88,
    )
    nodes += _fanfuni_trace_nodes(
        "AI2075888000000000004",
        "1688855390789285_7000000000000013",
        "夏天还需要防晒吗？",
        "防晒建议每天使用SPF30+，室内靠窗也需防护。",
        "2026-07-10 09:05:42",
        "msg-20260710-090542",
        "紫外线四季存在，室内靠窗与冬季也需防晒，日常以SPF30+ PA+++为宜。",
        0.85,
    )
    for node in nodes:
        backend.execute(
            "INSERT INTO message_log_traces(id, log_id, node_order, node_key, node_name, node_type, runtime, input_json, output_json, code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            node,
        )


def _seed_operation_tasks(backend: DatabaseBackend) -> None:
    """运营任务种子数据（4 个任务 + 关联 targets）。"""
    import datetime as _dt

    tasks = [
        {
            "id": "opt-1",
            "name": "杨奇成第一课",
            "task_type": "群发任务",
            "channel_type": "企业微信",
            "session_type": "群聊",
            "content_blocks": '[{"type":"text","content":"打"}]',
            "hosting_action": "保持不变",
            "run_frequency": "一次",
            "run_time": "2026-07-10 04:02:00",
            "effective_start": "2026-07-01 00:00:00",
            "effective_end": "2026-07-31 23:59:59",
            "cron_expression": "",
            "run_status": "已完成",
            "enabled": 1,
            "next_run_time": "2026-07-10 04:02:00",
        },
        {
            "id": "opt-2",
            "name": "第一节课",
            "task_type": "群发任务",
            "channel_type": "企业微信",
            "session_type": "群聊",
            "content_blocks": '[{"type":"text","content":"打"}]',
            "hosting_action": "保持不变",
            "run_frequency": "一次",
            "run_time": "2026-07-11 04:02:00",
            "effective_start": "2026-07-01 00:00:00",
            "effective_end": "2026-07-31 23:59:59",
            "cron_expression": "",
            "run_status": "未运行",
            "enabled": 0,
            "next_run_time": "2026-07-11 04:02:00",
        },
        {
            "id": "opt-3",
            "name": "每日早安问候",
            "task_type": "机器人定时任务",
            "channel_type": "企业微信",
            "session_type": "单聊",
            "content_blocks": '[{"type":"text","content":"早安！新的一天开始了，今天也要元气满满哦~"}]',
            "hosting_action": "保持不变",
            "run_frequency": "每天",
            "run_time": "08:00",
            "effective_start": "2026-07-01 00:00:00",
            "effective_end": "2026-12-31 23:59:59",
            "cron_expression": "",
            "run_status": "未运行",
            "enabled": 1,
            "next_run_time": "2026-07-20 08:00:00",
        },
        {
            "id": "opt-4",
            "name": "周末活动推送",
            "task_type": "朋友圈任务",
            "channel_type": "企业微信",
            "session_type": "群聊",
            "content_blocks": '[{"type":"text","content":"周末特惠活动已上线！快来参加吧~"}]',
            "hosting_action": "保持不变",
            "run_frequency": "每周",
            "run_time": "10:00",
            "effective_start": "2026-07-01 00:00:00",
            "effective_end": "2026-12-31 23:59:59",
            "cron_expression": "",
            "run_status": "未运行",
            "enabled": 1,
            "next_run_time": "2026-07-25 10:00:00",
        },
    ]

    for task in tasks:
        backend.execute(
            """INSERT INTO operation_tasks(
                id, name, task_type, channel_type, session_type,
                content_blocks, hosting_action, run_frequency, run_time,
                effective_start, effective_end, cron_expression,
                schedule_type, schedule_config,
                run_status, enabled, next_run_time, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                task["id"], task["name"], task["task_type"], task["channel_type"],
                task["session_type"], task["content_blocks"], task["hosting_action"],
                task["run_frequency"], task["run_time"], task["effective_start"],
                task["effective_end"], task["cron_expression"],
                task.get("schedule_type", ""), task.get("schedule_config", ""),
                task["run_status"],
                task["enabled"], task["next_run_time"],
            ),
        )

    # 种子 targets 映射
    task_targets_map = {
        "opt-1": ["ses-drjack", "ses-tongtian", "ses-zhizu"],
        "opt-2": ["ses-fushou", "ses-drjack"],
        "opt-3": ["ses-tongtian", "ses-zhizu", "ses-fushou"],
        "opt-4": ["ses-drjack", "ses-tongtian"],
    }

    for task_id, session_ids in task_targets_map.items():
        for session_id in session_ids:
            target_id = f"optt-{task_id}-{session_id.replace('ses-', '')}"
            backend.execute(
                "INSERT INTO operation_task_targets(id, task_id, target_type, session_id, filter_rules) "
                "VALUES (?, ?, ?, ?, ?)",
                (target_id, task_id, "static", session_id, "{}"),
            )

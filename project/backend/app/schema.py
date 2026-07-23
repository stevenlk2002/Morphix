"""数据库 schema 与索引定义。

集中管理建表语句与索引，保证：
- 建表语句与 database/init_morphix_mvp.sql 保持一致（幂等 CREATE IF NOT EXISTS）。
- 为高频查询列建立索引，兑现「分页/索引规范」性能落地要求。
- 种子数据仅在表为空时写入，避免重复。
"""
from __future__ import annotations

import json
import os

from .database import DatabaseBackend

# bot_id -> 显示名映射（前端「所属机器人」下拉与列表 robot 列共用）
BOT_NAMES: dict[str, str] = {
    "yefengqiu": "野风秋大健康机器人",
    "fanfuni": "笑笑尼家效销售机器人",
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
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- 账号卡片增强（本期）
  avatar TEXT NOT NULL DEFAULT '',
  default_single_bot_id TEXT NOT NULL DEFAULT '',
  default_group_bot_id TEXT NOT NULL DEFAULT ''
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
  description  TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 团队成员（冗余 account/nickname/role，避免 JOIN 授权用户内存表；team_id+user_id 唯一去重）
CREATE TABLE IF NOT EXISTS team_members (
  id          TEXT PRIMARY KEY,
  team_id     TEXT NOT NULL,
  user_id     TEXT NOT NULL,
  account     TEXT NOT NULL DEFAULT '',
  nickname    TEXT NOT NULL DEFAULT '',
  role        TEXT NOT NULL DEFAULT '',
  joined_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(team_id, user_id),
  FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id);

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
  source      TEXT NOT NULL DEFAULT '',
  -- iPad 协议同步扩展字段（T01）
  user_id     TEXT NOT NULL DEFAULT '',
  label_ids   TEXT NOT NULL DEFAULT '[]',
  raw_status  TEXT NOT NULL DEFAULT '',
  extra_json  TEXT NOT NULL DEFAULT '{}'
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
  -- iPad 协议同步扩展字段（T01）：外部联系人 labelid[] 原样镜像
  tags        TEXT NOT NULL DEFAULT '[]',
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
  hosting_chain TEXT NOT NULL DEFAULT '-',
  -- iPad 协议同步扩展字段（T01）
  remote_session_id TEXT NOT NULL DEFAULT '',
  msg_type    INTEGER NOT NULL DEFAULT 0,
  begin_msg_seq TEXT NOT NULL DEFAULT ''
);

-- ---- iPad 协议：客户群 / 内部群（不污染 channel_contacts，决策 #1） ----
CREATE TABLE IF NOT EXISTS channel_groups (
  id          TEXT PRIMARY KEY,
  account_id  TEXT NOT NULL DEFAULT '',
  room_id     TEXT NOT NULL DEFAULT '',
  group_type  TEXT NOT NULL DEFAULT 'customer_group',
  nickname    TEXT NOT NULL DEFAULT '',
  total       INTEGER NOT NULL DEFAULT 0,
  room_url    TEXT NOT NULL DEFAULT '',
  notice_content TEXT NOT NULL DEFAULT '',
  create_time TEXT NOT NULL DEFAULT '',
  update_time TEXT NOT NULL DEFAULT '',
  extra_json  TEXT NOT NULL DEFAULT '{}',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_group_members (
  id          TEXT PRIMARY KEY,
  group_id    TEXT NOT NULL DEFAULT '',
  uin         TEXT NOT NULL DEFAULT '',
  user_id     TEXT NOT NULL DEFAULT '',
  nickname    TEXT NOT NULL DEFAULT '',
  realname    TEXT NOT NULL DEFAULT '',
  avatar      TEXT NOT NULL DEFAULT '',
  room_nickname TEXT NOT NULL DEFAULT '',
  sex         INTEGER NOT NULL DEFAULT 0,
  mobile      TEXT NOT NULL DEFAULT '',
  join_time   TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

-- ---- LLM 配置表 ----
CREATE TABLE IF NOT EXISTS llm_model_configs (
  id TEXT PRIMARY KEY,
  vendor TEXT NOT NULL DEFAULT '',
  model_name TEXT NOT NULL DEFAULT '',
  api_key TEXT NOT NULL DEFAULT '',
  api_base_url TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---- 系统消息（消息中心） ----
CREATE TABLE IF NOT EXISTS system_messages (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL DEFAULT '',
  msg_time TEXT NOT NULL DEFAULT '',
  is_read INTEGER NOT NULL DEFAULT 0,
  is_warning INTEGER NOT NULL DEFAULT 0
);

-- ---- iPad 标签 ↔ Morphix 标签 映射（P1-1，幂等键 account_id + ipad_label_id） ----
CREATE TABLE IF NOT EXISTS ipad_label_map (
  account_id      TEXT NOT NULL DEFAULT '',
  ipad_label_id   TEXT NOT NULL DEFAULT '',
  label_name      TEXT NOT NULL DEFAULT '',
  label_type      INTEGER NOT NULL DEFAULT 0,
  label_group_id  TEXT NOT NULL DEFAULT '',
  tag_id          TEXT NOT NULL DEFAULT '',   -- 对应 customer_tags.id
  sync_type       INTEGER NOT NULL DEFAULT 0, -- 1=企业标签 2=个人标签
  PRIMARY KEY (account_id, ipad_label_id)
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

-- ---- iPad 协议同步域索引 ----
CREATE INDEX IF NOT EXISTS idx_channel_contacts_user ON channel_contacts(account_id, user_id);
CREATE INDEX IF NOT EXISTS idx_channel_groups_account ON channel_groups(account_id, group_type);
CREATE INDEX IF NOT EXISTS idx_channel_groups_room ON channel_groups(account_id, room_id);
CREATE INDEX IF NOT EXISTS idx_channel_group_members_group ON channel_group_members(group_id);
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

-- ---- P1+P2 iPad 同步域索引 ----
CREATE INDEX IF NOT EXISTS idx_ipad_label_map_account      ON ipad_label_map(account_id);
CREATE INDEX IF NOT EXISTS idx_messages_account           ON messages(channel_account_id, conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_server            ON messages(conversation_id, server_id);

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

-- ---- LLM 配置索引 ----
CREATE INDEX IF NOT EXISTS idx_llm_model_configs_updated ON llm_model_configs(updated_at);

-- ---- 系统消息索引 ----
CREATE INDEX IF NOT EXISTS idx_system_messages_read ON system_messages(is_read);
"""


def dashboard_seed() -> dict:
    """种子数据源（与原实现保持一致，保证 contract 不变）。"""
    return {
        "bots": [
            {"id": "yefengqiu", "name": "野风秋大健康机器人", "project": "Morphix", "status": "online", "workflow": "销售接待主流程", "tone": "亲切专业", "score": 92},
            {"id": "fanfuni", "name": "笑笑尼家效销售机器人", "project": "Morphix", "status": "training", "workflow": "售后问题处理", "tone": "耐心清晰", "score": 81},
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
        # 企业微信 iPad 协议托管接入（T01）
        "ipad_uuid": "TEXT NOT NULL DEFAULT ''",
        "ipad_user_info": "TEXT NOT NULL DEFAULT '{}'",
        "host_status": "TEXT NOT NULL DEFAULT 'pending'",
    }
    for col, ddl in _channel_account_cols.items():
        if not _has_column(backend, "channel_accounts", col):
            backend.execute(f"ALTER TABLE channel_accounts ADD COLUMN {col} {ddl}")

    # ---- iPad 协议同步域迁移（T01） ----
    # channel_accounts 同步状态
    _channel_account_sync_cols = {
        "sync_status": "TEXT NOT NULL DEFAULT ''",
        "last_sync_at": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in _channel_account_sync_cols.items():
        if not _has_column(backend, "channel_accounts", col):
            backend.execute(f"ALTER TABLE channel_accounts ADD COLUMN {col} {ddl}")

    # channel_contacts iPad 扩展字段
    _channel_contacts_cols = {
        "user_id": "TEXT NOT NULL DEFAULT ''",
        "label_ids": "TEXT NOT NULL DEFAULT '[]'",
        "raw_status": "TEXT NOT NULL DEFAULT ''",
        "extra_json": "TEXT NOT NULL DEFAULT '{}'",
    }
    for col, ddl in _channel_contacts_cols.items():
        if not _has_column(backend, "channel_contacts", col):
            backend.execute(f"ALTER TABLE channel_contacts ADD COLUMN {col} {ddl}")

    # channel_sessions iPad 扩展字段
    _channel_sessions_cols = {
        "remote_session_id": "TEXT NOT NULL DEFAULT ''",
        "msg_type": "INTEGER NOT NULL DEFAULT 0",
        "begin_msg_seq": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in _channel_sessions_cols.items():
        if not _has_column(backend, "channel_sessions", col):
            backend.execute(f"ALTER TABLE channel_sessions ADD COLUMN {col} {ddl}")

    # customer_profiles.tags（外部联系人 labelid[] 原样镜像）
    if not _has_column(backend, "customer_profiles", "tags"):
        backend.execute("ALTER TABLE customer_profiles ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")

    # ---- P1+P2 iPad 同步域迁移 ----
    # channel_accounts 回调配置列（P2-4 实时回调；IPAD_CALLBACK_PUBLIC_URL 未配置则保持空）
    _channel_account_callback_cols = {
        "callback_url": "TEXT NOT NULL DEFAULT ''",
        "callback_type": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in _channel_account_callback_cols.items():
        if not _has_column(backend, "channel_accounts", col):
            backend.execute(f"ALTER TABLE channel_accounts ADD COLUMN {col} {ddl}")

    # ---- 账号卡片增强迁移（本期 T01） ----
    # channel_accounts 头像 + 默认单聊/群聊机器人（空串表示未设置，与既有 ipad_uuid 列一致）
    _channel_account_card_cols = {
        "avatar": "TEXT NOT NULL DEFAULT ''",
        "default_single_bot_id": "TEXT NOT NULL DEFAULT ''",
        "default_group_bot_id": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in _channel_account_card_cols.items():
        if not _has_column(backend, "channel_accounts", col):
            backend.execute(f"ALTER TABLE channel_accounts ADD COLUMN {col} {ddl}")

    # messages 表扩展（P2 消息历史回填 / 已读 / 富媒体；统一复用 messages 表，决策 #6）
    _messages_cols = {
        "server_id": "TEXT NOT NULL DEFAULT ''",
        "msg_type": "INTEGER NOT NULL DEFAULT 0",     # 0文本 1图片 2文件 3应用 ...
        "sender_id": "TEXT NOT NULL DEFAULT ''",       # iPad user_id/room_id
        "direction": "TEXT NOT NULL DEFAULT 'inbound'",  # inbound|outbound
        "content_type": "TEXT NOT NULL DEFAULT 'text'",  # text|image|file
        "media_url": "TEXT NOT NULL DEFAULT ''",
        "media_meta": "TEXT NOT NULL DEFAULT '{}'",    # {width,height,size,md5,fileName,...}
        "is_read": "INTEGER NOT NULL DEFAULT 0",
        "channel_account_id": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in _messages_cols.items():
        if not _has_column(backend, "messages", col):
            backend.execute(f"ALTER TABLE messages ADD COLUMN {col} {ddl}")

    # ipad_label_map 为全新表，CREATE IF NOT EXISTS 同时覆盖新库与旧库，无需 ALTER。

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

    # ---- 渠道团队迁移：teams.description（本期新增，幂等 ALTER） ----
    # 新库由上方 CREATE TABLE 直接带列；旧库（teams 已存在但缺 description）在此补列。
    if not _has_column(backend, "teams", "description"):
        backend.execute("ALTER TABLE teams ADD COLUMN description TEXT NOT NULL DEFAULT ''")


def _count(backend: DatabaseBackend, sql: str, params: tuple = ()) -> int:
    """安全取 COUNT(*) 结果，COUNT 查询恒返回一行。"""
    row = backend.query_one(sql, params)
    return int(row["c"]) if row is not None else 0


def seed_defaults(backend: DatabaseBackend) -> None:
    """仅在空表时写入种子数据。

    渠道会话管理域演示数据（引用 acc-zhulu / acc-hengkang / acc-fushou 的会话、
    消息、托管席位等）默认不再注入，避免污染干净库、干扰真实流程测试。
    需要演示时设置环境变量 MORPHIX_SEED_CHANNEL_DEMO=1。
    """
    # 渠道会话演示数据开关：默认关闭，仅当显式设置 MORPHIX_SEED_CHANNEL_DEMO=1 时注入。
    _seed_channel_demo = os.environ.get("MORPHIX_SEED_CHANNEL_DEMO") == "1"
    if _count(backend, "SELECT COUNT(*) AS c FROM bots") == 0:
        for bot in dashboard_seed()["bots"]:
            backend.execute(
                "INSERT INTO bots(id, name, project, status, workflow, tone, training_prompt, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (bot["id"], bot["name"], bot["project"], bot["status"], bot["workflow"], bot["tone"], "围绕客户意图生成专业、合规、可转人工的话术。", bot["score"]),
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
            ("s-1", "张先生", "企业微信", "yefengqiu", "AI托管", "价格咨询", "标准版支持多少个账号？", "2分钟前"),
            ("s-2", "Alicia", "WhatsApp", "fanfuni", "人工接管", "预约演示", "Can we schedule a demo?", "8分钟前"),
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
            ("yefengqiu", 120, "2027-06-30 23:59:59"),
            ("fanfuni", 300, "2027-12-31 23:59:59"),
            ("bot-3", 80, "2026-12-31 23:59:59"),
        ]
        for row in subs:
            backend.execute(
                "INSERT INTO bot_subscriptions(bot_id, hosted_sessions, expire_at) VALUES (?, ?, ?)",
                row,
            )

    # ---- 渠道会话管理域种子（teams / contacts / sessions / hosting / wechat_subjects） ----
    if _count(backend, "SELECT COUNT(*) AS c FROM teams") == 0:
        backend.execute(
            "INSERT INTO teams(id, name, seats_left, energy_value, description) VALUES (?, ?, ?, ?, ?)",
            ("team-initial", "初始团队", 1, 908, ""),
        )

    # 渠道会话演示数据：引用 acc-zhulu / acc-hengkang / acc-fushou，受开关控制（默认不注入）。
    if _seed_channel_demo and _count(backend, "SELECT COUNT(*) AS c FROM channel_sessions") == 0:
        sessions = [
            ("ses-drjack", "acc-zhulu", "Dr.Jack 恒康倍力", "@微信", "wechat", "可以的，后续可以用", "10:36", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-06-30 18:29:18", "-"),
            ("ses-tongtian", "acc-zhulu", "通天草-林瞰", "@微信", "wechat", "竹绿-健康：亲爱的您好呀...", "10:41", 2, "unread", "unhosted", None, "竹", "online", "外部联系人", "外部", "2026-06-30 18:29:19", "-"),
            ("ses-zhizu", "acc-zhulu", "知足常乐【中奖】", "@微信", "wechat", "感谢参与本次活动", "09:12", 0, "read", "hosted", "yefengqiu", "竹", "offline", "外部联系人", "外部", "2026-06-30 18:29:20", "-"),
            ("ses-fushou", "acc-zhulu", "福寿康VIP", "@微信", "wechat", "您好，想咨询一下产品", "昨天", 0, "read", "unhosted", None, "竹", "offline", "外部联系人", "外部", "2026-06-30 18:29:21", "-"),
            # ---- 近 7 天种子（2026-07-14 ~ 2026-07-20），让数据面板有丰富内容 ----
            ("ses-714a", "acc-zhulu", "格布式健康咨询", "@微信", "wechat", "你好，想了解一下产品", "07-14", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-07-14 09:30:00", "-"),
            ("ses-714b", "acc-hengkang", "笑笑尼家效会员", "@企业微信", "wecom", "最近的优惠活动还有吗？", "07-14", 1, "unread", "hosted", "fanfuni", "恒", "online", "外部联系人", "外部", "2026-07-14 14:20:00", "-"),
            ("ses-715a", "acc-zhulu", "客户王阿姨", "@微信", "wechat", "帮我看看这个产品", "07-15", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-07-15 10:15:00", "-"),
            ("ses-715b", "acc-hengkang", "李先生咨询", "@企业微信", "wecom", "请问套餐价格？", "07-15", 0, "read", "unhosted", None, "恒", "offline", "外部联系人", "外部", "2026-07-15 16:40:00", "-"),
            ("ses-716a", "acc-zhulu", "用户张先生", "@微信", "wechat", "直播链接发一下", "07-16", 0, "read", "hosted", "yefengqiu", "竹", "offline", "外部联系人", "外部", "2026-07-16 08:50:00", "-"),
            ("ses-716b", "acc-zhulu", "新用户测试", "@微信", "wechat", "注册流程怎么样？", "07-16", 2, "unread", "unhosted", None, "竹", "online", "外部联系人", "外部", "2026-07-16 11:30:00", "-"),
            ("ses-717a", "acc-hengkang", "老客户赵姐", "@企业微信", "wecom", "帮我续费", "07-17", 1, "unread", "hosted", "fanfuni", "恒", "online", "外部联系人", "外部", "2026-07-17 09:00:00", "-"),
            ("ses-717b", "acc-zhulu", "陈总私人号", "@微信", "wechat", "上次的项目跟进一下", "07-17", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-07-17 15:20:00", "-"),
            ("ses-717c", "acc-fushou", "李女士问价", "@微信", "wechat", "价格表发我", "07-17", 0, "read", "unhosted", None, "福", "online", "外部联系人", "外部", "2026-07-17 17:45:00", "-"),
            ("ses-718a", "acc-zhulu", "VIP客户Tina", "@微信", "wechat", "预约明天的线上问诊", "07-18", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-07-18 08:10:00", "-"),
            ("ses-718b", "acc-hengkang", "学生家长群问", "@企业微信", "wecom", "暑假体验课还有名额吗", "07-18", 3, "unread", "unhosted", None, "恒", "offline", "外部联系人", "外部", "2026-07-18 14:00:00", "-"),
            ("ses-719a", "acc-zhulu", "周医生咨询", "@微信", "wechat", "帮我看看这个处方", "07-19", 1, "unread", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-07-19 07:30:00", "-"),
            ("ses-719b", "acc-zhulu", "孙阿姨复诊", "@微信", "wechat", "上次开的药吃完了", "07-19", 0, "read", "hosted", "yefengqiu", "竹", "online", "外部联系人", "外部", "2026-07-19 10:45:00", "-"),
            ("ses-719c", "acc-hengkang", "吴老师推荐", "@企业微信", "wecom", "您好我是吴老师推荐的", "07-19", 0, "read", "hosted", "fanfuni", "恒", "online", "外部联系人", "外部", "2026-07-19 16:20:00", "-"),
            ("ses-720a", "acc-zhulu", "健身老刘", "@微信", "wechat", "今天约几点？", "07-20", 0, "read", "hosted", "yefengqiu", "竹", "offline", "外部联系人", "外部", "2026-07-20 09:00:00", "-"),
            ("ses-720b", "acc-hengkang", "群内@小助手", "@企业微信", "wecom", "有人发广告", "07-20", 0, "read", "unhosted", None, "恒", "online", "外部联系人", "外部", "2026-07-20 11:30:00", "-"),
        ]
        for row in sessions:
            backend.execute(
                "INSERT INTO channel_sessions(id, account_id, name, channel, channel_type, last_message, last_time, unread_count, read_status, hosted_status, hosted_bot_id, owner, online_status, session_type, external_tag, add_time, hosting_chain) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

    # 为上述演示渠道会话写的消息（conversation_id 以 ses- 前缀），同样受开关控制（默认不注入）。
    if _seed_channel_demo and _count(backend, "SELECT COUNT(*) AS c FROM messages WHERE conversation_id LIKE 'ses-%'") == 0:
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
            # ---- 近 7 天消息种子（与上面新增的会话对应） ----
            ("msg-714a-1", "ses-714a", "user", "你好，想了解一下产品", "2026-07-14 09:30:00"),
            ("msg-714a-2", "ses-714a", "bot", "您好！很高兴为您服务，请问您想了解哪方面的产品呢？", "2026-07-14 09:30:03"),
            ("msg-714a-3", "ses-714a", "user", "主要是健康管理这块", "2026-07-14 09:31:00"),
            ("msg-714a-4", "ses-714a", "bot", "好的，我们的健康管理方案覆盖慢病管理、体检报告解读等多个维度。", "2026-07-14 09:31:05"),
            ("msg-714b-1", "ses-714b", "user", "最近的优惠活动还有吗？", "2026-07-14 14:20:00"),
            ("msg-714b-2", "ses-714b", "bot", "有的！目前暑期特惠正在进行中，会员可享8折优惠哦~", "2026-07-14 14:20:04"),
            ("msg-714b-3", "ses-714b", "user", "太好了，我报个名", "2026-07-14 14:21:00"),
            ("msg-714b-4", "ses-714b", "bot", "已为您登记，稍后会有客服联系您确认。", "2026-07-14 14:21:05"),
            ("msg-715a-1", "ses-715a", "user", "帮我看看这个产品", "2026-07-15 10:15:00"),
            ("msg-715a-2", "ses-715a", "bot", "好的，请您发送产品图片或名称，我来帮您查询。", "2026-07-15 10:15:05"),
            ("msg-715a-3", "ses-715a", "user", "就是那个保健茶", "2026-07-15 10:16:00"),
            ("msg-715a-4", "ses-715a", "system", "需要转人工：客户需要详细了解产品成分", "2026-07-15 10:16:30"),
            ("msg-715b-1", "ses-715b", "user", "请问套餐价格？", "2026-07-15 16:40:00"),
            ("msg-715b-2", "ses-715b", "bot", "目前基础套餐498元/月，高级套餐998元/月，您更关注哪个呢？", "2026-07-15 16:40:05"),
            ("msg-716a-1", "ses-716a", "user", "直播链接发一下", "2026-07-16 08:50:00"),
            ("msg-716a-2", "ses-716a", "bot", "今天的健康讲座直播将于10:00开始，链接已发送到您微信~", "2026-07-16 08:50:05"),
            ("msg-716b-1", "ses-716b", "user", "注册流程怎么样？", "2026-07-16 11:30:00"),
            ("msg-716b-2", "ses-716b", "bot", "注册很简单！只需要微信扫码→填写手机号→验证码→完成，约2分钟。", "2026-07-16 11:30:05"),
            ("msg-716b-3", "ses-716b", "user", "好的谢谢", "2026-07-16 11:31:00"),
            ("msg-716b-4", "ses-716b", "bot", "不客气，如有问题随时咨询~", "2026-07-16 11:31:05"),
            ("msg-717a-1", "ses-717a", "user", "帮我续费", "2026-07-17 09:00:00"),
            ("msg-717a-2", "ses-717a", "bot", "赵姐您好！您的会员将于月底到期，现在我帮您操作续费，确认一下是继续高级套餐吗？", "2026-07-17 09:00:05"),
            ("msg-717a-3", "ses-717a", "user", "对，就高级套餐", "2026-07-17 09:01:00"),
            ("msg-717a-4", "ses-717a", "bot", "好的，已提交续费申请，预计1个工作日内生效。", "2026-07-17 09:01:08"),
            ("msg-717a-5", "ses-717a", "system", "客户确认续费高级套餐，请安排跟进。", "2026-07-17 09:01:30"),
            ("msg-717b-1", "ses-717b", "user", "上次的项目跟进一下", "2026-07-17 15:20:00"),
            ("msg-717b-2", "ses-717b", "bot", "陈总好！上次关于企业健康管理的方案我已经整理好了，您方便什么时候详细沟通？", "2026-07-17 15:20:06"),
            ("msg-717c-1", "ses-717c", "user", "价格表发我", "2026-07-17 17:45:00"),
            ("msg-717c-2", "ses-717c", "bot", "好的，产品价格表已发送给您，请查收。如有疑问可以随时问我~", "2026-07-17 17:45:05"),
            ("msg-718a-1", "ses-718a", "user", "预约明天的线上问诊", "2026-07-18 08:10:00"),
            ("msg-718a-2", "ses-718a", "bot", "Tina您好！明天上午9:00-11:00、下午14:00-17:00都有号，您方便哪个时段？", "2026-07-18 08:10:05"),
            ("msg-718a-3", "ses-718a", "user", "上午9点吧", "2026-07-18 08:11:00"),
            ("msg-718a-4", "ses-718a", "bot", "已为您预约明天上午9:00线上问诊，届时请提前5分钟进入直播间~", "2026-07-18 08:11:08"),
            ("msg-718b-1", "ses-718b", "user", "暑假体验课还有名额吗", "2026-07-18 14:00:00"),
            ("msg-718b-2", "ses-718b", "bot", "有的！7月体验课还有5个名额，需要帮您预留吗？", "2026-07-18 14:00:05"),
            ("msg-719a-1", "ses-719a", "user", "帮我看看这个处方", "2026-07-19 07:30:00"),
            ("msg-719a-2", "ses-719a", "bot", "周医生您好，我暂时无法解读处方哦，建议您转人工咨询我们的执业药师。", "2026-07-19 07:30:05"),
            ("msg-719a-3", "ses-719a", "system", "转人工：客户需要处方解读，转入执业药师", "2026-07-19 07:30:20"),
            ("msg-719b-1", "ses-719b", "user", "上次开的药吃完了", "2026-07-19 10:45:00"),
            ("msg-719b-2", "ses-719b", "bot", "孙阿姨好！需要帮您续方吗？请确认一下药品名称和用量。", "2026-07-19 10:45:05"),
            ("msg-719b-3", "ses-719b", "user", "就是那个降压的药", "2026-07-19 10:46:00"),
            ("msg-719b-4", "ses-719b", "bot", "好的，降压药已记录。需要转人工确认续方，请稍等~", "2026-07-19 10:46:05"),
            ("msg-719b-5", "ses-719b", "system", "转人工：客户续方确认为降压药", "2026-07-19 10:46:20"),
            ("msg-719c-1", "ses-719c", "user", "您好我是吴老师推荐的", "2026-07-19 16:20:00"),
            ("msg-719c-2", "ses-719c", "bot", "您好！欢迎！吴老师是老客户了，请问您想了解哪方面的服务呢？", "2026-07-19 16:20:05"),
            ("msg-719c-3", "ses-719c", "user", "我想了解一下健康体检套餐", "2026-07-19 16:21:00"),
            ("msg-719c-4", "ses-719c", "bot", "好的！我们提供基础体检（399元）、全面体检（899元）和VIP深度体检（1999元）三种套餐。需要我详细介绍一下吗？", "2026-07-19 16:21:08"),
            ("msg-720a-1", "ses-720a", "user", "今天约几点？", "2026-07-20 09:00:00"),
            ("msg-720a-2", "ses-720a", "bot", "老刘好！今天的私教课是上午10:00，健身房3号厅见~", "2026-07-20 09:00:05"),
            ("msg-720b-1", "ses-720b", "user", "有人发广告", "2026-07-20 11:30:00"),
            ("msg-720b-2", "ses-720b", "system", "已检测群内广告内容，自动移除了该成员。", "2026-07-20 11:30:10"),
        ]
        for msg_id, conv_id, sender_type, content, ts in session_messages:
            backend.execute(
                "INSERT INTO messages(id, conversation_id, sender_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (msg_id, conv_id, sender_type, content, ts),
            )

    # 托管席位演示数据：引用 acc-zhulu，与渠道会话共用同一开关，避免孤儿引用（默认不注入）。
    if _seed_channel_demo and _count(backend, "SELECT COUNT(*) AS c FROM hosting_sessions") == 0:
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

    # ---- 运营SOP域种子（SOP 配置含 hostingAccountId=acc-zhulu 演示引用，受同一开关控制，默认不注入）----
    if _seed_channel_demo and _count(backend, "SELECT COUNT(*) AS c FROM operation_sops") == 0:
        _seed_operation_sops(backend)

    if _count(backend, "SELECT COUNT(*) AS c FROM operation_sop_records") == 0:
        _seed_operation_sop_records(backend)

    # ---- LLM 配置种子（主 / 副模型各 1 条） ----
    if _count(backend, "SELECT COUNT(*) AS c FROM llm_model_configs") == 0:
        backend.execute(
            "INSERT INTO llm_model_configs(id, vendor, model_name, api_key, api_base_url, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("primary", "OpenAI", "GPT-4o", "sk-orchestrator-7f3a9c2e1b4d", "https://api.openai.com/v1", 1),
        )
        backend.execute(
            "INSERT INTO llm_model_configs(id, vendor, model_name, api_key, api_base_url, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("secondary", "Anthropic", "Claude 3.5 Sonnet", "", "", 0),
        )

    # ---- 系统消息（消息中心）种子 ----
    if _count(backend, "SELECT COUNT(*) AS c FROM system_messages") == 0:
        _seed_system_messages(backend)


def _seed_system_messages(backend: DatabaseBackend) -> None:
    """消息中心种子（1 条额度预警 + 6 条竹绿-健康同步事件），与原型一致。"""
    messages: list[dict] = [
        {
            "id": "msg-1",
            "title": "可用额度不足预警",
            "content": "账户的可用额度仅剩余0.00元，为避免影响您的正常使用，请及时进入资源管理进行充值。",
            "msg_time": "2026-07-10 10:20:02",
            "is_read": 0,
            "is_warning": 1,
        },
        {
            "id": "msg-2",
            "title": "[竹绿-健康]已完成同步",
            "content": "[竹绿-健康]已于2026-07-09 22:43:43完成同步，您现在可以开始使用该账号了，如果您没有看到对话，请刷新页面。",
            "msg_time": "2026-07-09 22:43:43",
            "is_read": 0,
            "is_warning": 0,
        },
        {
            "id": "msg-3",
            "title": "[竹绿-健康]已开始同步",
            "content": "[竹绿-健康]已于2026-07-09 22:41:39开始同步，预计将在20分钟内同步完成，请勿在其他pc设备登录账号。",
            "msg_time": "2026-07-09 22:41:45",
            "is_read": 0,
            "is_warning": 0,
        },
        {
            "id": "msg-4",
            "title": "[竹绿-健康]已上线",
            "content": "[竹绿-健康]已于2026-07-09 22:41:39上线，您可以接收到该账号的消息了。",
            "msg_time": "2026-07-09 22:41:40",
            "is_read": 0,
            "is_warning": 0,
        },
        {
            "id": "msg-5",
            "title": "[竹绿-健康]已掉线",
            "content": "[竹绿-健康]已于2026-07-09 22:38:54掉线，原因为[客户端登出]。为不影响您的消息接收，请尽快重新登录。",
            "msg_time": "2026-07-09 22:38:54",
            "is_read": 0,
            "is_warning": 0,
        },
        {
            "id": "msg-6",
            "title": "[竹绿-健康]已完成同步",
            "content": "[竹绿-健康]已于2026-07-09 18:13:41完成同步，您现在可以开始使用该账号了，如果您没有看到对话，请刷新页面。",
            "msg_time": "2026-07-09 18:13:41",
            "is_read": 0,
            "is_warning": 0,
        },
        {
            "id": "msg-7",
            "title": "[竹绿-健康]已开始同步",
            "content": "[竹绿-健康]已于2026-07-09 18:09:31开始同步，预计将在20分钟内同步完成，请勿在其他pc设备登录账号。",
            "msg_time": "2026-07-09 18:09:39",
            "is_read": 0,
            "is_warning": 0,
        },
    ]
    for m in messages:
        backend.execute(
            "INSERT INTO system_messages(id, title, content, msg_time, is_read, is_warning) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (m["id"], m["title"], m["content"], m["msg_time"], m["is_read"], m["is_warning"]),
        )


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
    """客户管理域种子数据（仅保留标签分组与标签两类种子，移除扩展联系人/标签关系/客户分组等 demo）。"""
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

-- Morphix 资源域建库脚本（权威快照，须与 app/schema.py 的 SCHEMA_SQL + INDEX_SQL 保持一致）
-- 仅用于独立初始化数据库；运行时 schema 以 schema.py 为准（含幂等迁移）。

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

-- ---- 索引 ----
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
CREATE INDEX IF NOT EXISTS idx_workflow_runs_conversation ON workflow_runs(conversation_id, started_at);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_conversations_bot ON conversations(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_subscriptions_bot ON bot_subscriptions(bot_id);
CREATE INDEX IF NOT EXISTS idx_channel_seats_account ON channel_seats(channel_account_id);
CREATE INDEX IF NOT EXISTS idx_orch_wf_bot ON orchestration_workflows(bot_id);
CREATE INDEX IF NOT EXISTS idx_training_records_bot ON training_records(bot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_training_messages_record ON training_messages(record_id, msg_order);

-- ---- 托管消息日志（与 schema.py 保持一致） ----
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

-- ---- 渠道会话管理域（与 schema.py SCHEMA_SQL 保持一致） ----
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

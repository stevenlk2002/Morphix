"""运营任务 API 验收测试。

覆盖端点：
- GET    /api/operations/tasks
- POST   /api/operations/tasks
- GET    /api/operations/tasks/{id}
- PUT    /api/operations/tasks/{id}
- PATCH  /api/operations/tasks/{id}/toggle
- DELETE /api/operations/tasks/{id}
- GET    /api/operations/tasks/{id}/targets
- PUT    /api/operations/tasks/{id}/targets
- GET    /api/operations/targets/sessions
"""
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ---- 任务列表 ----

def test_list_tasks_returns_seed_data():
    """GET /api/operations/tasks → 200，返回种子 4 个任务。"""
    resp = client.get("/api/operations/tasks")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 4


def test_list_tasks_has_required_fields():
    """列表每项包含 id/name/task_type/enabled/target_count 等字段。"""
    resp = client.get("/api/operations/tasks")
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        assert "id" in item
        assert "name" in item
        assert "task_type" in item
        assert "enabled" in item
        assert "target_count" in item
        assert "run_status" in item
        assert "content_blocks" in item


def test_list_tasks_filter_by_type():
    """GET /api/operations/tasks?type=群发任务 → 仅群发任务。"""
    resp = client.get("/api/operations/tasks", params={"type": "群发任务"})
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["task_type"] == "群发任务" for item in items)
    assert len(items) >= 1


def test_list_tasks_filter_by_enabled():
    """GET /api/operations/tasks?enabled=enabled → 仅启用。"""
    resp = client.get("/api/operations/tasks", params={"enabled": "enabled"})
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["enabled"] is True for item in items)
    assert len(items) >= 1


def test_list_tasks_filter_by_disabled():
    """GET /api/operations/tasks?enabled=disabled → 仅禁用。"""
    resp = client.get("/api/operations/tasks", params={"enabled": "disabled"})
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["enabled"] is False for item in items)


def test_list_tasks_search_by_name():
    """GET /api/operations/tasks?search=早安 → 模糊匹配。"""
    resp = client.get("/api/operations/tasks", params={"search": "早安"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert any("早安" in item["name"] for item in items)


def test_list_tasks_sort_by_created_at():
    """GET /api/operations/tasks?sortBy=created_at&sortOrder=ASC → 升序。"""
    resp = client.get(
        "/api/operations/tasks",
        params={"sortBy": "created_at", "sortOrder": "ASC"},
    )
    assert resp.status_code == 200
    items = resp.json()
    timestamps = [item["created_at"] for item in items]
    assert timestamps == sorted(timestamps)


# ---- 创建任务 ----

def test_create_task_with_targets():
    """POST /api/operations/tasks 创建任务 + targets → 201。"""
    payload = {
        "name": "测试创建任务",
        "task_type": "群发任务",
        "channel_type": "企业微信",
        "session_type": "群聊",
        "content_blocks": [{"type": "text", "content": "测试内容"}],
        "hosting_action": "保持不变",
        "run_frequency": "一次",
        "run_time": "2026-08-01 10:00:00",
        "effective_start": "2026-07-20 00:00:00",
        "effective_end": "2026-08-31 23:59:59",
        "cron_expression": "",
        "targets": [
            {"session_id": "ses-drjack", "target_type": "static"},
            {"session_id": "ses-tongtian", "target_type": "static"},
        ],
    }
    resp = client.post("/api/operations/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    task = resp.json()
    assert task["name"] == "测试创建任务"
    assert task["task_type"] == "群发任务"
    assert len(task["content_blocks"]) == 1
    assert task["content_blocks"][0]["content"] == "测试内容"
    assert task["enabled"] is True
    assert task["run_status"] == "未运行"
    # 返回的 target_count 应反映创建时传入的 targets 数量
    assert task["target_count"] == 2


def test_create_task_minimal_fields():
    """POST /api/operations/tasks 仅必填字段 → 201，默认值填充。"""
    payload = {"name": "最小化任务"}
    resp = client.post("/api/operations/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    task = resp.json()
    assert task["name"] == "最小化任务"
    assert task["task_type"] == "群发任务"
    assert task["channel_type"] == "企业微信"
    assert task["session_type"] == "群聊"
    assert task["enabled"] is True
    assert task["run_status"] == "未运行"
    assert task["target_count"] == 0


# ---- 任务详情 ----

def test_get_task_detail():
    """GET /api/operations/tasks/opt-1 → 200，含 targets。"""
    resp = client.get("/api/operations/tasks/opt-1")
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["id"] == "opt-1"
    assert "targets" in task
    assert isinstance(task["targets"], list)
    assert len(task["targets"]) >= 1
    # 每个 target 应有 session 信息
    for target in task["targets"]:
        assert "id" in target
        assert "session_id" in target
        assert "session_name" in target


def test_get_task_not_found():
    """GET /api/operations/tasks/nonexistent → 404。"""
    resp = client.get("/api/operations/tasks/nonexistent")
    assert resp.status_code == 404


# ---- 更新任务 ----

def test_update_task_fields():
    """PUT /api/operations/tasks/opt-2 → 200，部分字段更新。"""
    payload = {"name": "改名后的任务", "run_frequency": "每天"}
    resp = client.put("/api/operations/tasks/opt-2", json=payload)
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["name"] == "改名后的任务"
    assert task["run_frequency"] == "每天"


def test_update_task_not_found():
    """PUT /api/operations/tasks/nonexistent → 404。"""
    resp = client.put("/api/operations/tasks/nonexistent", json={"name": "x"})
    assert resp.status_code == 404


# ---- 启停切换 ----

def test_toggle_task_enabled_to_disabled():
    """PATCH /api/operations/tasks/opt-3/toggle → 200，enabled 翻转。"""
    # 先获取当前状态
    before = client.get("/api/operations/tasks/opt-3")
    before_enabled = before.json()["enabled"]

    resp = client.patch("/api/operations/tasks/opt-3/toggle")
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["enabled"] is not before_enabled

    # 再翻转回来
    resp2 = client.patch("/api/operations/tasks/opt-3/toggle")
    assert resp2.status_code == 200
    assert resp2.json()["enabled"] is before_enabled


def test_toggle_task_not_found():
    """PATCH /api/operations/tasks/nonexistent/toggle → 404。"""
    resp = client.patch("/api/operations/tasks/nonexistent/toggle")
    assert resp.status_code == 404


# ---- 删除任务 ----

def test_delete_task():
    """DELETE /api/operations/tasks/{id} → 200，确认已删除。"""
    # 先创建一个临时任务
    create_resp = client.post("/api/operations/tasks", json={"name": "待删除任务"})
    task_id = create_resp.json()["id"]

    # 删除
    resp = client.delete(f"/api/operations/tasks/{task_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] is True

    # 再次 GET 应 404
    get_resp = client.get(f"/api/operations/tasks/{task_id}")
    assert get_resp.status_code == 404


def test_delete_task_not_found():
    """DELETE /api/operations/tasks/nonexistent → 404。"""
    resp = client.delete("/api/operations/tasks/nonexistent")
    assert resp.status_code == 404


# ---- 运营对象列表 ----

def test_list_targets():
    """GET /api/operations/tasks/opt-1/targets → 200。"""
    resp = client.get("/api/operations/tasks/opt-1/targets")
    assert resp.status_code == 200, resp.text
    targets = resp.json()
    assert isinstance(targets, list)
    assert len(targets) >= 1
    for t in targets:
        assert t["task_id"] == "opt-1"
        assert "session_id" in t
        assert "session_name" in t


def test_list_targets_task_not_found():
    """GET /api/operations/tasks/nonexistent/targets → 404。"""
    resp = client.get("/api/operations/tasks/nonexistent/targets")
    assert resp.status_code == 404


# ---- 设置运营对象 ----

def test_set_targets():
    """PUT /api/operations/tasks/opt-4/targets → 200，全量替换。"""
    payload = {
        "targets": [
            {"session_id": "ses-fushou", "target_type": "static"},
        ],
    }
    resp = client.put("/api/operations/tasks/opt-4/targets", json=payload)
    assert resp.status_code == 200, resp.text
    targets = resp.json()
    assert len(targets) == 1
    assert targets[0]["session_id"] == "ses-fushou"

    # 恢复原始 targets
    restore = {
        "targets": [
            {"session_id": "ses-drjack", "target_type": "static"},
            {"session_id": "ses-tongtian", "target_type": "static"},
        ],
    }
    client.put("/api/operations/tasks/opt-4/targets", json=restore)


def test_set_targets_task_not_found():
    """PUT /api/operations/tasks/nonexistent/targets → 404。"""
    resp = client.put(
        "/api/operations/tasks/nonexistent/targets",
        json={"targets": []},
    )
    assert resp.status_code == 404


# ---- 可用会话列表 ----

def test_list_target_sessions():
    """GET /api/operations/targets/sessions → 200。"""
    resp = client.get("/api/operations/targets/sessions")
    assert resp.status_code == 200, resp.text
    sessions = resp.json()
    assert isinstance(sessions, list)
    for s in sessions:
        assert "id" in s
        assert "name" in s
        assert "selected" in s


def test_list_target_sessions_with_task_id():
    """GET /api/operations/targets/sessions?task_id=opt-1 → 标记已选。"""
    resp = client.get(
        "/api/operations/targets/sessions", params={"task_id": "opt-1"}
    )
    assert resp.status_code == 200
    sessions = resp.json()
    selected = [s for s in sessions if s["selected"] is True]
    # opt-1 种子有 3 个 targets
    assert len(selected) == 3


def test_list_target_sessions_filter_by_type():
    """GET /api/operations/targets/sessions?session_type=群聊 → 仅群聊。"""
    resp = client.get(
        "/api/operations/targets/sessions", params={"session_type": "群聊"}
    )
    assert resp.status_code == 200
    sessions = resp.json()
    for s in sessions:
        assert s["session_type"] == "群聊"


def test_list_target_sessions_search():
    """GET /api/operations/targets/sessions?search=通 → 模糊搜索。"""
    resp = client.get(
        "/api/operations/targets/sessions", params={"search": "通"}
    )
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) >= 1


# ---- 新增：运营对象选择器 v2 ----

def test_list_target_sessions_v2_single():
    """GET /api/operations/target-sessions?sessionType=single → 200，返回好友 members。"""
    resp = client.get("/api/operations/target-sessions", params={"sessionType": "single"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert isinstance(data["items"], list)
    for item in data["items"]:
        assert "id" in item
        assert "name" in item
        assert "account_name" in item
        assert "hosted_status" in item
        assert "add_time" in item


def test_list_target_sessions_v2_group():
    """GET /api/operations/target-sessions?sessionType=group → 200。"""
    resp = client.get("/api/operations/target-sessions", params={"sessionType": "group"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data["items"], list)


def test_list_target_sessions_v2_with_channel():
    """GET /api/operations/target-sessions?channel=企业微信&sessionType=single → 200。"""
    resp = client.get(
        "/api/operations/target-sessions",
        params={"channel": "企业微信", "sessionType": "single"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data["items"], list)


def test_list_target_sessions_v2_with_keyword():
    """GET /api/operations/target-sessions?keyword=通 → 模糊搜索返回匹配项。"""
    resp = client.get(
        "/api/operations/target-sessions",
        params={"sessionType": "single", "keyword": "通"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["items"]) >= 1
    # 结果中应包含名称含"通"的会话
    names = [item["name"] for item in data["items"]]
    assert any("通" in name for name in names)


def test_list_target_sessions_v2_pagination():
    """GET /api/operations/target-sessions?page=1&pageSize=2 → 分页正常。"""
    resp = client.get(
        "/api/operations/target-sessions",
        params={"sessionType": "single", "page": 1, "pageSize": 2},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2


def test_list_hosting_accounts():
    """GET /api/operations/hosting-accounts → 200，返回账号列表。"""
    resp = client.get("/api/operations/hosting-accounts")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert "id" in item
        assert "account_name" in item
        assert "display_name" in item


def test_list_hosting_accounts_with_channel():
    """GET /api/operations/hosting-accounts?channel=企业微信 → 200。"""
    resp = client.get("/api/operations/hosting-accounts", params={"channel": "企业微信"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)


def test_list_hosting_bots():
    """GET /api/operations/hosting-bots → 200，返回机器人列表。"""
    resp = client.get("/api/operations/hosting-bots")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert "id" in item
        assert "name" in item


def test_list_tags():
    """GET /api/operations/tags → 200，返回标签列表（含分组）。"""
    resp = client.get("/api/operations/tags")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert "id" in item
        assert "name" in item
        assert "group_name" in item


def test_list_tag_groups():
    """GET /api/operations/tag-groups → 200，返回标签分组。"""
    resp = client.get("/api/operations/tag-groups")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert "id" in item
        assert "name" in item


# ---- AI Cron 生成 ----

def test_ai_cron_generates_expression():
    """POST /api/operations/ai-cron → 200，返回 cron 表达式。"""
    resp = client.post("/api/operations/ai-cron", json={"prompt": "每周一到周五早上9点"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "cron" in data
    assert isinstance(data["cron"], str)
    assert len(data["cron"]) > 0


def test_ai_cron_empty_prompt():
    """POST /api/operations/ai-cron 空 prompt → 400。"""
    resp = client.post("/api/operations/ai-cron", json={"prompt": ""})
    assert resp.status_code == 400, resp.text


# ---- 朋友圈渠道账号 ----

def test_list_channel_accounts_wecom():
    """GET /api/operations/channel-accounts?channel=wecom → 返回 2 个 online 账号。"""
    resp = client.get("/api/operations/channel-accounts", params={"channel": "wecom"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    for item in data:
        assert "id" in item
        assert "account_name" in item
        assert "channel_type" in item
        assert "status" in item
        assert "display_name" in item
        assert item["channel_type"] == "wecom"
        assert item["status"] == "online"


def test_list_channel_accounts_wechat():
    """GET /api/operations/channel-accounts?channel=wechat → 返回 1 个 offline 账号。"""
    resp = client.get("/api/operations/channel-accounts", params={"channel": "wechat"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "acc-fushou"
    assert data[0]["status"] == "offline"
    assert data[0]["channel_type"] == "wechat"

"""Fix 4 最小回归测试：SendTextMsg 返回 int 型 msg_id/server_id 时必须强制转 str。

真实 iPad 协议服务 SendTextMsg 返回的 `msg_id` / `server_id` 为整数，而
`SendTextResultDTO` 字段为 str 类型（Pydantic v2 不自动把 int/None 转 str），
不强制转 str 会在路由响应阶段触发 ResponseValidationError → 500（见任务 Issue #4）。

运行：
    cd project/backend && .venv/bin/python -m pytest tests/test_send_text_coerce.py -q
"""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

from app import ipad_client, ipad_sync


class _FakeRepo:
    """最小化 FakeRepo：仅满足 send_text_message 的目标解析路径。"""

    def get_account_by_id(self, account_id: str) -> dict:
        # 返回已托管 iPad 的账号，提供 ipadUuid 供 _resolve_target / 发送使用。
        return {"ipadUuid": "fake-uuid-0001"}

    def get_contact_by_id(self, contact_id: str) -> dict:
        # target_type=contact 时反查 user_id；非空即通过校验。
        return {"user_id": "fake-user-0001"}


class TestSendTextCoerce(unittest.TestCase):
    """验证 int 型回参被强制转 str，且结果可 JSON 序列化（不触发 ResponseValidationError）。"""

    def test_int_ids_coerced_to_str_and_serializable(self):
        with mock.patch.object(ipad_sync, "get_backend", return_value=object()), \
             mock.patch.object(ipad_sync, "ChannelMgmtRepository", return_value=_FakeRepo()), \
             mock.patch.object(
                 ipad_client, "send_text_msg",
                 return_value={"msg_id": 12345, "server_id": 67890},
             ):
            res = ipad_sync.send_text_message("acc-1", "contact", "cid-1", "hi")

        # 关键断言：字段必须是 str（而非 int），否则 DTO 校验失败 → 500。
        self.assertIsInstance(res["msgId"], str)
        self.assertIsInstance(res["serverId"], str)
        self.assertEqual(res["msgId"], "12345")
        self.assertEqual(res["serverId"], "67890")
        self.assertTrue(res["ok"])

        # 可序列化：证明不会在路由响应阶段触发 ResponseValidationError。
        payload = json.dumps(res)
        self.assertIsInstance(payload, str)
        self.assertIn('"msgId": "12345"', payload)


if __name__ == "__main__":
    unittest.main()

"""GetRunClientInfo 响应格式兼容性单元测试（mock 驱动，不依赖真实服务）。

验证 `get_run_client_info` 能正确解析协议文档定义的两种返回格式：
1) `data` 直接含字段：`{"data": {"loginType": 2, "userInfo": {...}, "longLinkState": "CONNECTED"}}`
2) `data.runClientList` 数组（多账号托管场景）：
   `{"data": {"runClientList": [{"loginType": 2, "userInfo": {...}, "longLinkState": "CONNECTED"}]}}`

两种格式都应归一化为 `{"loginType": 2, "userInfo": {...}, "longLinkState": "CONNECTED"}`；
并验证 snake_case 字段兼容与缺省安全值。

运行（在 project/backend 下）：

    .venv/bin/python -m pytest tests/test_ipad_client_compat.py -v
"""
from __future__ import annotations

from unittest.mock import patch

from app import ipad_client


def test_format1_direct_fields():
    """格式1：data 直接含 loginType/userInfo/longLinkState。"""
    raw = {
        "errcode": 0,
        "data": {
            "loginType": 2,
            "userInfo": {"nickname": "张三", "userId": "u123"},
            "longLinkState": "CONNECTED",
        },
    }
    with patch.object(ipad_client, "_post", return_value=raw):
        info = ipad_client.get_run_client_info("uuid-1")
    assert info == {
        "loginType": 2,
        "userInfo": {"nickname": "张三", "userId": "u123"},
        "longLinkState": "CONNECTED",
    }


def test_format2_run_client_list():
    """格式2：data.runClientList 数组，取第一个元素。"""
    raw = {
        "errcode": 0,
        "data": {
            "runClientList": [
                {
                    "loginType": 2,
                    "userInfo": {"nickname": "李四", "userId": "u456"},
                    "longLinkState": "CONNECTED",
                }
            ]
        },
    }
    with patch.object(ipad_client, "_post", return_value=raw):
        info = ipad_client.get_run_client_info("uuid-2")
    assert info == {
        "loginType": 2,
        "userInfo": {"nickname": "李四", "userId": "u456"},
        "longLinkState": "CONNECTED",
    }


def test_format2_picks_first_nonempty():
    """格式2：数组含多个元素（含空 dict），取第一个非空元素。"""
    raw = {
        "errcode": 0,
        "data": {
            "runClientList": [
                {},
                {
                    "loginType": 2,
                    "userInfo": {"nickname": "王五"},
                    "longLinkState": "CONNECTED",
                },
            ]
        },
    }
    with patch.object(ipad_client, "_post", return_value=raw):
        info = ipad_client.get_run_client_info("uuid-3")
    assert info["loginType"] == 2
    assert info["userInfo"] == {"nickname": "王五"}
    assert info["longLinkState"] == "CONNECTED"


def test_snake_case_field_compat():
    """兼容 snake_case 字段：login_type / user_info / long_link_state。"""
    raw = {
        "errcode": 0,
        "data": {
            "login_type": 2,
            "user_info": {"nickname": "赵六"},
            "long_link_state": "CONNECTED",
        },
    }
    with patch.object(ipad_client, "_post", return_value=raw):
        info = ipad_client.get_run_client_info("uuid-4")
    assert info == {
        "loginType": 2,
        "userInfo": {"nickname": "赵六"},
        "longLinkState": "CONNECTED",
    }


def test_default_safe_values():
    """缺省安全值：loginType=1、longLinkState=CONNECTING、userInfo=None。

    当 data 为空对象时（既无直接字段也无 runClientList），不应误判为登录态，
    loginType 必须保持默认 1，longLinkState 保持默认 CONNECTING。
    """
    raw = {"errcode": 0, "data": {}}
    with patch.object(ipad_client, "_post", return_value=raw):
        info = ipad_client.get_run_client_info("uuid-5")
    assert info == {
        "loginType": 1,
        "userInfo": None,
        "longLinkState": "CONNECTING",
    }

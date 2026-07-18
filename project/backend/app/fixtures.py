"""静态演示数据（非持久化部分）。

这些是 MVP 阶段前端展示所需、但尚未落库的只读数据。
保持与原 main.py 完全一致，确保 API contract 不变。
后续接入真实会话/客户/项目数据时，这里逐步替换为 Repository 查询。
"""
from __future__ import annotations


def dashboard_static() -> dict:
    """dashboard 中非 DB 部分（stats / sessions / customers / workflows）。"""
    return {
        "stats": {
            "activeProjects": 4,
            "channelAccounts": 28,
            "aiSessions": 1264,
            "conversionRate": "18.7%",
        },
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


def workflows_static() -> list[dict]:
    return dashboard_static()["workflows"]


def sessions_static() -> list[dict]:
    return dashboard_static()["sessions"]


def conversation_messages_static(conversation_id: str, page: int = 1) -> dict:
    messages = [
        {"id": "m-1", "senderType": "customer", "content": "标准版支持多少个账号？"},
        {"id": "m-2", "senderType": "ai", "content": "标准版适合小团队使用，支持基础渠道托管和知识库问答。"},
        {"id": "m-3", "senderType": "system", "content": "已完成需求分析、知识检索、表达控制。"},
    ]
    if page > 1:
        messages.insert(0, {"id": "m-0", "senderType": "customer", "content": "我想先了解价格和部署周期。"})
    return {"conversationId": conversation_id, "page": page, "items": messages, "hasMore": page < 2}

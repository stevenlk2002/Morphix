"""表情消息渲染/落库 —— 测试套件（Bug：表情消息在聊天框显示成 `[表情]` 裸文本）。

根因拆解：
1. 协议对表情图片的字段命名未文档化且线上多变（url / cdnurl / picUrl / emotionUrl …），
   `_extract_callback_messages` 原先只认 9 个候选键，漏掉图片链接 → `media_url=''`
   → `content_type` 判定回落 text → 前端只能渲染后端兜底文案 `[表情]`；
2. 表情尺寸/类型（emotionType/width/height）已有抽取函数 `_emotion_media_meta`，
   但从未接入落库路径，`media_meta` 恒为 `{}`；
3. 「文字表情」（`[强]`/`[微笑]`）本就是纯文本编码，后端**不做**替换（保证数据保真），
   由前端 `src/pages/Channels/shared/wecomEmoji.ts` 在渲染期转 Unicode。
   本文件只钉死后端侧不变式：文本原样保留、结构占位文案不变。

覆盖：
1. 协议 104（GIF 表情消息接收）携带 `url` → media_url 非空 + content_type='image'
   + media_meta 含 emotionType/width/height；
2. 各类未在旧候选列表中的图片字段（cdnurl / picUrl / imgUrl / thumb_url …）均可提取；
3. 显式字段全缺失时，兜底扫描消息体（含一层嵌套）取企业微信 CDN 图片链接；
4. 兜底扫描不误伤：非表情 msgType、非图片 URL 一律不提取；
5. `_render_message_content` 对 104 / 2001 / 101 / 14 的文本占位保持不变；
6. 文字表情码 `[强][强]` / `这个AI发的[微笑]` 后端原样落库，不被替换/清洗。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_emoji_render.py -q
"""
from __future__ import annotations

import os

os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest

from app import ipad_sync


# --- 协议真实样本（IPad协议API文档「2. GIF表情消息接收」） -------------------
EMOTION_104_PAYLOAD: dict = {
    "url": "https://wework.qpic.cn/wwpic3az/xxx",
    "emotionType": "EMOTION_DYNAMIC",
    "width": 108,
    "height": 108,
    "msgType": 104,
    "sender": "7881302555913738",
    "receiver": "1688850473951280",
    "is_room": 0,
    "server_id": "9001",
    "referid": 0,
    "send_time": 1730000000,
}


def _extract_one(payload: dict) -> dict:
    """跑一遍归一化并取出唯一一条消息（payload 为平铺单条消息体）。"""
    out = ipad_sync._extract_callback_messages(dict(payload), "message")
    assert len(out) == 1, f"期望归一化出 1 条消息，实际 {len(out)} 条"
    return out[0]


# ---------------------------------------------------------------------------
# 1. 协议 104 表情：URL 提取 + content_type + media_meta
# ---------------------------------------------------------------------------
class TestEmotion104Payload:
    def test_media_url_extracted(self) -> None:
        msg = _extract_one(EMOTION_104_PAYLOAD)
        assert msg["media_url"] == "https://wework.qpic.cn/wwpic3az/xxx"

    def test_content_type_is_image(self) -> None:
        # 无 content 文本 + 有媒体 URL + 无文件名 → 图片气泡（前端走 <img> 分支）。
        msg = _extract_one(EMOTION_104_PAYLOAD)
        assert msg["content_type"] == "image"

    def test_media_meta_filled_from_emotion_fields(self) -> None:
        msg = _extract_one(EMOTION_104_PAYLOAD)
        assert msg["media_meta"] == {
            "emotionType": "EMOTION_DYNAMIC",
            "width": 108,
            "height": 108,
        }

    def test_msg_type_and_content_placeholder(self) -> None:
        msg = _extract_one(EMOTION_104_PAYLOAD)
        assert msg["msg_type"] == 104
        # 有图时前端优先用 image 分支，文本仍保留可读兜底。
        assert msg["content"] == "[动画表情]"

    def test_static_emotion_summary(self) -> None:
        payload = {**EMOTION_104_PAYLOAD, "emotionType": "EMOTION_STATIC"}
        msg = _extract_one(payload)
        assert msg["media_meta"]["emotionType"] == "EMOTION_STATIC"
        assert msg["media_url"] == "https://wework.qpic.cn/wwpic3az/xxx"


# ---------------------------------------------------------------------------
# 2. 新增 URL 候选字段（回归前这些字段全部提取不到）
# ---------------------------------------------------------------------------
class TestExtendedMediaUrlKeys:
    @pytest.mark.parametrize(
        "key",
        [
            "img_url",
            "image_url",
            "pic_url",
            "thumb_url",
            "emoji_url",
            "cdnurl",
            "cdnUrl",
            "picUrl",
            "imageUrl",
            "imgUrl",
        ],
    )
    def test_each_new_key_is_recognised(self, key: str) -> None:
        payload = {
            key: "https://wework.qpic.cn/wwpic3az/emoji-001.gif",
            "emotionType": "EMOTION_DYNAMIC",
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9002",
        }
        msg = _extract_one(payload)
        assert msg["media_url"] == "https://wework.qpic.cn/wwpic3az/emoji-001.gif"
        assert msg["content_type"] == "image"

    def test_legacy_keys_still_work(self) -> None:
        """旧候选键不得回归失效。"""
        for key in ("media_url", "mediaUrl", "url", "emotionUrl", "emotion_url"):
            payload = {
                key: "https://wework.qpic.cn/wwpic3az/legacy.gif",
                "msgType": 104,
                "sender": "7881302555913738",
                "server_id": "9003",
            }
            assert _extract_one(payload)["media_url"] == (
                "https://wework.qpic.cn/wwpic3az/legacy.gif"
            ), f"旧候选键 {key} 提取失败"


# ---------------------------------------------------------------------------
# 3. 兜底扫描：显式候选字段全缺失
# ---------------------------------------------------------------------------
class TestImageUrlFallbackScan:
    def test_scan_unknown_top_level_field(self) -> None:
        payload = {
            "someUndocumentedField": "https://wework.qpic.cn/wwpic3az/unknown-key.gif",
            "emotionType": "EMOTION_DYNAMIC",
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9004",
        }
        msg = _extract_one(payload)
        assert msg["media_url"] == "https://wework.qpic.cn/wwpic3az/unknown-key.gif"
        assert msg["content_type"] == "image"

    def test_scan_nested_dict(self) -> None:
        payload = {
            "emotion": {"cdn": "https://mmbiz.qlogo.cn/emoticon/abc123"},
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9005",
        }
        assert _extract_one(payload)["media_url"] == "https://mmbiz.qlogo.cn/emoticon/abc123"

    def test_scan_nested_list(self) -> None:
        payload = {
            "candidates": ["not-a-url", "https://cdn.example.com/a/b/emo.png"],
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9006",
        }
        assert _extract_one(payload)["media_url"] == "https://cdn.example.com/a/b/emo.png"

    def test_scan_matches_by_extension(self) -> None:
        payload = {
            "anything": "https://cdn.example.com/x/y.webp?token=1",
            "msgType": 2001,
            "sender": "7881302555913738",
            "server_id": "9007",
        }
        assert _extract_one(payload)["media_url"] == "https://cdn.example.com/x/y.webp?token=1"

    def test_scan_skipped_for_non_emotion_msg_type(self) -> None:
        """普通文本消息不做兜底扫描，避免把正文里的链接误当媒体。"""
        payload = {
            "content": "参考 https://cdn.example.com/a.png 这张图",
            "msgType": 2,
            "sender": "7881302555913738",
            "server_id": "9008",
        }
        msg = _extract_one(payload)
        assert msg["media_url"] == ""
        assert msg["content_type"] == "text"

    def test_scan_ignores_non_image_url(self) -> None:
        payload = {
            "detail": "https://example.com/api/v1/query",
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9009",
        }
        assert _extract_one(payload)["media_url"] == ""

    def test_scan_ignores_non_http_value(self) -> None:
        payload = {
            "note": "emotion.gif",
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9010",
        }
        assert _extract_one(payload)["media_url"] == ""


class TestLooksLikeImageUrl:
    @pytest.mark.parametrize(
        "value",
        [
            "https://wework.qpic.cn/wwpic3az/xxx",
            "https://mmbiz.qlogo.cn/emoticon/abc",
            "http://cdn.example.com/a.JPG",
            "https://cdn.example.com/a.gif?x=1",
        ],
    )
    def test_positive(self, value: str) -> None:
        assert ipad_sync._looks_like_image_url(value) is True

    @pytest.mark.parametrize(
        "value",
        ["", "   ", "a.png", "ftp://host/a.png", "https://example.com/api", 123, None, {"a": 1}],
    )
    def test_negative(self, value: object) -> None:
        assert ipad_sync._looks_like_image_url(value) is False


# ---------------------------------------------------------------------------
# 4. 文本占位不变（前端渲染层依赖这些常量文案）
# ---------------------------------------------------------------------------
class TestRenderMessageContentPlaceholders:
    def test_104_returns_dynamic_emotion(self) -> None:
        assert ipad_sync._render_message_content(EMOTION_104_PAYLOAD, 104) == "[动画表情]"

    def test_image_types_return_image_placeholder(self) -> None:
        assert ipad_sync._render_message_content({}, 101) == "[图片]"
        assert ipad_sync._render_message_content({}, 14) == "[图片]"

    def test_2001_is_control_event_and_yields_empty(self) -> None:
        """2001 = MarkAsRead 已读回执，无聊天内容，返回空串由上游拦截。

        历史实现把 2001 当表情导致聊天框刷出成片 `[表情]`（DB 中仍留有旧数据），
        这里钉死当前语义，防止回退。
        """
        assert 2001 in ipad_sync.CONTROL_EVENT_MSG_TYPES
        assert ipad_sync._render_message_content(EMOTION_104_PAYLOAD, 2001) == ""

    def test_emotion_summary_branches(self) -> None:
        assert ipad_sync._emotion_summary({"emotionType": "EMOTION_STATIC"}) == "[表情]"
        assert ipad_sync._emotion_summary({"emotionType": "EMOTION_DYNAMIC"}) == "[动画表情]"
        assert ipad_sync._emotion_summary({}) == "[动画表情]"


# ---------------------------------------------------------------------------
# 5. 文字表情码：后端原样保真，替换只发生在前端渲染层
# ---------------------------------------------------------------------------
class TestTextEmojiCodePassthrough:
    @pytest.mark.parametrize(
        "text",
        ["[强][强][强][强]", "这个AI发的[微笑]", "[握手]辛苦了[玫瑰]"],
    )
    def test_text_emoji_codes_are_preserved(self, text: str) -> None:
        payload = {
            "content": text,
            "msgType": 2,
            "sender": "7881302555913738",
            "server_id": "9100",
        }
        msg = _extract_one(payload)
        assert msg["content"] == text
        assert msg["content_type"] == "text"
        assert msg["media_url"] == ""

    def test_text_with_emotion_field_keeps_text_content_type(self) -> None:
        """携带表情特征字段但同时有正文时，仍是文本消息（不吞正文）。"""
        payload = {
            "content": "收到[强]",
            "emotionType": "EMOTION_STATIC",
            "msgType": 2,
            "sender": "7881302555913738",
            "server_id": "9101",
        }
        msg = _extract_one(payload)
        assert msg["content"] == "收到[强]"
        assert msg["content_type"] == "text"


# ---------------------------------------------------------------------------
# 6. media_meta 兜底：非表情消息不得被污染
# ---------------------------------------------------------------------------
class TestMediaMetaMerge:
    def test_explicit_media_meta_preserved(self) -> None:
        payload = {
            "media_meta": {"size": 1024, "md5": "abc"},
            "url": "https://wework.qpic.cn/wwpic3az/x.gif",
            "emotionType": "EMOTION_DYNAMIC",
            "width": 108,
            "height": 108,
            "msgType": 104,
            "sender": "7881302555913738",
            "server_id": "9200",
        }
        meta = _extract_one(payload)["media_meta"]
        assert meta["size"] == 1024
        assert meta["md5"] == "abc"
        assert meta["emotionType"] == "EMOTION_DYNAMIC"
        assert meta["width"] == 108

    def test_plain_text_media_meta_stays_empty(self) -> None:
        payload = {
            "content": "你好",
            "msgType": 2,
            "sender": "7881302555913738",
            "server_id": "9201",
        }
        assert _extract_one(payload)["media_meta"] == {}

    def test_malformed_media_meta_coerced_to_dict(self) -> None:
        payload = {
            "media_meta": "not-a-dict",
            "content": "你好",
            "msgType": 2,
            "sender": "7881302555913738",
            "server_id": "9202",
        }
        assert _extract_one(payload)["media_meta"] == {}

"""群二维码链路边界与失败路径回归测试（QA 独立补充）。

覆盖工程师原测试未触达的失败路径：
1. `_sniff_content_type` 的空/极短/未知/容器格式字节边界；
2. 上游静态服务不可达、超时、非 2xx 时的降级行为；
3. 协议返回 `errcode != 0`（HTTP 200 + 业务失败）时的异常类型与路由映射；
4. 群归属校验缺失导致的越权取图（`room_id` 被 `_to_int_id` 静默降级为 0）。

对应 BugFix：删除 `_rewrite_qrcode_host()`，透传协议原始 URL。
"""

from __future__ import annotations

import httpx
import pytest

from app import ipad_client, ipad_sync


# ---------------------------------------------------------------------------
# 1. _sniff_content_type 边界
# ---------------------------------------------------------------------------
class TestSniffContentType:
    """魔数嗅探不得因短字节抛 IndexError，且需正确识别常见格式。"""

    @pytest.mark.parametrize(
        "data",
        [
            b"",  # 空字节
            b"\x89",  # 1 字节
            b"\x89P",  # 2 字节
            b"\x89PN",  # 3 字节（PNG 魔数差 1 字节）
            b"\xff",  # JPEG 魔数差 1 字节
            b"GIF",  # GIF 魔数差 1 字节
        ],
    )
    def test_short_bytes_no_exception(self, data: bytes):
        """极短/空字节不得抛异常，必须返回一个字符串。"""
        result = ipad_sync._sniff_content_type(data)
        assert isinstance(result, str) and result

    def test_png_detected(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        assert ipad_sync._sniff_content_type(png) == "image/png"

    def test_jpeg_detected(self):
        jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 32
        assert ipad_sync._sniff_content_type(jpeg) == "image/jpeg"

    def test_gif_detected(self):
        gif = b"GIF89a" + b"\x00" * 32
        assert ipad_sync._sniff_content_type(gif) == "image/gif"

    def test_unknown_format_falls_back(self):
        """未知格式回落为 image/jpeg（当前实现的既定行为）。"""
        assert ipad_sync._sniff_content_type(b"%PDF-1.7" + b"\x00" * 32) == "image/jpeg"

    def test_html_error_page_not_reported_as_image(self):
        """上游把错误页当图片返回时，嗅探结果不应声称是 PNG。

        当前实现会回落成 image/jpeg（仍是图片类型），此断言仅锁定
        『不会被误判为 PNG』这一最低保证。
        """
        html = b"<!DOCTYPE html><html><body>502 Bad Gateway</body></html>"
        assert ipad_sync._sniff_content_type(html) != "image/png"

    def test_webp_container_detected(self):
        """[缺陷 #3 已修复] WebP 是 RIFF 容器（'RIFF....WEBP'），应判为 image/webp。

        修复前 `RIFF` 与 `GIF8` 同处一个分支导致 WebP 被误判为 image/gif，
        且其后 `data[:4] == b"WEBP"` 分支永远不可达（死代码，已删除）。
        """
        webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16
        assert ipad_sync._sniff_content_type(webp) == "image/webp"

    def test_riff_without_webp_marker_not_webp(self):
        """RIFF 容器但非 WebP（如 WAV/AVI）不得被判为 image/webp。"""
        wav = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 16
        assert ipad_sync._sniff_content_type(wav) != "image/webp"

    def test_truncated_riff_no_exception(self):
        """RIFF 头但长度不足 12 字节时不得抛 IndexError。"""
        assert isinstance(ipad_sync._sniff_content_type(b"RIFF" + b"\x00" * 4), str)


# ---------------------------------------------------------------------------
# 2. 下载失败路径
# ---------------------------------------------------------------------------
class TestDownloadFailurePaths:
    """网络异常必须转成 IPadSyncError（路由映射 502），不得裸抛。"""

    def test_connect_error_becomes_sync_error(self, monkeypatch):
        def _boom(self, url, **kw):
            raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr(httpx.Client, "get", _boom)
        with pytest.raises(ipad_sync.IPadSyncError) as ei:
            ipad_sync._download_qrcode_image("http://127.0.0.1:1/x.jpg")
        assert "下载群二维码失败" in str(ei.value)

    def test_timeout_becomes_sync_error(self, monkeypatch):
        def _timeout(self, url, **kw):
            raise httpx.ReadTimeout("timed out")

        monkeypatch.setattr(httpx.Client, "get", _timeout)
        with pytest.raises(ipad_sync.IPadSyncError) as ei:
            ipad_sync._download_qrcode_image("http://example.invalid/x.jpg")
        assert "下载群二维码失败" in str(ei.value)

    def test_http_404_becomes_sync_error_with_status(self, monkeypatch):
        def _404(self, url, **kw):
            req = httpx.Request("GET", url)
            return httpx.Response(404, request=req, content=b"not found")

        monkeypatch.setattr(httpx.Client, "get", _404)
        with pytest.raises(ipad_sync.IPadSyncError) as ei:
            ipad_sync._download_qrcode_image("http://x/y.jpg")
        assert "404" in str(ei.value)

    def test_empty_body_200_raises(self, monkeypatch):
        """[次要项已修复] 上游 200 但返回 0 字节时必须报错，不得把空图当成功回传。"""

        def _empty(self, url, **kw):
            req = httpx.Request("GET", url)
            return httpx.Response(200, request=req, content=b"")

        monkeypatch.setattr(httpx.Client, "get", _empty)
        with pytest.raises(ipad_sync.IPadSyncError) as ei:
            ipad_sync._download_qrcode_image("http://x/y.jpg")
        assert "空响应体" in str(ei.value)

    def test_no_proxy_env_used(self, monkeypatch):
        """httpx 必须禁用环境代理（trust_env=False），避免 launchd 注入代理。"""
        captured = {}
        orig_init = httpx.Client.__init__

        def _spy(self, *a, **kw):
            captured.update(kw)
            return orig_init(self, *a, **kw)

        monkeypatch.setattr(httpx.Client, "__init__", _spy)
        monkeypatch.setattr(
            httpx.Client,
            "get",
            lambda self, url, **kw: httpx.Response(
                200, request=httpx.Request("GET", url), content=b"\x89PNG\r\n\x1a\n"
            ),
        )
        ipad_sync._download_qrcode_image("http://x/y.jpg")
        assert captured.get("trust_env") is False
        assert captured.get("proxy") is None


# ---------------------------------------------------------------------------
# 3. 协议业务失败（HTTP 200 + errcode != 0）
# ---------------------------------------------------------------------------
class TestProtocolBusinessError:
    """协议 errcode != 0 时 ipad_client 抛 IPadProtocolError。

    [缺陷 #2 已修复] 该异常与 IPadSyncError 无继承关系，若不显式转换会穿透
    路由层的 `except IPadSyncError` 变成 HTTP 500 + 堆栈。
    现由 `_resolve_qrcode_urls` 统一转成 IPadSyncError。
    """

    def test_protocol_error_is_not_sync_error(self):
        """两个异常类无继承关系——这正是必须显式转换的原因。"""
        assert not issubclass(ipad_client.IPadProtocolError, ipad_sync.IPadSyncError)
        assert issubclass(ipad_client.IPadProtocolError, RuntimeError)
        assert issubclass(ipad_sync.IPadSyncError, ValueError)

    def test_errcode_500_converted_to_sync_error(self, monkeypatch):
        """协议 errcode=500（实例未登录）必须被转换成 IPadSyncError，不得裸抛。"""

        class _FakeRepo:
            def __init__(self, *a, **kw) -> None:
                pass

            def get_account_by_id(self, account_id: str) -> dict:
                return {"id": account_id, "ipadUuid": "fake-uuid"}

        monkeypatch.setattr(ipad_sync, "ChannelMgmtRepository", _FakeRepo)
        # 归属校验通过，让流程走到协议调用这一步
        monkeypatch.setattr(ipad_sync, "_resolve_group", lambda a, r: {"id": "g1"})
        monkeypatch.setattr(
            ipad_sync.ipad_client,
            "wx_room_invite",
            lambda uuid, room_id: (_ for _ in ()).throw(
                ipad_client.IPadProtocolError("iPad 协议业务错误 errcode=500: 实例未登录")
            ),
        )

        with pytest.raises(ipad_sync.IPadSyncError) as ei:
            ipad_sync._resolve_qrcode_urls("acc-x", "123")
        # 保留协议原始错误信息，便于排障
        assert "WxRoomInvite" in str(ei.value)
        assert "实例未登录" in str(ei.value)

    def test_protocol_error_never_escapes_as_runtime_error(self, monkeypatch):
        """回归护栏：IPadProtocolError 不得再从 `_resolve_qrcode_urls` 逃逸。"""

        class _FakeRepo:
            def __init__(self, *a, **kw) -> None:
                pass

            def get_account_by_id(self, account_id: str) -> dict:
                return {"id": account_id, "ipadUuid": "fake-uuid"}

        monkeypatch.setattr(ipad_sync, "ChannelMgmtRepository", _FakeRepo)
        monkeypatch.setattr(ipad_sync, "_resolve_group", lambda a, r: {"id": "g1"})
        monkeypatch.setattr(
            ipad_sync.ipad_client,
            "wx_room_invite",
            lambda uuid, room_id: (_ for _ in ()).throw(
                ipad_client.IPadProtocolError("boom")
            ),
        )
        try:
            ipad_sync._resolve_qrcode_urls("acc-x", "123")
        except ipad_sync.IPadSyncError:
            pass  # 预期
        except ipad_client.IPadProtocolError:
            pytest.fail("IPadProtocolError 逃逸，将导致路由层 HTTP 500")


# ---------------------------------------------------------------------------
# 4. 群归属校验缺失
# ---------------------------------------------------------------------------
class TestRoomOwnershipValidation:
    """[缺陷 #1 已修复] `_resolve_qrcode_urls` 必须做群归属校验。"""

    def test_to_int_id_silently_coerces_garbage_to_zero(self):
        """非法 room_id 被 `_to_int_id` 静默降级为 0——这正是必须前置归属校验的原因。

        `_to_int_id` 是通用函数（影响面大）故不改动；改为在二维码链路前置
        `_resolve_group`，使非法 room_id 根本走不到协议调用。
        """
        assert ipad_client._to_int_id("abc-not-a-number") == 0
        assert ipad_client._to_int_id(None) == 0
        assert ipad_client._to_int_id("") == 0

    def test_qrcode_path_enforces_group_ownership_check(self):
        """回归护栏：二维码链路必须与其余 5 处群操作一样调用 `_resolve_group`。"""
        import inspect

        src = inspect.getsource(ipad_sync._resolve_qrcode_urls)
        assert "_resolve_group" in src, "群归属校验被移除，越权取图漏洞将复现"

    def test_ownership_check_runs_before_protocol_call(self, monkeypatch):
        """归属校验必须发生在协议调用之前——不得先请求协议再校验。"""
        called: list[str] = []

        class _FakeRepo:
            def __init__(self, *a, **kw) -> None:
                pass

            def get_account_by_id(self, account_id: str) -> dict:
                return {"id": account_id, "ipadUuid": "fake-uuid"}

        def _reject_group(account_id: str, room_id: str):
            called.append("group_check")
            raise ipad_sync.IPadSyncError("群不存在")

        def _protocol(uuid: str, room_id):
            called.append("protocol")
            return {"qr_code_path": "http://leaked/other-group.jpg"}

        monkeypatch.setattr(ipad_sync, "ChannelMgmtRepository", _FakeRepo)
        monkeypatch.setattr(ipad_sync, "_resolve_group", _reject_group)
        monkeypatch.setattr(ipad_sync.ipad_client, "wx_room_invite", _protocol)

        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync._resolve_qrcode_urls("acc-x", "abc-not-a-number")

        # 协议一次都不能被调用，否则说明校验位置错了
        assert called == ["group_check"], f"协议不应被调用，实际调用序列={called}"

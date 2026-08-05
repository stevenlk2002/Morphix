"""llm_client unit tests — no real network, httpx mocked.

Verifies the OpenAI-compatible request shape, response parsing, and the
graceful fallback contract (no key / HTTP error -> used_llm=False, no raise).
"""
import sys

BASE = "/Users/stevenmac/Desktop/工作目录/Morphix/morphix-control"
sys.path.insert(0, BASE)

from app.services import llm_client


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_no_key_returns_fallback(monkeypatch):
    monkeypatch.delenv("MORPHIX_AI_API_KEY", raising=False)
    text, used, err = llm_client.try_chat("sys", "user")
    assert used is False
    assert text == ""
    assert err is not None


def test_chat_builds_openai_request(monkeypatch):
    captured = {}
    monkeypatch.setenv("MORPHIX_AI_API_KEY", "sk-test-123")
    monkeypatch.setenv("MORPHIX_AI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("MORPHIX_AI_MODEL", "deepseek-chat")

    payload = {"choices": [{"message": {"content": "  hi there  "}}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None, timeout=None):
            captured.update(url=url, json=json, headers=headers)
            return _FakeResponse(payload)

    monkeypatch.setattr(llm_client.httpx, "Client", FakeClient)

    text, used, err = llm_client.try_chat("SYS", "USR", temperature=0.3, timeout=10)

    assert used is True
    assert text == "hi there"  # trimmed
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test-123"
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["json"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert captured["json"]["messages"][1] == {"role": "user", "content": "USR"}
    assert captured["json"]["temperature"] == 0.3
    assert err is None


def test_chat_http_error_falls_back(monkeypatch):
    monkeypatch.setenv("MORPHIX_AI_API_KEY", "sk-test-123")

    class ErrClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr(llm_client.httpx, "Client", ErrClient)

    text, used, err = llm_client.try_chat("s", "u")
    assert used is False
    assert text == ""
    assert "RuntimeError" in (err or "")

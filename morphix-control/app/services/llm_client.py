"""LLM client — OpenAI-compatible chat completions.

Wired to DeepSeek by default (project convention: MORPHIX_AI_API_KEY), but any
OpenAI-compatible endpoint works by overriding MORPHIX_AI_BASE_URL / MORPHIX_AI_MODEL.

Design rule: the runtime pipeline must NEVER crash because the LLM is missing or
errors out. `try_chat` always returns a tuple (text, used_llm, error) so callers
can fall back to a deterministic stub reply.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("morphix.llm")

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"


def _cfg() -> dict:
    return {
        "api_key": os.environ.get("MORPHIX_AI_API_KEY", ""),
        "base_url": os.environ.get("MORPHIX_AI_BASE_URL", _DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("MORPHIX_AI_MODEL", _DEFAULT_MODEL),
        "temperature": float(os.environ.get("MORPHIX_AI_TEMPERATURE", "0.7")),
        "timeout": int(os.environ.get("MORPHIX_AI_TIMEOUT", "30")),
    }


def chat(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    timeout: int | None = None,
) -> str:
    """Call an OpenAI-compatible /chat/completions endpoint. Raises on any failure."""
    cfg = _cfg()
    if not cfg["api_key"]:
        raise RuntimeError("MORPHIX_AI_API_KEY is not set")
    model = model or cfg["model"]
    url = f"{cfg['base_url']}/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature if temperature is not None else cfg["temperature"],
    }
    with httpx.Client(timeout=timeout or cfg["timeout"]) as client:
        resp = client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def try_chat(system_prompt: str, user_prompt: str, **kwargs) -> tuple[str, bool, str | None]:
    """Safe wrapper: returns (text, used_llm, error). Never raises."""
    try:
        return chat(system_prompt, user_prompt, **kwargs), True, None
    except Exception as e:  # noqa: BLE001 — graceful degradation is the contract here
        logger.warning("LLM call failed, falling back to stub: %s: %s", type(e).__name__, e)
        return "", False, f"{type(e).__name__}: {e}"

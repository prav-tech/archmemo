"""Thin async wrapper around an OpenAI-compatible chat endpoint (Groq by default)."""

from __future__ import annotations

import re
from functools import lru_cache

from openai import AsyncOpenAI

from app.config import get_settings

# Reasoning models (e.g. qwen3) may prepend a <think> block. It is not part of
# the briefing and must never reach the user or the audit log.
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    cfg = get_settings()
    return AsyncOpenAI(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key or "missing",
        timeout=cfg.llm_timeout_seconds,
        max_retries=2,
    )


def strip_reasoning(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


async def complete_chat(system: str, user: str) -> tuple[str, str]:
    """Run one chat completion. Returns (text, model_name)."""
    cfg = get_settings()
    resp = await _client().chat.completions.create(
        model=cfg.llm_model,
        temperature=cfg.llm_temperature,
        max_tokens=cfg.llm_max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = strip_reasoning(resp.choices[0].message.content or "")
    return text, resp.model or cfg.llm_model

import json
import logging
from typing import Any

from openai import APIError, AsyncOpenAI

from app.core.config import get_settings

RESPONSE_INSTRUCTIONS = (
    "\n\n---\n"
    "输出格式 / Output format: 只返回一个 JSON 对象 / return exactly one JSON object, "
    '{"reply_text": string, "candidates": [{"type": string, "items": [{"id": string, "label": string}]?, '
    '"fields": object?}]}. reply_text 是给用户看的简短消息；candidates 是可选的结构化建议，'
    "没有则给空数组。不要在 JSON 之外输出任何文字。"
)


logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """The AI provider call failed (bad key, unknown model, quota, network…).
    Carries a short, secret-free reason for the API response; the full error
    goes to the server log."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LLMResponse:
    def __init__(self, reply_text: str, candidates: list[dict[str, Any]]):
        self.reply_text = reply_text
        self.candidates = candidates


def _client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_turn(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> LLMResponse:
    settings = get_settings()
    messages = [{"role": "system", "content": system_prompt + RESPONSE_INSTRUCTIONS}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        completion = await _client().chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except APIError as e:
        logger.exception("OpenAI call failed (model=%s)", settings.openai_model)
        status = getattr(e, "status_code", None)
        raise LLMUnavailable(f"{type(e).__name__}{f' {status}' if status else ''}") from e
    raw = completion.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"reply_text": raw, "candidates": []}

    return LLMResponse(
        reply_text=parsed.get("reply_text", ""),
        candidates=parsed.get("candidates", []) or [],
    )

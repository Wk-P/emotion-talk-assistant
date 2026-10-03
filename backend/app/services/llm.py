import json
import logging
from typing import Any

from openai import APIError, AsyncOpenAI, BadRequestError

from app.core.config import get_settings

RESPONSE_INSTRUCTIONS = (
    "\n\n---\n"
    "输出格式 / Output format: 只返回一个 JSON 对象 / return exactly one JSON object, "
    '{"reply_text": string, "candidates": [{"type": string, "items": [{"id": string, "label": string}]?, '
    '"fields": object?}]}. reply_text 是给用户看的回复；candidates 是可选的结构化建议，'
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


# Progress signals the model reports alongside the reply (app/prompts/stages.
# signal_rules), consumed by app/services/flow.after_reply.
SIGNAL_FIELDS = ("stage_done", "user_request", "self_criticism")


class LLMResponse:
    def __init__(
        self, reply_text: str, candidates: list[dict[str, Any]], signals: dict[str, Any] | None = None
    ):
        self.reply_text = reply_text
        self.candidates = candidates
        self.signals = signals or {}


def _client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _messages(system_prompt: str, history: list[dict[str, str]], user_message: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt + RESPONSE_INSTRUCTIONS}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


async def _create(messages: list[dict[str, str]], model: str, effort: str | None):
    kwargs: dict[str, Any] = {"reasoning_effort": effort} if effort else {}
    try:
        return await _client().chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"}, **kwargs
        )
    except BadRequestError as e:
        # The admin set an effort, then switched to a model that doesn't take
        # one: answer at the model's default rather than failing every turn.
        if effort and "reasoning" in str(e).lower():
            logger.warning("model %s rejected reasoning_effort=%s; retrying without it", model, effort)
            return await _client().chat.completions.create(
                model=model, messages=messages, response_format={"type": "json_object"}
            )
        raise


async def _complete_json(messages: list[dict[str, str]], model: str, effort: str | None) -> dict[str, Any] | str:
    try:
        completion = await _create(messages, model, effort)
    except APIError as e:
        logger.exception("OpenAI call failed (model=%s)", model)
        status = getattr(e, "status_code", None)
        raise LLMUnavailable(f"{type(e).__name__}{f' {status}' if status else ''}") from e
    raw = completion.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return parsed if isinstance(parsed, dict) else raw


async def generate_turn(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    model: str,
    effort: str | None = None,
) -> LLMResponse:
    # `model` and `effort` come from model_settings (admin choice; model
    # falls back to .env, effort to OpenAI's default for the model).
    parsed = await _complete_json(_messages(system_prompt, history, user_message), model, effort)
    if isinstance(parsed, str):
        parsed = {"reply_text": parsed, "candidates": []}

    return LLMResponse(
        reply_text=parsed.get("reply_text", ""),
        candidates=parsed.get("candidates", []) or [],
        signals={k: parsed.get(k) for k in SIGNAL_FIELDS},
    )

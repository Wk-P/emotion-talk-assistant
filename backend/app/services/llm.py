import json
import logging
from typing import Any

import httpx2
from openai import APIError, AsyncOpenAI, BadRequestError

from app.core.config import get_settings
from app.core.tls_pinning import openai_ssl_context
from app.services import ai_params


logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """The AI provider call failed (bad key, unknown model, quota, network…).
    Carries a short, secret-free reason for the API response; the full error
    goes to the server log."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# Progress signals the model reports alongside the reply (app/prompts/system.py
# "signals"), consumed by app/services/flow.after_reply.
SIGNAL_FIELDS = ("stage_done", "user_request", "self_criticism")


class LLMResponse:
    def __init__(
        self, reply_text: str, candidates: list[dict[str, Any]], signals: dict[str, Any] | None = None
    ):
        self.reply_text = reply_text
        self.candidates = candidates
        self.signals = signals or {}


# Pinned to the CA that actually anchors api.openai.com's certificate chain
# (see app/core/tls_pinning.py): defense-in-depth against a certificate
# forged via an unrelated, compromised CA that the OS trust store would
# otherwise still accept.
_HTTP_CLIENT = httpx2.AsyncClient(verify=openai_ssl_context())


def _client(params: dict[str, Any] | None = None) -> AsyncOpenAI:
    settings = get_settings()
    params = params or {}
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=params.get("timeout_seconds") or ai_params.FIELDS["timeout_seconds"][3],
        max_retries=params.get("max_retries", ai_params.FIELDS["max_retries"][3]),
        http_client=_HTTP_CLIENT,
    )


def _messages(system_prompt: list[str], history: list[dict[str, str]], user_message: str) -> list[dict[str, str]]:
    # One system message per part (app/prompts/base.py): program, then admin.
    messages = [{"role": "system", "content": p} for p in system_prompt]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


async def _create(
    messages: list[dict[str, str]], model: str, effort: str | None, params: dict[str, Any] | None = None
):
    kwargs: dict[str, Any] = {"reasoning_effort": effort} if effort else {}
    kwargs.update(ai_params.request_args(params))
    client = _client(params)
    while True:
        try:
            return await client.chat.completions.create(
                model=model, messages=messages, response_format={"type": "json_object"}, **kwargs
            )
        except BadRequestError as e:
            # A setting the model doesn't take (an effort set before switching
            # models, temperature on a reasoning model, …): drop it and answer
            # at the model's default rather than failing every turn.
            text = str(e).lower()
            rejected = [k for k in kwargs if k in text]
            if not rejected and "reasoning_effort" in kwargs and "reasoning" in text:
                rejected = ["reasoning_effort"]
            if not rejected:
                raise
            logger.warning("model %s rejected %s; retrying without", model, rejected)
            for k in rejected:
                kwargs.pop(k)


async def _complete_json(
    messages: list[dict[str, str]], model: str, effort: str | None, params: dict[str, Any] | None = None
) -> dict[str, Any] | str:
    try:
        completion = await _create(messages, model, effort, params)
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
    system_prompt: list[str],
    history: list[dict[str, str]],
    user_message: str,
    model: str,
    effort: str | None = None,
    params: dict[str, Any] | None = None,
) -> LLMResponse:
    # `model` and `effort` come from model_settings (admin choice; model
    # falls back to .env, effort to OpenAI's default for the model); `params`
    # from ai_params (the admin's advanced settings).
    parsed = await _complete_json(_messages(system_prompt, history, user_message), model, effort, params)
    if isinstance(parsed, str):
        parsed = {"reply_text": parsed, "candidates": []}

    return LLMResponse(
        reply_text=parsed.get("reply_text", ""),
        candidates=parsed.get("candidates", []) or [],
        signals={k: parsed.get(k) for k in SIGNAL_FIELDS},
    )


async def generate_json(
    system_prompt: str, user_message: str, model: str, effort: str | None = None, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """A one-off JSON answer outside the conversation (e.g. the conversation
    card, app/services/summary_card.py). {} when the model didn't return an
    object."""

    parsed = await _complete_json(_messages([system_prompt], [], user_message), model, effort, params)
    return parsed if isinstance(parsed, dict) else {}

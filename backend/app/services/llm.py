import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import APIError, AsyncOpenAI, BadRequestError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """The AI provider call failed (bad key, unknown model, quota, network…).
    Carries a short, secret-free reason for the API response; the full error
    goes to the server log."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


_clients: dict[tuple[str, float, int], AsyncOpenAI] = {}


def _client(timeout: float, retries: int) -> AsyncOpenAI:
    # One client per setting combination, so connections are reused across turns.
    key = (get_settings().openai_api_key, timeout, retries)
    if key not in _clients:
        _clients[key] = AsyncOpenAI(api_key=key[0], timeout=timeout, max_retries=retries)
    return _clients[key]


async def stream_text(messages: list[dict[str, str]], model: str, params: dict[str, Any]) -> AsyncIterator[str]:
    """A plain-text reply, piece by piece as the model writes it. `params`:
    temperature (None = the model's default), timeout_seconds, max_retries."""

    kwargs: dict[str, Any] = {"stream": True}
    if params.get("temperature") is not None:
        kwargs["temperature"] = params["temperature"]
    client = _client(params["timeout_seconds"], params["max_retries"])
    try:
        try:
            stream = await client.chat.completions.create(model=model, messages=messages, **kwargs)
        except BadRequestError as e:
            # Some models (reasoning ones) don't take a temperature: answer at
            # the model's default rather than failing every turn.
            if "temperature" not in kwargs or "temperature" not in str(e).lower():
                raise
            logger.warning("model %s rejected temperature; retrying without", model)
            kwargs.pop("temperature")
            stream = await client.chat.completions.create(model=model, messages=messages, **kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except APIError as e:
        logger.exception("OpenAI stream failed (model=%s)", model)
        status = getattr(e, "status_code", None)
        raise LLMUnavailable(f"{type(e).__name__}{f' {status}' if status else ''}") from e

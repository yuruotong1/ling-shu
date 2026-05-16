"""统一LLM客户端，支持OpenAI/Azure/Anthropic/自定义endpoint"""
import json
from openai import AsyncOpenAI
from app.models.model_config import ModelConfig


def _build_client(mc: ModelConfig, api_key_plain: str | None = None) -> AsyncOpenAI:
    key = api_key_plain or mc.api_key_encrypted or "no-key"
    return AsyncOpenAI(base_url=mc.endpoint, api_key=key)


async def chat_completion(
    mc: ModelConfig,
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    api_key_plain: str | None = None,
) -> dict:
    client = _build_client(mc, api_key_plain)
    target_model = model or mc.default_model
    params = dict(mc.default_params or {})
    if temperature is not None:
        params["temperature"] = temperature
    if max_tokens is not None:
        params["max_tokens"] = max_tokens

    kwargs: dict = dict(model=target_model, messages=messages, **params)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"

    response = await client.chat.completions.create(**kwargs)
    return response.model_dump()

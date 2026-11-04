"""DeepSeek 调用（OpenAI 兼容协议），技术方案 5.1、5.2。"""

import logging
import time
from collections.abc import AsyncIterator
from enum import StrEnum

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.errors import AppError

logger = logging.getLogger("app.ai")

_client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
    timeout=60,
    max_retries=1,
)
# 前缀续写（接着一段已有的回答往下写）只在 beta 地址上提供
_beta_client = _client.with_options(base_url=f"{settings.deepseek_base_url}/beta")


class Model(StrEnum):
    FAST = "fast"
    VISION = "vision"
    REASONING = "reasoning"


def _model_args(model: Model) -> dict:
    # deepseek-flash 默认开思考，首字要多等 1 秒左右；只有 REASONING 用思考模式
    thinking = "enabled" if model is Model.REASONING else "disabled"
    name = {
        Model.FAST: settings.model_fast,
        Model.VISION: settings.model_vision,
        Model.REASONING: settings.model_reasoning,
    }[model]
    return {"model": name, "extra_body": {"thinking": {"type": thinking}}}


def _app_error(exc: openai.OpenAIError) -> AppError:
    if isinstance(exc, openai.APITimeoutError):
        return AppError(504, "AI_TIMEOUT", "AI 响应超时，请稍后再试")
    return AppError(502, "AI_UNAVAILABLE", "AI 服务暂时不可用，请稍后再试")


def _log(scene: str, model: Model, started: float, tokens: int | None, failed: bool) -> None:
    logger.info(
        "ai scene=%s model=%s ms=%d tokens=%s failed=%s",
        scene,
        _model_args(model)["model"],
        (time.monotonic() - started) * 1000,
        tokens,
        failed,
    )


async def stream_text(
    scene: str, model: Model, messages: list[dict], prefix: str = ""
) -> AsyncIterator[str]:
    """逐段产出回答文字；传了 prefix 时接着它往下写，产出的不含 prefix 本身。

    出错抛 AppError；调用方中途停止迭代时连接随之关闭。
    """
    started = time.monotonic()
    tokens = None
    failed = True
    client = _client
    if prefix:
        client = _beta_client
        messages = [*messages, {"role": "assistant", "content": prefix, "prefix": True}]
    try:
        stream = await client.chat.completions.create(
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            **_model_args(model),
        )
        async with stream:
            async for chunk in stream:
                if chunk.usage:
                    tokens = chunk.usage.total_tokens
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        failed = False
    except openai.OpenAIError as exc:
        raise _app_error(exc) from exc
    finally:
        _log(scene, model, started, tokens, failed)


async def complete_text(
    scene: str, model: Model, messages: list[dict], json_output: bool = False
) -> str:
    started = time.monotonic()
    tokens = None
    failed = True
    extra = {"response_format": {"type": "json_object"}} if json_output else {}
    try:
        resp = await _client.chat.completions.create(
            messages=messages, **_model_args(model), **extra
        )
        tokens = resp.usage.total_tokens if resp.usage else None
        failed = False
        return resp.choices[0].message.content or ""
    except openai.OpenAIError as exc:
        raise _app_error(exc) from exc
    finally:
        _log(scene, model, started, tokens, failed)


async def complete_json[T: BaseModel](
    scene: str, model: Model, messages: list[dict], schema: type[T]
) -> T:
    """输出按 schema 校验，不合格时重新生成，最多重试 2 次。"""
    for _ in range(3):
        text = await complete_text(scene, model, messages, json_output=True)
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            logger.warning("ai scene=%s invalid output: %s", scene, exc.errors()[:3])
    raise AppError(502, "AI_UNAVAILABLE", "AI 服务暂时不可用，请稍后再试")

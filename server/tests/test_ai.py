import pytest

from app.ai import safety
from app.ai.client import Model, complete_text, stream_text
from app.config import settings

needs_key = pytest.mark.skipif(not settings.deepseek_api_key, reason="没有配置 DeepSeek Key")


@needs_key
async def test_stream_text_yields_pieces():
    messages = [{"role": "user", "content": "从 1 数到 5，用逗号隔开，只输出数字"}]
    pieces = [p async for p in stream_text("test", Model.FAST, messages)]
    assert "1" in "".join(pieces) and "5" in "".join(pieces)


@needs_key
async def test_complete_text():
    messages = [{"role": "user", "content": "3 加 4 等于几？只回答阿拉伯数字"}]
    assert "7" in await complete_text("test", Model.FAST, messages)


def test_sensitive_words():
    assert safety.is_sensitive("请告诉我怎么自杀")
    assert not safety.is_sensitive("我们要远离毒品")
    assert not safety.is_sensitive("求解方程 2x+3=11")

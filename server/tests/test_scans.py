import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ai import client as ai_client
from app.ai.client import Model, complete_json
from app.config import settings
from app.errors import AppError
from app.schemas.scan import Recognized
from app.services import scans

needs_key = pytest.mark.skipif(not settings.deepseek_api_key, reason="没有配置 DeepSeek Key")


async def _upload(client, headers, *lines: str) -> int:
    image = Image.new("RGB", (900, 120 + 100 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((40, 60 + 100 * i), line, fill="black", font=ImageFont.load_default(44))
    data = io.BytesIO()
    image.save(data, "PNG")
    resp = await client.post(
        "/api/v1/files", files={"file": ("q.png", data.getvalue())}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _recognize(client, headers, image_file_id: int):
    return await client.post(
        "/api/v1/recognize", json={"image_file_id": image_file_id}, headers=headers
    )


async def test_recognize_rules(client, student, teacher):
    teachers = await _upload(client, teacher)
    resp = await _recognize(client, teacher, teachers)
    assert resp.status_code == 403
    # 别人的图片按不存在处理，不调模型
    resp = await _recognize(client, student, teachers)
    assert resp.status_code == 404


async def test_invalid_output_is_retried(monkeypatch):
    outputs = iter(
        [
            "不是 JSON",
            '{"status": "ok", "subject": null, "text": ""}',
            '{"status": "ok", "subject": "math", "text": "1+1=?"}',
        ]
    )

    async def fake(*args, **kwargs):
        return next(outputs)

    monkeypatch.setattr(ai_client, "complete_text", fake)
    result = await complete_json("test", Model.VISION, [], Recognized)
    assert result.text == "1+1=?"

    outputs = iter(["{}"] * 3)
    with pytest.raises(AppError) as exc:
        await complete_json("test", Model.VISION, [], Recognized)
    assert exc.value.code == "AI_UNAVAILABLE"


@needs_key
async def test_recognize_one_question(client, student):
    image_id = await _upload(
        client, student, "12. Solve the equation: 3x + 5 = 20", "A. x=3   B. x=5   C. x=7"
    )
    resp = await _recognize(client, student, image_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["subject"] == "math"
    assert "3x" in body["text"].replace(" ", "")
    assert "A." in body["text"] and "C." in body["text"]


@needs_key
async def test_recognize_rejects_empty_and_multiple(client, student):
    resp = await _recognize(client, student, await _upload(client, student))
    assert resp.json()["error"]["code"] == "NO_QUESTION_FOUND"

    image_id = await _upload(
        client,
        student,
        "1. Solve the equation: 2x + 3 = 11",
        "2. A car travels 120 km in 2 hours.",
        "    What is its average speed?",
    )
    resp = await _recognize(client, student, image_id)
    assert resp.json()["error"]["code"] == "MULTIPLE_QUESTIONS"


def test_missing_table_separator_is_added():
    text = "数据如下表。\n\n| F/N | 0 | 2 |\n| L/cm | 5 | 6 |\n\n求原长。"
    fixed = scans._table_separators(text)
    assert "| F/N | 0 | 2 |\n| --- | --- | --- |\n| L/cm | 5 | 6 |\n\n求原长。" in fixed
    assert scans._table_separators(fixed) == fixed

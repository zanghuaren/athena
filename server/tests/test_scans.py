import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select

from app import worker
from app.ai import client as ai_client
from app.ai.client import Model, complete_json
from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import Attempt, Job, Question, Scan, ScanItem
from app.schemas.scan import PageRecognized, Recognized
from app.services import jobs, scans
from app.services.knowledge import KnowledgeCatalog, import_catalog

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


# ---- 整页批改 ----

SEED_DIR = Path(__file__).parents[1] / "seed" / "knowledge"


async def _page(client, headers, size=(1200, 1600), lines=()) -> int:
    """印刷体的题目用黑色，学生的作答用蓝色写在后面。"""
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for i, (question, answer) in enumerate(lines):
        y = 120 + 260 * i
        draw.text((60, y), question, fill="black", font=ImageFont.load_default(40))
        if answer:
            draw.text((140, y + 90), answer, fill=(20, 40, 200), font=ImageFont.load_default(56))
    data = io.BytesIO()
    image.save(data, "JPEG", quality=92)
    resp = await client.post(
        "/api/v1/files", files={"file": ("page.jpg", data.getvalue())}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _start(client, headers, image_file_id: int) -> dict:
    resp = await client.post(
        "/api/v1/scans", json={"image_file_id": image_file_id}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _run_jobs() -> None:
    async with SessionLocal() as db:
        while (job_id := await jobs.claim(db)) is not None:
            await worker.run_job(job_id)


async def test_small_photo_fails_as_unclear_without_model(client, student, teacher):
    created = await _start(client, student, await _page(client, student, size=(1200, 900)))
    assert created["scan"]["status"] == "processing"
    await _run_jobs()

    job = (await client.get(f"/api/v1/jobs/{created['job_id']}", headers=student)).json()
    assert job["status"] == "failed"
    assert job["error"]["code"] == "PHOTO_UNCLEAR"
    assert "平铺" in job["error"]["message"]
    scan_id = created["scan"]["id"]
    scan = (await client.get(f"/api/v1/scans/{scan_id}", headers=student)).json()
    assert (scan["status"], scan["fail_reason"], scan["items"]) == ("failed", "unclear", [])

    listed = (await client.get("/api/v1/scans", headers=student)).json()
    assert [s["id"] for s in listed["items"]] == [scan_id]
    assert listed["items"][0]["image"]["url"].startswith(f"/api/v1/files/{scan['image']['id']}")

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "role": "student",
            "username": "student_b",
            "password": "abc12345",
            "display_name": "小典",
            "grade": 8,
        },
    )
    others = {"Authorization": f"Bearer {other.json()['token']}"}
    assert (await client.get(f"/api/v1/scans/{scan_id}", headers=others)).status_code == 404
    assert (await client.get("/api/v1/scans", headers=others)).json()["total"] == 0
    assert (await client.get("/api/v1/scans", headers=teacher)).status_code == 403


async def _done_scan_with_unknown_item(client, headers) -> int:
    """直接建一份已完成、第 1 题是“？”的批改，用来测确认和重批的规则。"""
    me = (await client.get("/api/v1/me", headers=headers)).json()
    image_id = await _page(client, headers)
    async with SessionLocal() as db:
        question = Question(
            subject="math",
            type="blank",
            content={"stem": "3 + 4 = ____", "blank_count": 1},
            answer={"blanks": [["7"]]},
            analysis=[{"title": "加法", "body": "3 + 4 = 7"}],
            difficulty=1,
            source="scan",
            owner_id=me["id"],
            content_text="3 + 4 = ____",
        )
        scan = Scan(student_id=me["id"], image_file_id=image_id, status="done", total=1, unknown=1)
        db.add_all([question, scan])
        await db.flush()
        db.add(
            ScanItem(
                scan_id=scan.id,
                seq=1,
                bbox={"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.1},
                question_id=question.id,
                answer=None,
                confidence=0.3,
            )
        )
        await db.commit()
        return scan.id


async def test_confirm_unknown_item(client, student):
    scan_id = await _done_scan_with_unknown_item(client, student)
    url = f"/api/v1/scans/{scan_id}/items/1"
    resp = await client.post(f"{url}/confirm", json={"result": "correct"}, headers=student)
    assert resp.status_code == 200, resp.text
    attempt = resp.json()["attempt"]
    assert (attempt["result"], attempt["score"], attempt["graded_by"]) == ("correct", 1, "student")

    scan = (await client.get(f"/api/v1/scans/{scan_id}", headers=student)).json()
    assert (scan["total"], scan["correct"], scan["unknown"]) == (1, 1, 0)
    # 已经有结果的题不能再确认
    resp = await client.post(f"{url}/confirm", json={"result": "wrong"}, headers=student)
    assert resp.status_code == 409


async def test_regrade_checks_answer_and_replaces_attempt(client, student):
    scan_id = await _done_scan_with_unknown_item(client, student)
    url = f"/api/v1/scans/{scan_id}/items/1/regrade"
    for body in ({"answer": {"choice": ["A"]}}, {"answer": {"blanks": ["7", "8"]}}):
        resp = await client.post(url, json=body, headers=student)
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR", body
    assert (
        await client.post(
            f"/api/v1/scans/{scan_id}/items/2/regrade",
            json={"answer": {"blanks": ["7"]}},
            headers=student,
        )
    ).status_code == 404

    for answer, result in (("6", "wrong"), ("７", "correct")):
        resp = await client.post(url, json={"answer": {"blanks": [answer]}}, headers=student)
        assert resp.status_code == 202, resp.text
        await _run_jobs()
        job = (await client.get(f"/api/v1/jobs/{resp.json()['job_id']}", headers=student)).json()
        assert job["status"] == "succeeded"
        item = (await client.get(f"/api/v1/scans/{scan_id}", headers=student)).json()["items"][0]
        assert item["answer"] == {"blanks": [answer]}
        assert item["attempt"]["result"] == result
    async with SessionLocal() as db:
        # 重批覆盖原来的作答记录，不会越来越多
        assert await db.scalar(select(func.count()).select_from(Attempt)) == 1


@needs_key
async def test_grade_page_end_to_end(client, student):
    async with SessionLocal() as db:
        for path in sorted(SEED_DIR.glob("*.json")):
            await import_catalog(db, KnowledgeCatalog.model_validate_json(path.read_text()))
    lines = [
        ("1. Calculate: 3 + 4 = ____", "7"),
        ("2. Calculate: 12 - 5 = ____", "8"),
        ("3. Which number is a prime number? (   )", None),
        ("   A. 4      B. 6      C. 7      D. 9", "C"),
    ]
    created = await _start(client, student, await _page(client, student, lines=lines))
    await _run_jobs()
    job = (await client.get(f"/api/v1/jobs/{created['job_id']}", headers=student)).json()
    assert job["status"] == "succeeded", job

    scan = (await client.get(f"/api/v1/scans/{created['scan']['id']}", headers=student)).json()
    assert (scan["status"], scan["subject"], scan["total"]) == ("done", "math", 3)
    results = [i["attempt"] and i["attempt"]["result"] for i in scan["items"]]
    assert results == ["correct", "wrong", "correct"], scan["items"]
    assert scan["correct"] == 2
    for item in scan["items"]:
        assert item["question"]["answer"] is not None
        assert item["question"]["knowledge_points"]
        assert 0 <= item["bbox"]["y"] < 1
    # 识别的坐标框从上到下排列
    assert scan["items"][0]["bbox"]["y"] < scan["items"][2]["bbox"]["y"]


async def test_model_error_while_grading_keeps_its_code(client, student, monkeypatch):
    page = PageRecognized.model_validate(
        {
            "status": "ok",
            "subject": "math",
            "questions": [
                {
                    "seq": 1,
                    "type": "blank",
                    "content": {"stem": "3 + 4 = ____", "blank_count": 1},
                    "bbox": [50, 50, 950, 200],
                    "confidence": 0.9,
                }
            ],
        }
    )

    async def recognized_page(image):
        return page

    async def no_answer(limit, photo, question):
        return None

    async def unavailable(*args):
        raise AppError(502, "AI_UNAVAILABLE", "AI 服务暂时不可用，请稍后再试")

    monkeypatch.setattr(scans, "_recognize_page", recognized_page)
    monkeypatch.setattr(scans, "_recognize_answer", no_answer)
    monkeypatch.setattr(scans, "_grade_item", unavailable)
    created = await _start(client, student, await _page(client, student))
    async with SessionLocal() as db:
        job = await db.get_one(Job, created["job_id"])
        # 抛出的是原来的错误，Worker 才会按模型服务出错重试、提示，而不是“处理失败”
        with pytest.raises(AppError) as exc:
            await scans.grade_page(db, job)
    assert exc.value.code == "AI_UNAVAILABLE"


def test_page_keeps_valid_questions_when_one_is_broken():
    # 页面顶部露出上一题的半截选项，模型给出没有选项的单选题：只丢掉这一道
    broken = {"seq": 1, "type": "single", "content": {"stem": "C. 2:3"}, "bbox": [1, 2, 300, 40]}
    solution = {
        "seq": 2,
        "type": "solution",
        "content": {"stem": "(1) ____ (2) ____", "blank_count": 2},
        "bbox": [1, 50, 300, 90],
    }
    page = PageRecognized.model_validate(
        {
            "status": "ok",
            "subject": "physics",
            "questions": [{**broken, "confidence": 0.9}, {**solution, "confidence": 0.9}],
        }
    )
    assert [(q.seq, q.type, q.content.blank_count) for q in page.questions] == [
        (2, "solution", None)
    ]

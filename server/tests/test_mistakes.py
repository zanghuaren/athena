from datetime import timedelta

import pytest
from sqlalchemy import select

from app import worker
from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import Attempt, Chapter, File, KnowledgePoint, Question, Scan, ScanItem
from app.models import QuestionKnowledgePoint as QKP
from app.schemas.mistake import MistakeTip
from app.services import jobs, mistakes

needs_key = pytest.mark.skipif(not settings.deepseek_api_key, reason="没有配置 DeepSeek Key")


@pytest.fixture
def fake_tip(monkeypatch):
    calls = []

    async def fake(question, attempt, my_answer=None):
        calls.append(question.id)
        return MistakeTip(tip="先确定斜边再列式", error_reason="calculation")

    monkeypatch.setattr(mistakes, "_tip", fake)
    return calls


async def _me(client, headers) -> int:
    return (await client.get("/api/v1/me", headers=headers)).json()["id"]


# 每道题：题型、内容、答案、学生作答、结果、错因；结果为 None 是“？”
_ITEMS = [
    (
        "blank",
        {"stem": "3 + 4 = ____", "blank_count": 1},
        {"blanks": [["7"]]},
        {"blanks": ["6"]},
        "wrong",
        None,
    ),
    ("judge", {"stem": "7 是质数"}, {"judge": True}, {"judge": True}, "correct", None),
    (
        "solution",
        {"stem": "直角边 3 和 4，求斜边"},
        {"text": "5"},
        {"text": "3+4=7"},
        "partial",
        "method",
    ),
    ("blank", {"stem": "2 × 3 = ____", "blank_count": 1}, {"blanks": [["6"]]}, None, None, None),
]


async def _scan(client, headers, subject="math") -> int:
    """直接建一份已完成的批改：第 1 题错、第 2 题对、第 3 题部分对、第 4 题“？”。"""
    student_id = await _me(client, headers)
    async with SessionLocal() as db:
        chapter = await db.scalar(select(Chapter).where(Chapter.code == "M8-01"))
        if chapter is None:
            chapter = Chapter(code="M8-01", subject="math", grade=8, title="勾股定理", sort=1)
            db.add(chapter)
            await db.flush()
            db.add(
                KnowledgePoint(
                    chapter_id=chapter.id,
                    code="M8-01-01",
                    name="勾股定理",
                    description="",
                    grades=[8],
                    sort=1,
                )
            )
            await db.flush()
        point = await db.scalar(select(KnowledgePoint).where(KnowledgePoint.code == "M8-01-01"))
        image = File(owner_id=student_id, kind="image", path="x.jpg", mime="image/jpeg", size=1)
        db.add(image)
        await db.flush()
        scan = Scan(student_id=student_id, image_file_id=image.id, status="done", subject=subject)
        db.add(scan)
        await db.flush()
        for seq, (type_, content, answer, given, result, reason) in enumerate(_ITEMS, 1):
            question = Question(
                subject=subject,
                type=type_,
                content=content,
                answer=answer,
                analysis=[{"title": "思路", "body": "略"}],
                scoring_points=[{"point": "结果", "score": 2}] if type_ == "solution" else None,
                difficulty=2,
                source="scan",
                owner_id=student_id,
                content_text=content["stem"],
            )
            db.add(question)
            await db.flush()
            if seq == 3:
                db.add(QKP(question_id=question.id, knowledge_point_id=point.id))
            attempt = None
            if result is not None:
                attempt = Attempt(
                    student_id=student_id,
                    question_id=question.id,
                    source="scan",
                    source_id=scan.id,
                    answer=given,
                    grading_status="graded",
                    result=result,
                    score={"correct": 1, "partial": 1, "wrong": 0}[result],
                    max_score=2 if type_ == "solution" else 1,
                    grading_detail={"confidence": 0.9, "items": [], "summary": "缺少过程"},
                    graded_by="ai",
                    error_reason=reason,
                )
                db.add(attempt)
                await db.flush()
            db.add(
                ScanItem(
                    scan_id=scan.id,
                    seq=seq,
                    bbox={"x": 0, "y": 0.2 * seq, "w": 1, "h": 0.1},
                    question_id=question.id,
                    answer=given,
                    attempt_id=attempt.id if attempt else None,
                    confidence=0.9 if attempt else 0.3,
                )
            )
        await db.commit()
        return scan.id


async def _add(client, headers, scan_id, seqs):
    return await client.post(
        "/api/v1/mistakes/batch", json={"scan_id": scan_id, "seqs": seqs}, headers=headers
    )


async def test_add_from_scan(client, student, teacher, fake_tip):
    scan_id = await _scan(client, student)
    # 做对的题、“？”题、不存在的题都不能加
    for seqs, code in (([2], 400), ([4], 400), ([1, 9], 404)):
        assert (await _add(client, student, scan_id, seqs)).status_code == code, seqs
    assert (await _add(client, teacher, scan_id, [1])).status_code == 403

    resp = await _add(client, student, scan_id, [3, 1])
    assert resp.status_code == 201, resp.text
    items = resp.json()["items"]
    assert [i["question"]["content"]["stem"] for i in items] == [
        "3 + 4 = ____",
        "直角边 3 和 4，求斜边",
    ]
    first, third = items
    tomorrow = (mistakes.today() + timedelta(days=1)).isoformat()
    assert (first["source"], first["status"], first["next_review_on"]) == (
        "scan",
        "pending",
        tomorrow,
    )
    assert (first["wrong_count"], first["review_count"], first["tip"]) == (1, 0, "先确定斜边再列式")
    # 作答记录有错因就用它的，没有才用模型判断的
    assert (first["error_reason"], third["error_reason"]) == ("calculation", "method")
    assert first["question"]["answer"] == {"blanks": [["7"]]}
    assert len(fake_tip) == 2
    scan = (await client.get(f"/api/v1/scans/{scan_id}", headers=student)).json()
    assert [i["mistake_id"] for i in scan["items"]] == [first["id"], None, third["id"], None]

    # 再加一次不重复入本，也不重置复习进度和笔记
    resp = await client.patch(
        f"/api/v1/mistakes/{first['id']}", json={"note": "看清加号"}, headers=student
    )
    assert resp.status_code == 200
    resp = await _add(client, student, scan_id, [1])
    assert [i["id"] for i in resp.json()["items"]] == [first["id"]]
    assert len(fake_tip) == 2
    detail = (await client.get(f"/api/v1/mistakes/{first['id']}", headers=student)).json()
    assert detail["note"] == "看清加号"

    # 别人的批改按不存在处理
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
    assert (await _add(client, others, scan_id, [1])).status_code == 404
    assert (await client.get(f"/api/v1/mistakes/{first['id']}", headers=others)).status_code == 404
    assert (await client.get("/api/v1/mistakes", headers=others)).json()["total"] == 0


async def test_tip_failure_does_not_block(client, student, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise AppError(502, "AI_UNAVAILABLE", "AI 服务暂时不可用，请稍后再试")

    monkeypatch.setattr(mistakes, "complete_json", unavailable)
    scan_id = await _scan(client, student)
    resp = await _add(client, student, scan_id, [1, 3])
    assert resp.status_code == 201, resp.text
    assert [(i["tip"], i["error_reason"]) for i in resp.json()["items"]] == [
        (None, None),
        (None, "method"),
    ]


async def test_list_filters_and_sort(client, student, fake_tip):
    math = await _scan(client, student)
    physics = await _scan(client, student, subject="physics")
    await _add(client, student, math, [1, 3])
    await _add(client, student, physics, [1])
    listed = (await client.get("/api/v1/mistakes", headers=student)).json()
    assert listed["total"] == 3
    # 最近加入的在前
    assert listed["items"][0]["question"]["subject"] == "physics"

    async def ids(**params):
        resp = await client.get("/api/v1/mistakes", params=params, headers=student)
        assert resp.status_code == 200, resp.text
        return [i["question"]["content"]["stem"] for i in resp.json()["items"]]

    assert await ids(subject="physics") == ["3 + 4 = ____"]
    point = (
        listed["items"][1]["question"]["knowledge_points"]
        or listed["items"][2]["question"]["knowledge_points"]
    )
    assert await ids(knowledge_point_id=point[0]["id"]) == ["直角边 3 和 4，求斜边"]
    assert await ids(source="practice") == []
    assert len(await ids(status="pending")) == 3

    async with SessionLocal() as db:
        first = await db.scalar(select(mistakes.Mistake).order_by(mistakes.Mistake.id))
        first.wrong_count = 3
        await db.commit()
    assert (await ids(sort="wrong_count"))[0] == "3 + 4 = ____"
    resp = await client.get("/api/v1/mistakes", params={"sort": "x"}, headers=student)
    assert resp.status_code == 400


async def test_detail_update_and_delete(client, student, fake_tip):
    scan_id = await _scan(client, student)
    mistake_id = (await _add(client, student, scan_id, [3])).json()["items"][0]["id"]
    url = f"/api/v1/mistakes/{mistake_id}"
    detail = (await client.get(url, headers=student)).json()
    assert detail["answer"] == {"text": "3+4=7"}
    assert (detail["attempt"]["result"], detail["attempt"]["score"]) == ("partial", 1)
    assert (detail["my_answer"], detail["note"]) == (None, None)

    resp = await client.patch(url, json={"note": "字" * 501}, headers=student)
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    resp = await client.patch(
        url, json={"error_reason": "concept", "note": "勾股"}, headers=student
    )
    assert (resp.json()["error_reason"], resp.json()["note"]) == ("concept", "勾股")
    # 只改传了的字段
    resp = await client.patch(url, json={"status": "mastered"}, headers=student)
    body = resp.json()
    assert (body["status"], body["next_review_on"], body["error_reason"]) == (
        "mastered",
        None,
        "concept",
    )
    resp = await client.patch(url, json={"status": "pending"}, headers=student)
    body = resp.json()
    assert (body["status"], body["review_stage"]) == ("pending", 0)
    assert body["next_review_on"] == (mistakes.today() + timedelta(days=1)).isoformat()

    assert (await client.delete(url, headers=student)).status_code == 204
    assert (await client.get(url, headers=student)).status_code == 404
    # 移出后可以重新加入
    assert (await _add(client, student, scan_id, [3])).status_code == 201


async def test_regrade_updates_my_answer(client, student, fake_tip):
    scan_id = await _scan(client, student)
    mistake_id = (await _add(client, student, scan_id, [1])).json()["items"][0]["id"]
    resp = await client.post(
        f"/api/v1/scans/{scan_id}/items/1/regrade",
        json={"answer": {"blanks": ["5"]}},
        headers=student,
    )
    assert resp.status_code == 202
    async with SessionLocal() as db:
        while (job_id := await jobs.claim(db)) is not None:
            await worker.run_job(job_id)
    detail = (await client.get(f"/api/v1/mistakes/{mistake_id}", headers=student)).json()
    assert detail["answer"] == {"blanks": ["5"]}


@needs_key
async def test_real_tip(client, student):
    scan_id = await _scan(client, student)
    item = (await _add(client, student, scan_id, [3])).json()["items"][0]
    assert item["tip"] and len(item["tip"]) <= 60

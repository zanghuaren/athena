import json
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import worker
from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import (
    Attempt,
    Chapter,
    Conversation,
    File,
    KnowledgePoint,
    Message,
    Question,
    Scan,
    ScanItem,
)
from app.models import QuestionKnowledgePoint as QKP
from app.schemas.mistake import MistakeTip
from app.services import jobs, knowledge, mistakes
from app.services.knowledge import KnowledgeCatalog, import_catalog

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


# ---- 答疑加入、手动添加 ----

SEED_DIR = Path(__file__).parents[1] / "seed" / "knowledge"

_EXTRACTED = {
    "status": "ok",
    "subject": "math",
    "question": {
        "type": "single",
        "content": {
            "stem": "直角三角形两直角边为 6 和 8，斜边长为（　）",
            "options": [{"key": "A", "text": "9"}, {"key": "B", "text": "10"}],
        },
        "answer": {"choice": ["B"]},
        "analysis": [{"title": "用勾股定理", "body": "$\\sqrt{6^2+8^2}=10$"}],
        "difficulty": 1,
    },
    "knowledge_points": [],
}


@pytest.fixture
async def catalog():
    async with SessionLocal() as db:
        for path in sorted(SEED_DIR.glob("*.json")):
            await import_catalog(db, KnowledgeCatalog.model_validate_json(path.read_text()))
        return await knowledge.catalog(db, "math")


@pytest.fixture
def fake_extract(monkeypatch):
    """模型按给定的输出走真实的校验；calls 记录调用次数。"""
    outputs: list[dict] = []
    calls = []

    async def fake(scene, model, messages, schema, context=None):
        calls.append(messages[-1]["content"])
        # 和 complete_json 一样，不合格就换下一个输出
        while True:
            try:
                return schema.model_validate_json(json.dumps(outputs.pop(0)), context=context)
            except ValidationError:
                continue

    monkeypatch.setattr(mistakes, "complete_json", fake)
    return outputs, calls


async def _reply(client, headers, subject=None) -> int:
    """直接建一段对话：学生问一道题，AI 引导式讲了一步。返回 AI 那条消息的 ID。"""
    user_id = await _me(client, headers)
    async with SessionLocal() as db:
        conversation = Conversation(user_id=user_id, title="勾股定理", subject=subject)
        db.add(conversation)
        await db.flush()
        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content="直角三角形两直角边为 6 和 8，斜边长为多少？A. 9 B. 10",
            )
        )
        reply = Message(
            conversation_id=conversation.id, role="assistant", content="先想想勾股定理怎么写？"
        )
        db.add(reply)
        await db.commit()
        return reply.id


async def test_extract_and_add_from_ask(client, student, teacher, catalog, fake_tip, fake_extract):
    outputs, calls = fake_extract
    message_id = await _reply(client, student, subject="math")
    url = f"/api/v1/messages/{message_id}/extract-question"
    assert (await client.post(url, headers=teacher)).status_code == 403
    assert (
        await client.post(f"/api/v1/messages/{message_id - 1}/extract-question", headers=student)
    ).status_code == 404

    # 知识点不在目录里的输出不合格，重新生成
    code = next(iter(catalog))
    outputs += [
        {**_EXTRACTED, "knowledge_points": ["P8-01-01"]},
        {**_EXTRACTED, "knowledge_points": [code]},
    ]
    resp = await client.post(url, headers=student)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mistake_id"] is None
    draft = body["question"]
    assert (draft["subject"], draft["type"], draft["answer"]) == (
        "math",
        "single",
        {"choice": ["B"]},
    )
    assert [k["code"] for k in draft["knowledge_points"]] == [code]
    # 指定了学科的会话只给这个学科的目录，带上了学生的原题
    assert len(calls) == 1
    assert "斜边长为多少" in calls[0] and "P8-" not in calls[0]

    question = {k: v for k, v in draft.items() if k != "knowledge_points"}
    question["content"]["stem"] = "直角边 6 和 8，斜边是（　）"
    question["knowledge_point_ids"] = [catalog[code][0]]
    payload = {"source": "ask", "message_id": message_id, "question": question}
    resp = await client.post("/api/v1/mistakes", json=payload, headers=student)
    assert resp.status_code == 201, resp.text
    mistake = resp.json()
    assert (mistake["source"], mistake["question"]["source"]) == ("ask", "ask")
    assert mistake["question"]["content"]["stem"] == "直角边 6 和 8，斜边是（　）"
    assert (mistake["answer"], mistake["attempt"], mistake["tip"]) == (
        None,
        None,
        "先确定斜边再列式",
    )

    # 提取过的讲解直接返回那道题，不再调模型；再加一次也不重复
    resp = await client.post(url, headers=student)
    assert resp.json()["mistake_id"] == mistake["id"]
    assert resp.json()["question"]["content"]["stem"] == "直角边 6 和 8，斜边是（　）"
    assert len(calls) == 1
    resp = await client.post("/api/v1/mistakes", json=payload, headers=student)
    assert resp.json()["id"] == mistake["id"]
    assert len(fake_tip) == 1


async def test_extract_without_question(client, student, catalog, fake_extract):
    outputs, calls = fake_extract
    message_id = await _reply(client, student)
    outputs.append({"status": "none"})
    resp = await client.post(f"/api/v1/messages/{message_id}/extract-question", headers=student)
    assert resp.json()["error"]["code"] == "NO_QUESTION_FOUND"
    # 没指定学科时三个学科的目录都给
    assert "M8-" in calls[0] and "P8-" in calls[0]


async def test_add_manual(client, student, catalog, fake_tip):
    math_id = next(iter(catalog.values()))[0]
    payload = {
        "source": "manual",
        "subject": "math",
        "stem": "$\\sqrt{8}$ 化简",
        "answer": "$2\\sqrt{2}$",
        "my_answer": "4",
        "knowledge_point_ids": [math_id],
    }
    resp = await client.post("/api/v1/mistakes", json=payload, headers=student)
    assert resp.status_code == 201, resp.text
    mistake = resp.json()
    assert (mistake["source"], mistake["my_answer"], mistake["answer"]) == ("manual", "4", None)
    question = mistake["question"]
    assert (question["type"], question["source"], question["answer"]) == (
        "solution",
        "manual",
        {"text": "$2\\sqrt{2}$", "final": None},
    )
    assert [k["id"] for k in question["knowledge_points"]] == [math_id]

    async with SessionLocal() as db:
        other = await knowledge.catalog(db, "physics")
    resp = await client.post(
        "/api/v1/mistakes",
        json={**payload, "knowledge_point_ids": [next(iter(other.values()))[0]]},
        headers=student,
    )
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    resp = await client.post("/api/v1/mistakes", json={**payload, "stem": ""}, headers=student)
    assert resp.status_code == 400


@needs_key
async def test_real_extract(client, student, catalog):
    user_id = await _me(client, student)
    async with SessionLocal() as db:
        conversation = Conversation(user_id=user_id, title="方程")
        db.add(conversation)
        await db.flush()
        db.add_all(
            [
                Message(conversation_id=conversation.id, role="user", content="解方程 3x + 5 = 20"),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="我们先把 5 移到右边。你觉得移过去以后右边是多少？",
                ),
                Message(conversation_id=conversation.id, role="user", content="15"),
            ]
        )
        reply = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="对！$3x=15$，接下来两边同时除以几？",
        )
        db.add(reply)
        await db.commit()
    resp = await client.post(f"/api/v1/messages/{reply.id}/extract-question", headers=student)
    assert resp.status_code == 200, resp.text
    draft = resp.json()["question"]
    assert draft["subject"] == "math"
    assert "3x" in draft["content"]["stem"].replace(" ", "")
    assert "5" in json.dumps(draft["answer"])
    assert draft["knowledge_points"]

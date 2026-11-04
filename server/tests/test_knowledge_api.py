import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import KnowledgePoint, Question, QuestionKnowledgePoint, User
from app.services.knowledge import KnowledgeCatalog, import_catalog

CATALOG = {
    "subject": "english",
    "chapters": [
        {
            "code": "E-01",
            "grade": None,
            "title": "名词",
            "points": [
                {
                    "code": "E-01-01",
                    "name": "复数",
                    "description": "规则和不规则变化",
                    "grades": [7],
                },
                {"code": "E-01-02", "name": "所有格", "description": "'s 和 of", "grades": [7, 8]},
            ],
        },
        {
            "code": "E-02",
            "grade": None,
            "title": "代词",
            "points": [{"code": "E-02-01", "name": "反身代词", "description": "x", "grades": [8]}],
        },
    ],
}


@pytest.fixture
async def catalog():
    async with SessionLocal() as db:
        await import_catalog(db, KnowledgeCatalog.model_validate(CATALOG))


async def point_id(code: str) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(KnowledgePoint.id).where(KnowledgePoint.code == code))


async def test_knowledge_tree_requires_login(client):
    resp = await client.get("/api/v1/knowledge-tree", params={"subject": "math"})
    assert resp.status_code == 401


async def test_knowledge_tree_keeps_order(client, student, catalog):
    resp = await client.get("/api/v1/knowledge-tree?subject=english", headers=student)
    assert resp.status_code == 200
    chapters = resp.json()["chapters"]
    assert [ch["code"] for ch in chapters] == ["E-01", "E-02"]
    assert [p["code"] for p in chapters[0]["knowledge_points"]] == ["E-01-01", "E-01-02"]


async def test_knowledge_tree_filters_by_grade(client, student, catalog):
    resp = await client.get("/api/v1/knowledge-tree?subject=english&grade=7", headers=student)
    chapters = resp.json()["chapters"]
    # 代词这一章没有七年级的知识点，整章不返回
    assert [ch["code"] for ch in chapters] == ["E-01"]
    assert len(chapters[0]["knowledge_points"]) == 2

    resp = await client.get("/api/v1/knowledge-tree?subject=math", headers=student)
    assert resp.json()["chapters"] == []


async def test_knowledge_point_detail(client, student, catalog):
    resp = await client.get(
        f"/api/v1/knowledge-points/{await point_id('E-01-02')}", headers=student
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "'s 和 of"
    assert body["chapter"]["title"] == "名词"

    resp = await client.get("/api/v1/knowledge-points/999999", headers=student)
    assert resp.status_code == 404


async def add_question(owner_username: str | None = None) -> int:
    async with SessionLocal() as db:
        owner_id = None
        if owner_username:
            owner_id = await db.scalar(select(User.id).where(User.username == owner_username))
        q = Question(
            subject="english",
            type="single",
            content={
                "stem": "two ____",
                "options": [{"key": "A", "text": "mans"}, {"key": "B", "text": "men"}],
            },
            answer={"choice": ["B"]},
            analysis=[{"title": "不规则变化", "body": "man 的复数是 men。"}],
            difficulty=1,
            source="preset" if owner_id is None else "teacher",
            owner_id=owner_id,
            content_text="two ____ mans men",
        )
        db.add(q)
        await db.flush()
        kp = await db.scalar(select(KnowledgePoint.id).where(KnowledgePoint.code == "E-01-01"))
        db.add(QuestionKnowledgePoint(question_id=q.id, knowledge_point_id=kp))
        await db.commit()
        return q.id


async def test_teacher_sees_answer_of_preset_question(client, teacher, catalog):
    resp = await client.get(f"/api/v1/questions/{await add_question()}", headers=teacher)
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == {"choice": ["B"]}
    assert body["analysis"][0]["title"] == "不规则变化"
    assert [p["code"] for p in body["knowledge_points"]] == ["E-01-01"]


async def test_student_does_not_see_answer(client, student, catalog):
    resp = await client.get(f"/api/v1/questions/{await add_question()}", headers=student)
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"]["options"][1]["text"] == "men"
    assert body["answer"] is None
    assert body["analysis"] is None


async def test_others_question_is_not_found(client, student, teacher, catalog):
    question_id = await add_question(owner_username="teacher_a")
    assert (
        await client.get(f"/api/v1/questions/{question_id}", headers=teacher)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/questions/{question_id}", headers=student)
    ).status_code == 404

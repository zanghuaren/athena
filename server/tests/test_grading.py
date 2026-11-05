import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import Attempt, Question, User
from app.schemas.attempt import (
    BlanksInput,
    ChoiceInput,
    JudgeInput,
    SubInput,
    SubInputItem,
    TextInput,
)
from app.schemas.question import QuestionBody, QuestionContent
from app.services import grading

needs_key = pytest.mark.skipif(not settings.deepseek_api_key, reason="没有配置 DeepSeek Key")

ANALYSIS = [{"title": "解析", "body": "略"}]


def _body(type_: str, content: dict, answer: dict, **extra) -> QuestionBody:
    return QuestionBody.model_validate(
        {
            "type": type_,
            "content": content,
            "answer": answer,
            "analysis": ANALYSIS,
            "difficulty": 2,
            **extra,
        }
    )


OPTIONS = [{"key": k, "text": k.lower()} for k in "ABCD"]
SINGLE = _body("single", {"stem": "选一个", "options": OPTIONS}, {"choice": ["B"]})
MULTIPLE = _body("multiple", {"stem": "选多个", "options": OPTIONS}, {"choice": ["A", "C"]})
JUDGE = _body("judge", {"stem": "对吗"}, {"judge": True})
BLANK = _body(
    "blank",
    {"stem": "$x$ 的值是 ____，$y$ 的值是 ____", "blank_count": 2},
    {"blanks": [["1/2"], ["2x+1"]]},
)
READING = _body(
    "reading",
    {
        "stem": "阅读短文，回答问题",
        "material": "Tom has two cats.",
        "sub_questions": [
            {"seq": 1, "type": "single", "stem": "How many?", "options": OPTIONS, "score": 2},
            {"seq": 2, "type": "judge", "stem": "Tom has a dog.", "score": 1},
            {"seq": 3, "type": "blank", "stem": "Tom has ____ cats.", "blank_count": 1, "score": 2},
        ],
    },
    {
        "sub": [
            {"seq": 1, "choice": ["B"]},
            {"seq": 2, "judge": False},
            {"seq": 3, "blanks": [["two"]]},
        ]
    },
)
SOLUTION = _body(
    "solution",
    {"stem": "在 Rt△ABC 中，∠C=90°，AC=3，BC=4，求 AB 的长。"},
    {"text": "由勾股定理，$AB=\\sqrt{AC^2+BC^2}=\\sqrt{9+16}=5$", "final": "AB=5"},
    scoring_points=[
        {"point": "指出 AB 是斜边并写出勾股定理 $AB^2=AC^2+BC^2$", "score": 2},
        {"point": "代入计算得 AB=5", "score": 2},
    ],
)


async def _grade(body, answer, max_score=None, subject="math"):
    return await grading.grade(subject, body, answer, max_score or grading.natural_score(body))


async def test_choice_and_judge():
    assert (await _grade(SINGLE, ChoiceInput(choice=["B"]))).result == "correct"
    wrong = await _grade(SINGLE, ChoiceInput(choice=["A"]))
    assert (wrong.result, wrong.score, wrong.graded_by) == ("wrong", 0, "rule")

    # 多选：全对满分、少选一半、错选 0
    for choice, result, score in (
        (["C", "A"], "correct", 4),
        (["A"], "partial", 2),
        (["A", "B"], "wrong", 0),
        ([], "wrong", 0),
    ):
        got = await _grade(MULTIPLE, ChoiceInput(choice=choice), max_score=4)
        assert (got.result, got.score, got.max_score) == (result, score, 4), choice

    assert (await _grade(JUDGE, JudgeInput(judge=True))).result == "correct"
    assert (await _grade(JUDGE, JudgeInput(judge=None))).result == "wrong"


async def test_blanks_match_by_rule():
    # 全角、空格、公式的 $ 不影响；数学上等价的写法都算对
    for first, second in (
        ("１/２", "2x + 1"),
        ("0.5", "1+2x"),
        ("$\\frac{1}{2}$", "1 + x·2"),
        ("2^(-1)", "x×2+1"),
    ):
        got = await _grade(BLANK, BlanksInput(blanks=[first, second]))
        assert (got.result, got.graded_by) == ("correct", "rule"), (first, second)

    # 都是数字还对不上，直接判错，不用问模型；没填的空也是错
    got = await _grade(BLANK, BlanksInput(blanks=["0.6", ""]), max_score=3)
    assert (got.result, got.score, got.graded_by) == ("wrong", 0, "rule")
    got = await _grade(BLANK, BlanksInput(blanks=["0.5"]), max_score=3)
    assert (got.result, got.score) == ("partial", 1.5)
    assert [(i.key, i.result, i.score) for i in got.detail.items] == [
        ("blank_1", "correct", 1.5),
        ("blank_2", "wrong", 0),
    ]


def test_chinese_and_english_blanks_skip_sympy():
    # 语文、英语的“3”和“三”字面不同，不能当算式比，交给模型判断
    assert grading._match_blank("math", ["3"], "3.0") is True
    for subject in ("chinese", "english"):
        assert grading._match_blank(subject, ["三"], "3") is None
        assert grading._match_blank(subject, ["春风"], " 春风 ") is True


def test_expression_parser_only_accepts_plain_math():
    assert grading._expr("√2") is not None
    assert grading._expr("x²") is not None
    # parse_expr 内部用 eval，不能放行任意名字；算不完的乘方也不算
    for text in ("__import__('os')", "exit()", "abc", "9^9^9", "2^99999", "1" * 41):
        assert grading._expr(text) is None, text


async def test_reading_grades_each_sub_question():
    answer = SubInput(
        sub=[
            SubInputItem(seq=1, choice=["B"]),
            SubInputItem(seq=3, blanks=["two"]),
        ]
    )
    got = await _grade(READING, answer, subject="english")
    assert (got.result, got.score, got.max_score) == ("partial", 4, 5)
    assert [(i.key, i.result) for i in got.detail.items] == [
        ("sub_1", "correct"),
        ("sub_2", "wrong"),
        ("sub_3_blank_1", "correct"),
    ]


async def test_empty_solution_and_wrong_structure():
    got = await _grade(SOLUTION, TextInput(text=" "), max_score=10)
    assert (got.result, got.score, got.max_score, got.graded_by) == ("wrong", 0, 10, "rule")
    assert [i.max_score for i in got.detail.items] == [5, 5]

    with pytest.raises(ValueError):
        await _grade(SINGLE, BlanksInput(blanks=["B"]))


async def _question(body: QuestionBody, subject="math") -> Question:
    async with SessionLocal() as db:
        question = Question(
            subject=subject,
            **body.model_dump(include={"type", "content", "answer", "analysis", "difficulty"}),
            scoring_points=None,
            source="preset",
            content_text=body.content.stem,
        )
        db.add(question)
        await db.commit()
        return question


async def _student(client, student) -> User:
    me = (await client.get("/api/v1/me", headers=student)).json()
    async with SessionLocal() as db:
        return await db.get_one(User, me["id"])


async def test_record_writes_attempt(client, student):
    user = await _student(client, student)
    question = await _question(MULTIPLE)
    async with SessionLocal() as db:
        await grading.record(db, user, question, ChoiceInput(choice=["A"]), "scan", 7)
        await grading.record(
            db, user, question, ChoiceInput(choice=["A", "C"]), "homework", 8, max_score=6
        )
        await db.commit()
        scan, homework = await db.scalars(select(Attempt).order_by(Attempt.id))

    assert (scan.grading_status, scan.result, scan.score, scan.max_score) == (
        "graded",
        "partial",
        0.5,
        1,
    )
    assert scan.answer == {"choice": ["A"]}
    assert scan.grading_detail["confidence"] == 1
    assert scan.graded_by == "rule"
    assert scan.counted_at is not None
    # 作业等老师发布后才计入掌握度
    assert (homework.result, homework.score, homework.counted_at) == ("correct", 6, None)


async def test_record_keeps_pending_when_ai_fails(client, student, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise AppError(502, "AI_UNAVAILABLE", "AI 服务暂时不可用，请稍后再试")

    monkeypatch.setattr(grading, "complete_json", unavailable)
    user = await _student(client, student)
    question = await _question(BLANK)
    async with SessionLocal() as db:
        attempt = await grading.record(
            db, user, question, BlanksInput(blanks=["x", "y"]), "scan", 1
        )
        await db.commit()
    assert (attempt.grading_status, attempt.result, attempt.score) == ("pending", None, None)
    assert attempt.counted_at is None


UNIT = _body("blank", {"stem": "5 cm = ____ m", "blank_count": 1}, {"blanks": [["0.05"]]})


@needs_key
async def test_ai_judges_blank_with_units():
    got = await _grade(UNIT, BlanksInput(blanks=["0.05m"]), subject="physics")
    assert (got.result, got.graded_by) == ("correct", "ai")
    got = await _grade(UNIT, BlanksInput(blanks=["5m"]), subject="physics")
    assert got.result == "wrong"


@needs_key
async def test_ai_grades_solution_by_points():
    answer = TextInput(text="AB²=AC²+BC²=3²+4²=9+16=24，所以 AB=√24=2√6")
    got = await _grade(SOLUTION, answer, max_score=8)
    assert (got.result, got.graded_by) == ("partial", "ai")
    assert 0 < got.score < 8
    assert got.detail.items[0].score == 4
    assert got.detail.summary
    assert got.error_reason in ("calculation", "careless")

    correct = await _grade(SOLUTION, TextInput(text="AB²=AC²+BC²=9+16=25，AB=5"), max_score=8)
    assert (correct.result, correct.score, correct.error_reason) == ("correct", 8, None)


@needs_key
async def test_solve_question_without_answer():
    content = QuestionContent(
        stem="下列各数中，最小的是（　）",
        options=[
            {"key": "A", "text": "$-2$"},
            {"key": "B", "text": "$0$"},
            {"key": "C", "text": "$-\\frac{1}{2}$"},
            {"key": "D", "text": "$1$"},
        ],
    )
    catalog = {
        "M7-01-01": "正数和负数",
        "M7-01-04": "有理数的大小比较",
        "M8-03-01": "勾股定理",
        "M8-03-02": "勾股定理的逆定理",
    }
    body, points = await grading.solve("math", "single", content, catalog)
    assert body.answer.choice == ["A"]
    assert body.analysis
    assert "M7-01-04" in points

    solution, points = await grading.solve("math", "solution", SOLUTION.content, catalog)
    assert solution.answer.text
    assert solution.scoring_points
    assert points[0] == "M8-03-01"

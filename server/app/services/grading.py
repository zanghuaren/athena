"""判分（KP-04）：规则判得了的由代码判，判不了的交给 MODEL_REASONING，技术方案 5.5。"""

import json
import logging
import re
import string
from dataclasses import dataclass

import sympy
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from app.ai import prompts
from app.ai.client import Model, complete_json
from app.errors import AppError
from app.models import Attempt, Question, User
from app.schemas.attempt import (
    BlanksInput,
    BlankVerdicts,
    ChoiceInput,
    GradingDetail,
    GradingItem,
    JudgeInput,
    Result,
    SolutionGrading,
    Solved,
    StudentAnswer,
    SubInput,
    SubInputItem,
    TextInput,
)
from app.schemas.question import QuestionBody, QuestionContent

logger = logging.getLogger(__name__)

AI_ERRORS = {"AI_TIMEOUT", "AI_UNAVAILABLE"}


@dataclass
class Grading:
    result: Result
    score: float
    max_score: float
    detail: GradingDetail
    graded_by: str
    error_reason: str | None = None


async def record(
    db: AsyncSession,
    student: User,
    question: Question,
    answer: StudentAnswer,
    source: str,
    source_id: int,
    max_score: float | None = None,
) -> Attempt:
    """判分并写一条作答记录，由调用方 commit。

    max_score 是这道题在作业里的分值；不传时用题目本身的分值（见 natural_score）。
    模型出错时记为待判分，不影响其他题。
    """
    body = question_body(question)
    max_score = max_score or natural_score(body)
    attempt = Attempt(
        student_id=student.id,
        question_id=question.id,
        source=source,
        source_id=source_id,
        answer=answer.model_dump(),
        max_score=max_score,
        grading_status="pending",
    )
    db.add(attempt)
    try:
        grading = await grade(question.subject, body, answer, max_score)
    except AppError as exc:
        if exc.code not in AI_ERRORS:
            raise
        logger.warning("grading question=%s pending: %s", question.id, exc.code)
        return attempt
    attempt.grading_status = "graded"
    attempt.result = grading.result
    attempt.score = grading.score
    attempt.grading_detail = grading.detail.model_dump(exclude_none=True)
    attempt.graded_by = grading.graded_by
    attempt.error_reason = grading.error_reason
    # 作业等老师发布后才计入掌握度（数据库设计 attempts）
    if source != "homework":
        attempt.counted_at = func.now()
    return attempt


def question_body(question: Question) -> QuestionBody:
    return QuestionBody.model_validate(
        {
            "type": question.type,
            "content": question.content,
            "answer": question.answer,
            "analysis": question.analysis,
            "scoring_points": question.scoring_points,
            "difficulty": question.difficulty,
        }
    )


def natural_score(body: QuestionBody) -> float:
    """题目本身的分值：选择、判断 1 分，填空每空 1 分，解答按评分要点，完形、阅读按小题分值。"""
    match body.type:
        case "solution" | "essay":
            return sum(p.score for p in body.scoring_points or [])
        case "cloze" | "reading":
            return sum(s.score for s in body.content.sub_questions or [])
        case "blank":
            return body.content.blank_count or 1
        case _:
            return 1


async def grade(
    subject: str, body: QuestionBody, answer: StudentAnswer, max_score: float
) -> Grading:
    """出错时抛 AppError；作答的结构和题型对不上抛 ValueError（应在入口校验）。"""
    if body.type == "essay":
        raise ValueError("作文批改是加分项（PRC-05），还没有做")
    if body.type == "solution":
        grading = await _grade_solution(body, _expect(answer, TextInput))
    else:
        grading = await _grade_objective(subject, body, answer)
    return _scaled(grading, max_score)


@dataclass
class _Blank:
    key: str
    max_score: float
    answers: list[str]
    given: str
    # None 表示规则判断不了，交给模型
    correct: bool | None
    confidence: float = 1.0


async def _grade_objective(subject: str, body: QuestionBody, answer: StudentAnswer) -> Grading:
    parts: list[GradingItem | _Blank] = []
    if body.type in ("cloze", "reading"):
        given = {item.seq: item for item in _expect(answer, SubInput).sub}
        correct = {item.seq: item for item in body.answer.sub}
        for sub in body.content.sub_questions:
            parts += _parts(
                subject,
                f"sub_{sub.seq}",
                sub.type,
                sub.score,
                correct[sub.seq],
                given.get(sub.seq, SubInputItem(seq=sub.seq)),
            )
    else:
        expected = {
            "single": ChoiceInput,
            "multiple": ChoiceInput,
            "judge": JudgeInput,
            "blank": BlanksInput,
        }[body.type]
        given = _expect(answer, expected)
        parts += _parts(subject, "answer", body.type, natural_score(body), body.answer, given)

    pending = [p for p in parts if isinstance(p, _Blank) and p.correct is None]
    if pending:
        await _judge_blanks(subject, body, pending)
    items = [
        GradingItem(
            key=p.key,
            result="correct" if p.correct else "wrong",
            score=p.max_score if p.correct else 0,
            max_score=p.max_score,
        )
        if isinstance(p, _Blank)
        else p
        for p in parts
    ]
    blanks = [p for p in parts if isinstance(p, _Blank)]
    return Grading(
        result=_result(items),
        score=sum(i.score for i in items),
        max_score=sum(i.max_score for i in items),
        detail=GradingDetail(
            confidence=min((b.confidence for b in blanks), default=1.0), items=items
        ),
        graded_by="ai" if pending else "rule",
    )


def _parts(subject, key, type_, max_score, correct, given) -> list[GradingItem | _Blank]:
    """一道小题（或不带小题的整道题）拆成判分项；correct、given 都按字段名取作答。"""
    match type_:
        case "single" | "multiple":
            ratio = _choice_ratio(correct.choice, given.choice or [], type_ == "multiple")
            return [_item(key, ratio, max_score)]
        case "judge":
            right = given.judge is not None and given.judge == correct.judge
            return [_item(key, float(right), max_score)]
        case _:
            each = max_score / len(correct.blanks)
            texts = given.blanks or []
            prefix = "" if key == "answer" else f"{key}_"
            parts = []
            for i, answers in enumerate(correct.blanks):
                text = texts[i] if i < len(texts) else ""
                match = _match_blank(subject, answers, text)
                parts.append(_Blank(f"{prefix}blank_{i + 1}", each, answers, text, match))
            return parts


def _choice_ratio(correct: list[str], given: list[str], multiple: bool) -> float:
    if set(given) == set(correct):
        return 1
    # 多选：少选得一半，错选得 0
    if multiple and given and set(given) < set(correct):
        return 0.5
    return 0


def _item(key: str, ratio: float, max_score: float) -> GradingItem:
    result = "correct" if ratio == 1 else "wrong" if ratio == 0 else "partial"
    return GradingItem(key=key, result=result, score=ratio * max_score, max_score=max_score)


def _match_blank(subject: str, answers: list[str], given: str) -> bool | None:
    text = _normalize(given)
    if not text:
        return False
    if any(_normalize(a) == text for a in answers):
        return True
    if subject == "english":
        return None
    expr = _expr(text)
    if expr is None:
        return None
    others = [_expr(_normalize(a)) for a in answers]
    if any(o is not None and _equal(expr, o) for o in others):
        return True
    # 都是不带字母的数还不相等，肯定是错的；带字母的可能是单位写法不同，交给模型
    if not expr.free_symbols and all(o is not None and not o.free_symbols for o in others):
        return False
    return None


_FULL_WIDTH = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)} | {0x3000: 0x20}


def _normalize(text: str) -> str:
    """全角转半角，去掉空白和公式的 $。不用 NFKC：它会把 ² 变成 2。"""
    return re.sub(r"[\s$]", "", text.translate(_FULL_WIDTH))


_LATEX = [
    (r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))"),
    (r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)"),
    (r"\\(times|cdot)", "*"),
    (r"\\div", "/"),
    (r"\\pi", "pi"),
    (r"\\left|\\right", ""),
]
_OPERATORS = str.maketrans(
    {
        "×": "*",
        "·": "*",
        "÷": "/",
        "−": "-",
        "π": "pi",
        "√": "sqrt",
        "²": "^2",
        "³": "^3",
        "{": "(",
        "}": ")",
    }
)
_EXPR_CHARS = re.compile(r"[0-9A-Za-z.+\-*/^()]{1,40}")
# parse_expr 内部用 eval，学生的输入只放行单个字母、sqrt、pi，所有字母都映射成普通符号
_SYMBOLS = {c: sympy.Symbol(c) for c in string.ascii_letters}
_TRANSFORMS = (*standard_transformations, implicit_multiplication_application, convert_xor)


def _expr(text: str) -> sympy.Expr | None:
    for pattern, repl in _LATEX:
        text = re.sub(pattern, repl, text)
    text = text.translate(_OPERATORS)
    text = re.sub(r"sqrt(\d+(?:\.\d+)?|[A-Za-z])", r"sqrt(\1)", text)
    if not _EXPR_CHARS.fullmatch(text):
        return None
    if any(len(name) > 1 and name not in ("sqrt", "pi") for name in re.findall(r"[A-Za-z]+", text)):
        return None
    # 防止 9^9^9 这种算不完的数
    if text.count("^") + text.count("**") > 1 or re.search(r"\^\(?\d{4}|\d{10}", text):
        return None
    try:
        expr = parse_expr(text, local_dict=dict(_SYMBOLS), transformations=_TRANSFORMS)
    except Exception:
        return None
    return expr if isinstance(expr, sympy.Expr) else None


def _equal(a: sympy.Expr, b: sympy.Expr) -> bool:
    try:
        return sympy.simplify(a - b) == 0
    except Exception:
        return False


async def _judge_blanks(subject: str, body: QuestionBody, blanks: list[_Blank]) -> None:
    question = _question_json(subject, body)
    asked = [{"seq": i, "answers": b.answers, "given": b.given} for i, b in enumerate(blanks, 1)]
    messages = [
        {"role": "system", "content": prompts.load("grading/blank")},
        {
            "role": "user",
            "content": f"题目：{question}\n\n要判断的空：{json.dumps(asked, ensure_ascii=False)}",
        },
    ]
    verdicts = await complete_json(
        "grading_blank", Model.REASONING, messages, BlankVerdicts, context={"count": len(blanks)}
    )
    for verdict in verdicts.blanks:
        blank = blanks[verdict.seq - 1]
        blank.correct = verdict.correct
        blank.confidence = verdict.confidence


async def _grade_solution(body: QuestionBody, answer: TextInput) -> Grading:
    points = body.scoring_points or []
    if not answer.text.strip():
        items = [_item(f"point_{i}", 0, p.score) for i, p in enumerate(points, 1)]
        return Grading(
            result="wrong",
            score=0,
            max_score=sum(p.score for p in points),
            detail=GradingDetail(confidence=1, items=items, summary="没有作答"),
            graded_by="rule",
        )
    question = {
        "题目": body.content.model_dump(exclude_none=True, exclude={"images"}),
        "参考答案": body.answer.model_dump(exclude_none=True),
        "解析": [s.model_dump() for s in body.analysis],
        "评分要点": [{"seq": i, **p.model_dump()} for i, p in enumerate(points, 1)],
    }
    messages = [
        {
            "role": "system",
            "content": f"{prompts.load('grading/solution')}\n\n{prompts.load('format')}",
        },
        {
            "role": "user",
            "content": f"{json.dumps(question, ensure_ascii=False)}\n\n学生作答：\n{answer.text}",
        },
    ]
    graded = await complete_json(
        "grading_solution",
        Model.REASONING,
        messages,
        SolutionGrading,
        context={"max_scores": [p.score for p in points]},
    )
    items = [
        GradingItem(
            key=f"point_{s.seq}",
            result="correct" if s.score == p.score else "wrong" if s.score == 0 else "partial",
            score=s.score,
            max_score=p.score,
            comment=s.comment or None,
        )
        for s, p in zip(graded.points, points, strict=True)
    ]
    result = _result(items)
    return Grading(
        result=result,
        score=sum(i.score for i in items),
        max_score=sum(i.max_score for i in items),
        detail=GradingDetail(confidence=graded.confidence, items=items, summary=graded.summary),
        graded_by="ai",
        error_reason=None if result == "correct" else graded.error_reason,
    )


def _result(items: list[GradingItem]) -> Result:
    score = sum(i.score for i in items)
    if score >= sum(i.max_score for i in items):
        return "correct"
    return "wrong" if score == 0 else "partial"


def _scaled(grading: Grading, max_score: float) -> Grading:
    """按题目在作业里的分值换算，分数保留 1 位小数。"""
    factor = max_score / grading.max_score
    items = [
        i.model_copy(
            update={
                "score": round(i.score * factor, 1),
                "max_score": round(i.max_score * factor, 1),
            }
        )
        for i in grading.detail.items
    ]
    grading.detail.items = items
    grading.score = round(grading.score * factor, 1)
    grading.max_score = max_score
    return grading


async def solve(subject: str, type: str, content: QuestionContent) -> QuestionBody:
    """拍照识别出来的题没有答案：先由模型解出答案、解析（解答题还有评分要点），再拿来判分。"""
    data = content.model_dump(exclude_none=True)
    messages = [
        {
            "role": "system",
            "content": f"{prompts.load('grading/solve')}\n\n{prompts.load('format')}",
        },
        {
            "role": "user",
            "content": json.dumps(
                {"学科": subject, "题型": type, "题目": data}, ensure_ascii=False
            ),
        },
    ]
    solved = await complete_json(
        "grading_solve", Model.REASONING, messages, Solved, context={"type": type, "content": data}
    )
    return solved.to_body(type, data)


def _question_json(subject: str, body: QuestionBody) -> str:
    content = body.content.model_dump(exclude_none=True, exclude={"images"})
    return json.dumps({"学科": subject, "题型": body.type, **content}, ensure_ascii=False)


def _expect[T](answer: object, cls: type[T]) -> T:
    if not isinstance(answer, cls):
        raise ValueError("作答的结构和题型不一致")
    return answer

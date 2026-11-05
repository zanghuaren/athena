"""错题本（MIS）：入本、列表、详情、标记已掌握；复习调度见技术方案 7.2。"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import get_args

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.ai import prompts
from app.ai.client import Model, complete_json
from app.errors import AppError
from app.models import (
    Attempt,
    Chapter,
    Conversation,
    KnowledgePoint,
    Message,
    Mistake,
    Question,
    QuestionKnowledgePoint,
    Scan,
    ScanItem,
    User,
)
from app.schemas.knowledge import KnowledgePointBrief
from app.schemas.mistake import (
    AskMistakeIn,
    Extracted,
    ManualMistakeIn,
    MistakePatch,
    MistakeTip,
    QuestionDraft,
)
from app.schemas.question import QuestionBody
from app.schemas.user import Subject
from app.services import grading, knowledge, questions

logger = logging.getLogger(__name__)

# 复习按北京时间的自然日算；中国没有夏令时，固定 +8 即可
BEIJING = timezone(timedelta(hours=8))
WRONG_RESULTS = ("wrong", "partial")
# 批量加入时同时生成提示的模型调用数，和整页批改一样受账户并发限制
_CONCURRENCY = 4


def today() -> date:
    return datetime.now(BEIJING).date()


def _restart(mistake: Mistake) -> None:
    """入本、再次做错、恢复复习：回到第 0 档，明天复习。"""
    mistake.status = "pending"
    mistake.review_stage = 0
    mistake.next_review_on = today() + timedelta(days=1)


def _with_question(query: Select) -> Select:
    return query.options(
        selectinload(Mistake.question).selectinload(Question.knowledge_points),
        selectinload(Mistake.last_attempt),
    )


async def add_from_scan(
    db: AsyncSession, user: User, scan_id: int, seqs: list[int]
) -> list[Mistake]:
    """拍照批改里做错、部分对的题加入错题本；已经在本里的保留原来的复习进度。"""
    scan = await db.get(Scan, scan_id)
    if scan is None or scan.student_id != user.id:
        raise AppError(404, "NOT_FOUND", "批改记录不存在或已被删除")
    items = list(
        await db.scalars(
            select(ScanItem)
            .where(ScanItem.scan_id == scan_id, ScanItem.seq.in_(seqs))
            .order_by(ScanItem.seq)
            .options(selectinload(ScanItem.question), selectinload(ScanItem.attempt))
        )
    )
    if len(items) != len(set(seqs)):
        raise AppError(404, "NOT_FOUND", "这道题不存在")
    if any(i.attempt is None or i.attempt.result not in WRONG_RESULTS for i in items):
        raise AppError(400, "VALIDATION_ERROR", "只能加入做错的题")

    question_ids = [i.question_id for i in items]
    existing = set(
        await db.scalars(
            select(Mistake.question_id).where(
                Mistake.student_id == user.id, Mistake.question_id.in_(question_ids)
            )
        )
    )
    new_items = [i for i in items if i.question_id not in existing]
    limit = asyncio.Semaphore(_CONCURRENCY)

    async def tip(item: ScanItem) -> MistakeTip | None:
        async with limit:
            return await _tip(item.question, item.attempt)

    tips = await asyncio.gather(*(tip(i) for i in new_items))
    for item, made in zip(new_items, tips, strict=True):
        mistake = Mistake(
            student_id=user.id,
            question_id=item.question_id,
            source="scan",
            last_attempt_id=item.attempt_id,
            error_reason=item.attempt.error_reason or (made and made.error_reason),
            tip=made and made.tip,
        )
        _restart(mistake)
        db.add(mistake)
    await db.commit()
    result = await db.scalars(
        _with_question(
            select(Mistake).where(
                Mistake.student_id == user.id, Mistake.question_id.in_(question_ids)
            )
        )
    )
    order = {q: i for i, q in enumerate(question_ids)}
    return sorted(result, key=lambda m: order[m.question_id])


# ---- 答疑加入、手动添加 ----

# 提取题目时带上的最近几条消息：引导式讲解里，原题常在几轮之前
_CONTEXT_MESSAGES = 8


async def _owned_reply(
    db: AsyncSession, user: User, message_id: int
) -> tuple[Message, Conversation]:
    row = (
        await db.execute(
            select(Message, Conversation)
            .join(Conversation)
            .where(
                Message.id == message_id,
                Message.role == "assistant",
                Conversation.user_id == user.id,
            )
        )
    ).first()
    if row is None:
        raise AppError(404, "NOT_FOUND", "消息不存在或已被删除")
    message, conversation = row
    return message, conversation


async def extract_question(
    db: AsyncSession, user: User, message_id: int
) -> tuple[QuestionDraft, int | None]:
    """从这条讲解所在的对话里提取题目（MODEL_FAST），交给学生确认；不入库。

    这条讲解已经提取过（加入过错题本）时直接返回那道题和对应的错题。
    """
    message, conversation = await _owned_reply(db, user, message_id)
    if message.question_id is not None:
        question = await db.scalar(
            select(Question)
            .where(Question.id == message.question_id)
            .options(selectinload(Question.knowledge_points))
        )
        added = await of_questions(db, user, [question.id])
        draft = QuestionDraft(
            **grading.question_body(question).model_dump(),
            subject=question.subject,
            knowledge_points=question.knowledge_points,
        )
        return draft, added.get(question.id)

    history = list(
        await db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.id <= message.id,
                Message.status != "blocked",
            )
            .order_by(Message.id.desc())
            .limit(_CONTEXT_MESSAGES)
        )
    )[::-1]
    subjects = [conversation.subject] if conversation.subject else list(get_args(Subject))
    catalogs = {s: await knowledge.catalog(db, s) for s in subjects}
    dialog = [f"更早的对话摘要：{conversation.summary}"] if conversation.summary else []
    dialog += [f"{'学生' if m.role == 'user' else 'AI 助教'}：{m.content}" for m in history]
    points = "\n\n".join(
        f"{s}：\n" + "\n".join(f"{code} {name}" for code, (_, name) in c.items())
        for s, c in catalogs.items()
    )
    messages = [
        {
            "role": "system",
            "content": f"{prompts.load('mistakes/extract')}\n\n{prompts.load('format')}",
        },
        {"role": "user", "content": "\n\n".join(dialog) + f"\n\n知识点目录：\n{points}"},
    ]
    extracted = await complete_json(
        "mistake_extract",
        Model.FAST,
        messages,
        Extracted,
        context={"codes": {s: set(c) for s, c in catalogs.items()}},
    )
    if extracted.status == "none":
        raise AppError(400, "NO_QUESTION_FOUND", "这段讲解里没有找到具体的题目")
    found = {
        p.code: p
        for p in await db.scalars(
            select(KnowledgePoint).where(KnowledgePoint.code.in_(extracted.knowledge_points))
        )
    }
    draft = QuestionDraft(
        **extracted.question.model_dump(),
        subject=extracted.subject,
        knowledge_points=[
            KnowledgePointBrief.model_validate(found[c]) for c in extracted.knowledge_points
        ],
    )
    return draft, None


async def add(db: AsyncSession, user: User, body: AskMistakeIn | ManualMistakeIn) -> Mistake:
    """答疑里确认过的题、手动添加的题加入错题本；同一道题已经在本里时不改动。"""
    my_answer = None
    if isinstance(body, AskMistakeIn):
        message, _ = await _owned_reply(db, user, body.message_id)
        if message.question_id is None:
            data = body.question
            content = QuestionBody.model_validate(
                data.model_dump(exclude={"subject", "knowledge_point_ids"})
            )
            question = await _create_question(
                db, user, "ask", data.subject, content, data.knowledge_point_ids
            )
            message.question_id = question.id
        else:
            question = await db.get_one(Question, message.question_id)
    else:
        content = QuestionBody(
            type="solution",
            content={"stem": body.stem},
            answer={"text": body.answer},
            analysis=[{"title": "参考答案", "body": body.answer}],
            scoring_points=[{"point": "答案正确", "score": 1}],
            difficulty=3,
        )
        question = await _create_question(
            db, user, "manual", body.subject, content, body.knowledge_point_ids
        )
        my_answer = body.my_answer.strip() or None

    mistake = await db.scalar(
        select(Mistake).where(Mistake.student_id == user.id, Mistake.question_id == question.id)
    )
    if mistake is None:
        made = await _tip(question, None, my_answer)
        mistake = Mistake(
            student_id=user.id,
            question_id=question.id,
            source=body.source,
            my_answer=my_answer,
            error_reason=made and made.error_reason,
            tip=made and made.tip,
        )
        _restart(mistake)
        db.add(mistake)
    await db.commit()
    return await get_owned(db, user, mistake.id)


async def _create_question(
    db: AsyncSession,
    user: User,
    source: str,
    subject: str,
    body: QuestionBody,
    point_ids: list[int],
) -> Question:
    found = set(
        await db.scalars(
            select(KnowledgePoint.id)
            .join(Chapter)
            .where(KnowledgePoint.id.in_(point_ids), Chapter.subject == subject)
        )
    )
    if found != set(point_ids):
        raise AppError(400, "VALIDATION_ERROR", "知识点不存在或不属于这个学科")
    question = Question(subject=subject, source=source, owner_id=user.id, **questions.columns(body))
    db.add(question)
    await db.flush()
    questions.link_points(db, question.id, point_ids)
    return question


async def _tip(
    question: Question, attempt: Attempt | None, my_answer: str | None = None
) -> MistakeTip | None:
    """一句话提示和错因，用 MODEL_FAST；模型出错时返回 None，不影响入本。"""
    body = grading.question_body(question)
    data = {
        "学科": question.subject,
        "题型": question.type,
        "题目": body.content.model_dump(exclude_none=True, exclude={"images"}),
        "参考答案": body.answer.model_dump(exclude_none=True),
        "解析": [s.model_dump() for s in body.analysis],
    }
    if attempt is not None:
        data["学生作答"] = attempt.answer
        summary = (attempt.grading_detail or {}).get("summary")
        if summary:
            data["批改意见"] = summary
    elif my_answer:
        data["学生作答"] = my_answer
    messages = [
        {
            "role": "system",
            "content": f"{prompts.load('mistakes/tip')}\n\n{prompts.load('format')}",
        },
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
    ]
    try:
        return await complete_json("mistake_tip", Model.FAST, messages, MistakeTip)
    except AppError as exc:
        if exc.code not in grading.AI_ERRORS:
            raise
        logger.warning("mistake tip question=%s skipped: %s", question.id, exc.code)
        return None


async def of_questions(db: AsyncSession, user: User, question_ids: list[int]) -> dict[int, int]:
    """这些题里已经在错题本里的：题目 ID → 错题 ID。"""
    rows = await db.execute(
        select(Mistake.question_id, Mistake.id).where(
            Mistake.student_id == user.id, Mistake.question_id.in_(question_ids)
        )
    )
    return {question_id: mistake_id for question_id, mistake_id in rows}


async def list_page(
    db: AsyncSession,
    user: User,
    *,
    subject: str | None,
    knowledge_point_id: int | None,
    source: str | None,
    status: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[Mistake], int]:
    query = select(Mistake).where(Mistake.student_id == user.id)
    if subject is not None:
        query = query.join(Question).where(Question.subject == subject)
    if knowledge_point_id is not None:
        query = query.where(
            exists().where(
                QuestionKnowledgePoint.question_id == Mistake.question_id,
                QuestionKnowledgePoint.knowledge_point_id == knowledge_point_id,
            )
        )
    if source is not None:
        query = query.where(Mistake.source == source)
    if status is not None:
        query = query.where(Mistake.status == status)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    order = [Mistake.created_at.desc(), Mistake.id.desc()]
    if sort == "wrong_count":
        order.insert(0, Mistake.wrong_count.desc())
    result = await db.scalars(
        _with_question(query.order_by(*order).offset((page - 1) * page_size).limit(page_size))
    )
    return list(result), total or 0


async def get_owned(db: AsyncSession, user: User, mistake_id: int) -> Mistake:
    mistake = await db.scalar(
        _with_question(
            select(Mistake).where(Mistake.id == mistake_id, Mistake.student_id == user.id)
        )
    )
    if mistake is None:
        raise AppError(404, "NOT_FOUND", "错题不存在或已移出错题本")
    return mistake


async def update(db: AsyncSession, user: User, mistake_id: int, body: MistakePatch) -> Mistake:
    mistake = await get_owned(db, user, mistake_id)
    fields = body.model_fields_set
    if "error_reason" in fields:
        mistake.error_reason = body.error_reason
    if "note" in fields:
        mistake.note = body.note or None
    if body.status == "mastered":
        mistake.status = "mastered"
        mistake.next_review_on = None
    elif body.status == "pending" and mistake.status == "mastered":
        _restart(mistake)
    await db.commit()
    return await get_owned(db, user, mistake_id)


async def delete(db: AsyncSession, user: User, mistake_id: int) -> None:
    await db.delete(await get_owned(db, user, mistake_id))
    await db.commit()

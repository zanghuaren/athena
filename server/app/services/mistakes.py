"""错题本（MIS）：入本、列表、详情、标记已掌握；复习调度见技术方案 7.2。"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.ai import prompts
from app.ai.client import Model, complete_json
from app.errors import AppError
from app.models import Attempt, Mistake, Question, QuestionKnowledgePoint, Scan, ScanItem, User
from app.schemas.mistake import MistakePatch, MistakeTip
from app.services import grading

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
    return dict(rows.tuples().all())


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

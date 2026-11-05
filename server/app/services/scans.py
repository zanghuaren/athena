"""拍照识题与批改（SCAN），技术方案 5.4。"""

import asyncio
import io
import json
import logging
import re

import anyio
from PIL import Image
from pydantic import TypeAdapter
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai import prompts
from app.ai.client import Model, complete_json
from app.db import SessionLocal
from app.errors import AppError
from app.models import (
    Attempt,
    Chapter,
    File,
    Job,
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    Scan,
    ScanItem,
    User,
)
from app.schemas.attempt import (
    BlanksInput,
    ChoiceInput,
    JudgeInput,
    StudentAnswer,
    SubInput,
    TextInput,
    check_answer,
)
from app.schemas.question import QuestionBody, QuestionContent
from app.schemas.scan import (
    AnswerRecognized,
    PageQuestion,
    PageRecognized,
    Recognized,
    RecognizeOut,
    RegradeIn,
    check_content,
)
from app.services import files, grading, jobs

logger = logging.getLogger(__name__)


async def recognize(db: AsyncSession, user: User, image_file_id: int) -> RecognizeOut:
    image = await files.get_owned(db, user, image_file_id)
    messages = [
        {"role": "system", "content": prompts.load("scan/recognize")},
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": await files.data_url(image)}}],
        },
    ]
    result = await complete_json("scan_recognize", Model.VISION, messages, Recognized)
    if result.status == "empty":
        raise AppError(400, "NO_QUESTION_FOUND", "没有识别到题目")
    if result.status == "multiple":
        raise AppError(400, "MULTIPLE_QUESTIONS", "请只框选一道题")
    return RecognizeOut(subject=result.subject, text=_table_separators(result.text.strip()))


_SEPARATOR = re.compile(r"\|(\s*:?-+:?\s*\|)+")


def _table_separators(text: str) -> str:
    # 提示词里要求了，模型仍常漏掉表头下面的分隔行，Markdown 就不把它当表格
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        header = line.startswith("|") and (i == 0 or not lines[i - 1].startswith("|"))
        below = lines[i + 1] if i + 1 < len(lines) else ""
        if header and below.startswith("|") and not _SEPARATOR.fullmatch(below.strip()):
            out.append("|" + " --- |" * (line.count("|") - 1))
    return "\n".join(out)


# ---- 整页批改（SCAN-03），技术方案 5.4 ----

MAX_QUESTIONS = 20
MIN_SIDE = 1000
MIN_CONFIDENCE = 0.6
# 一次批改里同时调用模型的上限
_CONCURRENCY = 6
_UNCLEAR = "照片不清楚。请在光线充足的地方把作业平铺，手机正对纸面，一次拍一页"


async def create(db: AsyncSession, user: User, image_file_id: int) -> tuple[Scan, Job]:
    image = await files.get_owned(db, user, image_file_id)
    scan = Scan(student_id=user.id, image_file_id=image.id, image_file=image)
    db.add(scan)
    await db.flush()
    job = jobs.enqueue(db, user, "scan_grading", {"scan_id": scan.id})
    await db.flush()
    scan.job_id = job.id
    await db.commit()
    await db.refresh(scan)
    return scan, job


async def list_page(
    db: AsyncSession, user: User, page: int, page_size: int
) -> tuple[list[Scan], int]:
    query = select(Scan).where(Scan.student_id == user.id)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.scalars(
        query.order_by(Scan.created_at.desc(), Scan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result), total or 0


async def get_owned(db: AsyncSession, user: User, scan_id: int) -> Scan:
    scan = await db.get(Scan, scan_id)
    if scan is None or scan.student_id != user.id:
        raise AppError(404, "NOT_FOUND", "批改记录不存在或已被删除")
    return scan


async def items_of(db: AsyncSession, scan_id: int) -> list[ScanItem]:
    result = await db.scalars(
        select(ScanItem)
        .where(ScanItem.scan_id == scan_id)
        .order_by(ScanItem.seq)
        .options(
            selectinload(ScanItem.question).selectinload(Question.knowledge_points),
            selectinload(ScanItem.attempt),
        )
    )
    return list(result)


async def grade_page(db: AsyncSession, job: Job) -> None:
    """整页批改任务：识别题目 → 识别作答 → 逐题解题和判分。"""
    scan = await db.get_one(Scan, job.payload["scan_id"])
    # 任务重试时从头再来，先删掉上一次生成的题目（作答记录和 scan_items 随之级联删除）
    await db.execute(
        delete(Question).where(
            Question.id.in_(select(ScanItem.question_id).where(ScanItem.scan_id == scan.id))
        )
    )
    await jobs.set_stage(db, job, "recognize_questions", 5)
    image = await db.get_one(File, scan.image_file_id)
    page = await _recognize_page(image)
    questions = page.questions[:MAX_QUESTIONS]
    scan.subject = page.subject
    scan.truncated = len(page.questions) > MAX_QUESTIONS

    await jobs.set_stage(db, job, "recognize_answers", 30)
    limit = asyncio.Semaphore(_CONCURRENCY)
    photo = await files.read(image)
    answers = await asyncio.gather(*(_recognize_answer(limit, photo, q) for q in questions))

    await jobs.set_stage(db, job, "grade_questions", 60)
    student = await db.get_one(User, scan.student_id)
    catalog = await _catalog(db, page.subject)
    done = 0

    async def grade_one(seq: int, question: PageQuestion, answer: AnswerRecognized | None):
        nonlocal done
        await _grade_item(limit, student, scan.id, seq, question, answer, catalog, page.subject)
        done += 1
        await jobs.report_progress(job.id, 60 + 35 * done // len(questions))

    async with asyncio.TaskGroup() as group:
        for seq, (question, answer) in enumerate(zip(questions, answers, strict=True), 1):
            group.create_task(grade_one(seq, question, answer))
    await _summarize(db, scan)
    scan.status = "done"
    await db.commit()


async def mark_failed(db: AsyncSession, job: Job) -> None:
    scan = await db.get_one(Scan, job.payload["scan_id"])
    scan.status = "failed"
    scan.fail_reason = {"PHOTO_UNCLEAR": "unclear", "NO_QUESTION_FOUND": "no_question"}.get(
        job.error["code"], "error"
    )


async def _recognize_page(image: File) -> PageRecognized:
    if min(image.width or 0, image.height or 0) < MIN_SIDE:
        raise AppError(400, "PHOTO_UNCLEAR", _UNCLEAR)
    messages = [
        {"role": "system", "content": prompts.load("scan/page")},
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": await files.data_url(image)}}],
        },
    ]
    page = await complete_json("scan_page", Model.VISION, messages, PageRecognized)
    if page.status == "unclear":
        raise AppError(400, "PHOTO_UNCLEAR", _UNCLEAR)
    if page.status == "empty" or not page.questions:
        raise AppError(400, "NO_QUESTION_FOUND", "没有识别到题目，请拍一页带题目的作业")
    return page


async def _recognize_answer(
    limit: asyncio.Semaphore, photo: bytes, question: PageQuestion
) -> AnswerRecognized | None:
    """看不清时返回 None；单道题识别失败不影响整页，这道题标“？”。"""
    crop = await anyio.to_thread.run_sync(_crop, photo, question.bbox)
    content = question.content.model_dump(exclude_none=True)
    info = json.dumps({"题型": question.type, "题目": content}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": prompts.load("scan/answer")},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": files.to_data_url(crop)}},
                {"type": "text", "text": info},
            ],
        },
    ]
    context = {"type": question.type, "content": question.content}
    try:
        async with limit:
            result = await complete_json(
                "scan_answer", Model.VISION, messages, AnswerRecognized, context=context
            )
    except AppError as exc:
        logger.warning("scan answer failed seq=%s: %s", question.seq, exc.code)
        return None
    if result.status != "ok" or _is_empty(result.answer):
        return None
    return result


def _is_empty(answer: StudentAnswer) -> bool:
    """整道题一点作答都没读到。

    作答常写在框外（双栏页面、写在题目旁边），按“？”让学生核对，不直接判 0 分。
    """
    match answer:
        case ChoiceInput(choice=choice):
            return not choice
        case JudgeInput(judge=judge):
            return judge is None
        case BlanksInput(blanks=blanks):
            return not any(b.strip() for b in blanks)
        case TextInput(text=text):
            return not text.strip()
        case SubInput(sub=sub):
            return all(
                not i.choice and i.judge is None and not any(b.strip() for b in i.blanks or [])
                for i in sub
            )


def _crop(photo: bytes, bbox: list[int]) -> bytes:
    # 模型给的框只是大致位置，双栏、倾斜的页面会偏半行到一行，上下多留半个框高（技术方案 5.4）
    image = Image.open(io.BytesIO(photo))
    x1, y1, x2, y2 = (v / 1000 for v in bbox)
    margin = max((y2 - y1) / 2, 0.04)
    box = (max(x1 - 0.03, 0), max(y1 - margin, 0), min(x2 + 0.03, 1), min(y2 + margin, 1))
    w, h = image.size
    out = io.BytesIO()
    image.crop((box[0] * w, box[1] * h, box[2] * w, box[3] * h)).save(out, "JPEG", quality=90)
    return out.getvalue()


async def _catalog(db: AsyncSession, subject: str) -> dict[str, tuple[int, str]]:
    """这个学科的知识点：编号 → (ID, 名称)。"""
    rows = await db.execute(
        select(KnowledgePoint.code, KnowledgePoint.id, KnowledgePoint.name)
        .join(Chapter)
        .where(Chapter.subject == subject)
        .order_by(KnowledgePoint.code)
    )
    return {code: (id_, name) for code, id_, name in rows}


async def _grade_item(
    limit: asyncio.Semaphore,
    student: User,
    scan_id: int,
    seq: int,
    page_question: PageQuestion,
    recognized: AnswerRecognized | None,
    catalog: dict[str, tuple[int, str]],
    subject: str,
) -> None:
    """解题、判分，各题并发执行，每题用自己的数据库会话。"""
    async with limit:
        body, codes = await grading.solve(
            subject,
            page_question.type,
            page_question.content,
            {code: name for code, (_, name) in catalog.items()},
        )
    confidence = page_question.confidence
    answer = None
    if recognized is not None:
        answer = recognized.answer
        confidence = min(confidence, recognized.confidence)
    async with SessionLocal() as db:
        question = Question(
            subject=subject, source="scan", owner_id=student.id, **_question_fields(body)
        )
        db.add(question)
        await db.flush()
        _link_points(db, question.id, [catalog[c][0] for c in codes])
        attempt = None
        if answer is not None and confidence >= MIN_CONFIDENCE:
            async with limit:
                attempt = await grading.record(db, student, question, answer, "scan", scan_id)
            await db.flush()
        x1, y1, x2, y2 = (v / 1000 for v in page_question.bbox)
        db.add(
            ScanItem(
                scan_id=scan_id,
                seq=seq,
                bbox={"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1},
                question_id=question.id,
                answer=answer.model_dump() if answer else None,
                attempt_id=attempt.id if attempt else None,
                confidence=confidence,
            )
        )
        await db.commit()


def _question_fields(body: QuestionBody) -> dict:
    data = body.model_dump(exclude_none=True)
    content = body.content
    text = "\n".join(
        [content.stem, *(o.text for o in content.options or []), content.material or ""]
    )
    return {
        "type": body.type,
        "content": data["content"],
        "answer": data["answer"],
        "analysis": data["analysis"],
        "scoring_points": data.get("scoring_points"),
        "difficulty": body.difficulty,
        "content_text": text.strip(),
    }


def _link_points(db: AsyncSession, question_id: int, point_ids: list[int]) -> None:
    db.add_all(
        QuestionKnowledgePoint(question_id=question_id, knowledge_point_id=i) for i in point_ids
    )


async def _summarize(db: AsyncSession, scan: Scan) -> None:
    rows = (
        await db.execute(
            select(Attempt.result, Attempt.grading_status)
            .select_from(ScanItem)
            .outerjoin(Attempt, ScanItem.attempt_id == Attempt.id)
            .where(ScanItem.scan_id == scan.id)
        )
    ).all()
    scan.total = len(rows)
    scan.correct = sum(result == "correct" for result, _ in rows)
    # 没有作答记录（“？”）和待判分的都不计入正确率
    scan.unknown = sum(status != "graded" for _, status in rows)


# ---- 修改识别结果后重批、“？”题自己确认 ----


async def _done_item(db: AsyncSession, user: User, scan_id: int, seq: int) -> tuple[Scan, ScanItem]:
    scan = await get_owned(db, user, scan_id)
    if scan.status != "done":
        raise AppError(409, "CONFLICT", "这次批改还没有完成")
    item = await db.scalar(
        select(ScanItem)
        .where(ScanItem.scan_id == scan_id, ScanItem.seq == seq)
        .options(selectinload(ScanItem.question), selectinload(ScanItem.attempt))
    )
    if item is None:
        raise AppError(404, "NOT_FOUND", "这道题不存在")
    return scan, item


async def request_regrade(
    db: AsyncSession, user: User, scan_id: int, seq: int, body: RegradeIn
) -> Job:
    _, item = await _done_item(db, user, scan_id, seq)
    question = item.question
    content = body.content or QuestionContent.model_validate(question.content)
    try:
        check_content(question.type, content)
        check_answer(question.type, content, body.answer)
    except ValueError as exc:
        raise AppError(400, "VALIDATION_ERROR", str(exc)) from exc
    payload = {
        "scan_id": scan_id,
        "seq": seq,
        "answer": body.answer.model_dump(),
        "content": body.content.model_dump(exclude_none=True) if body.content else None,
    }
    job = jobs.enqueue(db, user, "regrade", payload)
    await db.commit()
    return job


async def regrade(db: AsyncSession, job: Job) -> None:
    """重批任务：改了题目就重新解题，再按学生改过的作答判分，覆盖原来的作答记录。"""
    scan = await db.get_one(Scan, job.payload["scan_id"])
    item = await db.scalar(
        select(ScanItem)
        .where(ScanItem.scan_id == scan.id, ScanItem.seq == job.payload["seq"])
        .options(selectinload(ScanItem.question), selectinload(ScanItem.attempt))
    )
    question = item.question
    student = await db.get_one(User, scan.student_id)
    await jobs.set_stage(db, job, "regrade", 10)
    if job.payload["content"] is not None:
        catalog = await _catalog(db, question.subject)
        body, codes = await grading.solve(
            question.subject,
            question.type,
            QuestionContent.model_validate(job.payload["content"]),
            {code: name for code, (_, name) in catalog.items()},
        )
        for key, value in _question_fields(body).items():
            setattr(question, key, value)
        await db.execute(
            delete(QuestionKnowledgePoint).where(QuestionKnowledgePoint.question_id == question.id)
        )
        _link_points(db, question.id, [catalog[c][0] for c in codes])
    old, item.attempt = item.attempt, None
    if old is not None:
        await db.delete(old)
    answer = TypeAdapter(StudentAnswer).validate_python(job.payload["answer"])
    item.attempt = await grading.record(db, student, question, answer, "scan", scan.id)
    item.answer = answer.model_dump()
    # 学生自己核对过，不再是“？”
    item.confidence = 1
    await _summarize(db, scan)
    await db.commit()


async def confirm(db: AsyncSession, user: User, scan_id: int, seq: int, result: str) -> None:
    scan, item = await _done_item(db, user, scan_id, seq)
    if item.attempt is not None:
        raise AppError(409, "CONFLICT", "这道题已经有批改结果")
    max_score = grading.natural_score(grading.question_body(item.question))
    attempt = Attempt(
        student_id=user.id,
        question_id=item.question_id,
        source="scan",
        source_id=scan.id,
        answer=item.answer or {},
        grading_status="graded",
        result=result,
        score=max_score if result == "correct" else 0,
        max_score=max_score,
        grading_detail={"confidence": 1, "items": [], "summary": "学生自己确认"},
        graded_by="student",
        counted_at=func.now(),
    )
    item.attempt = attempt
    await db.flush()
    await _summarize(db, scan)
    await db.commit()

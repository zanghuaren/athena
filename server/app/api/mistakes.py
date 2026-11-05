from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from pydantic import TypeAdapter

from app.api.deps import CurrentStudent
from app.db import DB
from app.models import Mistake
from app.schemas.attempt import AttemptResult, StudentAnswer
from app.schemas.mistake import (
    MistakeBatchIn,
    MistakeBatchOut,
    MistakeDetail,
    MistakeOut,
    MistakePage,
    MistakePatch,
    MistakeSource,
    MistakeStatus,
)
from app.schemas.question import QuestionOut
from app.schemas.user import Subject
from app.services import mistakes

router = APIRouter(prefix="/mistakes", tags=["错题与复习"])

_answer = TypeAdapter(StudentAnswer)


@router.get("")
async def list_mistakes(
    db: DB,
    user: CurrentStudent,
    subject: Subject | None = None,
    knowledge_point_id: int | None = None,
    source: MistakeSource | None = None,
    status: MistakeStatus | None = None,
    sort: Literal["recent", "wrong_count"] = "recent",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MistakePage:
    items, total = await mistakes.list_page(
        db,
        user,
        subject=subject,
        knowledge_point_id=knowledge_point_id,
        source=source,
        status=status,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return MistakePage(items=[_out(m) for m in items], total=total, page=page, page_size=page_size)


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def add_from_scan(db: DB, user: CurrentStudent, body: MistakeBatchIn) -> MistakeBatchOut:
    added = await mistakes.add_from_scan(db, user, body.scan_id, body.seqs)
    return MistakeBatchOut(items=[_out(m) for m in added])


@router.get("/{mistake_id}")
async def get_mistake(db: DB, user: CurrentStudent, mistake_id: int) -> MistakeDetail:
    return _detail(await mistakes.get_owned(db, user, mistake_id))


@router.patch("/{mistake_id}")
async def update_mistake(
    db: DB, user: CurrentStudent, mistake_id: int, body: MistakePatch
) -> MistakeDetail:
    return _detail(await mistakes.update(db, user, mistake_id, body))


@router.delete("/{mistake_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mistake(db: DB, user: CurrentStudent, mistake_id: int) -> None:
    await mistakes.delete(db, user, mistake_id)


def _out(mistake: Mistake) -> MistakeOut:
    # 错题是学生自己做错过的题，答案和解析都可以看
    return MistakeOut(
        id=mistake.id,
        question=QuestionOut.model_validate(mistake.question),
        source=mistake.source,
        wrong_count=mistake.wrong_count,
        error_reason=mistake.error_reason,
        tip=mistake.tip,
        status=mistake.status,
        review_stage=mistake.review_stage,
        review_count=mistake.review_count,
        next_review_on=mistake.next_review_on,
        created_at=mistake.created_at,
    )


def _detail(mistake: Mistake) -> MistakeDetail:
    attempt = mistake.last_attempt
    return MistakeDetail(
        **_out(mistake).model_dump(),
        answer=_answer.validate_python(attempt.answer) if attempt else None,
        attempt=AttemptResult.model_validate(attempt) if attempt else None,
        my_answer=mistake.my_answer,
        note=mistake.note,
    )

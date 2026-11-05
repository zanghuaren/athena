from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentStudent
from app.db import DB
from app.models import Scan, ScanItem
from app.schemas.attempt import AttemptResult
from app.schemas.question import QuestionOut
from app.schemas.scan import (
    ConfirmIn,
    RecognizeIn,
    RecognizeOut,
    RegradeIn,
    RegradeOut,
    ScanCreated,
    ScanDetail,
    ScanIn,
    ScanItemOut,
    ScanOut,
    ScanPage,
)
from app.services import files, mistakes, scans

router = APIRouter(tags=["拍照识题与批改"])


@router.post("/recognize")
async def recognize(db: DB, user: CurrentStudent, body: RecognizeIn) -> RecognizeOut:
    return await scans.recognize(db, user, body.image_file_id)


@router.post("/scans", status_code=status.HTTP_201_CREATED)
async def create_scan(db: DB, user: CurrentStudent, body: ScanIn) -> ScanCreated:
    scan, job = await scans.create(db, user, body.image_file_id)
    return ScanCreated(scan=_scan_out(scan), job_id=job.id)


@router.get("/scans")
async def list_scans(
    db: DB,
    user: CurrentStudent,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScanPage:
    items, total = await scans.list_page(db, user, page, page_size)
    return ScanPage(
        items=[_scan_out(s) for s in items], total=total, page=page, page_size=page_size
    )


@router.get("/scans/{scan_id}")
async def get_scan(db: DB, user: CurrentStudent, scan_id: int) -> ScanDetail:
    scan = await scans.get_owned(db, user, scan_id)
    items = await scans.items_of(db, scan.id)
    added = await mistakes.of_questions(db, user, [i.question_id for i in items])
    return ScanDetail(**_scan_out(scan).model_dump(), items=[_item_out(i, added) for i in items])


@router.post("/scans/{scan_id}/items/{seq}/regrade", status_code=status.HTTP_202_ACCEPTED)
async def regrade_item(
    db: DB, user: CurrentStudent, scan_id: int, seq: int, body: RegradeIn
) -> RegradeOut:
    job = await scans.request_regrade(db, user, scan_id, seq, body)
    return RegradeOut(job_id=job.id)


@router.post("/scans/{scan_id}/items/{seq}/confirm")
async def confirm_item(
    db: DB, user: CurrentStudent, scan_id: int, seq: int, body: ConfirmIn
) -> ScanItemOut:
    await scans.confirm(db, user, scan_id, seq, body.result)
    item = next(i for i in await scans.items_of(db, scan_id) if i.seq == seq)
    return _item_out(item, await mistakes.of_questions(db, user, [item.question_id]))


def _scan_out(scan: Scan) -> ScanOut:
    return ScanOut(
        id=scan.id,
        status=scan.status,
        fail_reason=scan.fail_reason,
        subject=scan.subject,
        image=files.file_out(scan.image_file),
        job_id=scan.job_id,
        truncated=scan.truncated,
        total=scan.total,
        correct=scan.correct,
        unknown=scan.unknown,
        created_at=scan.created_at,
    )


def _item_out(item: ScanItem, added: dict[int, int]) -> ScanItemOut:
    # 拍照批改的题是学生自己的，批改完就能看答案和解析
    return ScanItemOut(
        seq=item.seq,
        bbox=item.bbox,
        confidence=item.confidence,
        question=QuestionOut.model_validate(item.question),
        answer=item.answer,
        attempt=AttemptResult.model_validate(item.attempt) if item.attempt else None,
        mistake_id=added.get(item.question_id),
    )

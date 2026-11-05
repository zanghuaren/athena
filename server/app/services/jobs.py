"""长任务：API 写入 jobs 表，Worker 取出执行，技术方案第 6 节、接口约定 2.2。"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import Job, User
from app.schemas.job import JobOut

MAX_TRIES = 3
# 第 1、2 次失败后分别等多久再重试
RETRY_DELAYS = (timedelta(seconds=10), timedelta(seconds=60))
STALE_AFTER = timedelta(minutes=10)
INTERNAL_ERROR = {"code": "INTERNAL_ERROR", "message": "处理失败，请稍后重试"}

STAGE_LABELS = {
    "recognize_questions": "识别题目",
    "recognize_answers": "识别作答",
    "grade_questions": "逐题批改",
}


def enqueue(db: AsyncSession, owner: User, type: str, payload: dict) -> Job:
    """和资源在同一个事务里提交，由调用方 commit。"""
    job = Job(owner_id=owner.id, type=type, payload=payload)
    db.add(job)
    return job


async def get(db: AsyncSession, user: User, job_id: int) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.owner_id != user.id:
        raise AppError(404, "NOT_FOUND", "任务不存在")
    return job


def job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        status=job.status,
        stage=job.stage,
        stage_label=STAGE_LABELS.get(job.stage) if job.stage else None,
        progress=job.progress,
        error=job.error,
    )


async def claim(db: AsyncSession) -> int | None:
    """取一个到期的任务并标为执行中，返回任务 ID。"""
    job = await db.scalar(
        select(Job)
        .where(Job.status == "queued", Job.run_after <= func.now())
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = "running"
    job.tries += 1
    job.started_at = func.now()
    await db.commit()
    return job.id


async def set_stage(db: AsyncSession, job: Job, stage: str, progress: int) -> None:
    job.stage = stage
    job.progress = progress
    await db.commit()


async def succeed(db: AsyncSession, job: Job) -> None:
    job.status = "succeeded"
    job.progress = 100
    job.finished_at = func.now()
    await db.commit()


def fail(job: Job, error: dict, retry: bool) -> bool:
    """记一次失败；还能重试就放回队列。返回是否最终失败，由调用方 commit。"""
    if retry and job.tries < MAX_TRIES:
        job.status = "queued"
        job.run_after = func.now() + RETRY_DELAYS[job.tries - 1]
        return False
    job.status = "failed"
    job.error = error
    job.finished_at = func.now()
    return True


async def stale(db: AsyncSession) -> list[Job]:
    """执行中但很久没有更新进度的任务，多半是 Worker 中途被重启了。"""
    result = await db.scalars(
        select(Job)
        .where(Job.status == "running", Job.updated_at < func.now() - STALE_AFTER)
        .with_for_update(skip_locked=True)
    )
    return list(result)

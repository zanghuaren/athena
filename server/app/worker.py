"""Worker 入口：python -m app.worker。循环从 jobs 表取任务执行，技术方案第 6 节。"""

import asyncio
import logging
import time

from app.db import SessionLocal
from app.errors import AppError
from app.jobs import HANDLERS
from app.models import Job
from app.services import jobs

logger = logging.getLogger("app.worker")

CONCURRENCY = 4
POLL_INTERVAL = 1
STALE_CHECK_INTERVAL = 60
# 网络和模型服务的临时问题才值得重试，业务错误重试结果也一样
_RETRYABLE = {"AI_TIMEOUT", "AI_UNAVAILABLE"}


async def main() -> None:
    running: set[asyncio.Task] = set()
    last_stale_check = 0.0
    while True:
        if time.monotonic() - last_stale_check > STALE_CHECK_INTERVAL:
            await fail_stale()
            last_stale_check = time.monotonic()
        while len(running) < CONCURRENCY and (job_id := await _claim()) is not None:
            task = asyncio.create_task(run_job(job_id))
            running.add(task)
            task.add_done_callback(running.discard)
        await asyncio.sleep(POLL_INTERVAL)


async def _claim() -> int | None:
    async with SessionLocal() as db:
        return await jobs.claim(db)


async def run_job(job_id: int) -> None:
    async with SessionLocal() as db:
        job = await db.get_one(Job, job_id)
        handler = HANDLERS[job.type]
        try:
            await handler.run(db, job)
        except Exception as exc:
            await db.rollback()
            await db.refresh(job)
            error, retry = _error(job, exc)
            if jobs.fail(job, error, retry):
                await handler.on_failed(db, job)
            await db.commit()
        else:
            await jobs.succeed(db, job)


def _error(job: Job, exc: Exception) -> tuple[dict, bool]:
    if isinstance(exc, AppError):
        logger.warning("job %s type=%s try=%s failed: %s", job.id, job.type, job.tries, exc.code)
        return {"code": exc.code, "message": exc.message}, exc.code in _RETRYABLE
    logger.exception("job %s type=%s try=%s crashed", job.id, job.type, job.tries)
    return jobs.INTERNAL_ERROR, True


async def fail_stale() -> None:
    async with SessionLocal() as db:
        for job in await jobs.stale(db):
            logger.warning("job %s type=%s stale", job.id, job.type)
            if jobs.fail(job, jobs.INTERNAL_ERROR, retry=True):
                await HANDLERS[job.type].on_failed(db, job)
        await db.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app import worker
from app.db import SessionLocal
from app.errors import AppError
from app.jobs import HANDLERS
from app.models import Job, User
from app.services import jobs


@pytest.fixture
async def owner(client, student) -> User:
    me = (await client.get("/api/v1/me", headers=student)).json()
    async with SessionLocal() as db:
        return await db.get_one(User, me["id"])


async def _enqueue(owner: User, payload: dict | None = None) -> int:
    async with SessionLocal() as db:
        job = jobs.enqueue(db, owner, "scan_grading", payload or {})
        await db.commit()
        return job.id


async def _claim() -> int | None:
    async with SessionLocal() as db:
        return await jobs.claim(db)


async def _job(job_id: int) -> Job:
    async with SessionLocal() as db:
        return await db.get_one(Job, job_id)


async def _make_due(job_id: int) -> None:
    async with SessionLocal() as db:
        await db.execute(update(Job).where(Job.id == job_id).values(run_after=func.now()))
        await db.commit()


@pytest.fixture
def failed_jobs(monkeypatch) -> list[int]:
    """登记一个测试用的处理函数：按 payload 里的 raise 抛错，最终失败的任务 ID 记在列表里。"""
    failed = []

    async def run(db, job):
        await jobs.set_stage(db, job, "recognize_questions", 30)
        match job.payload.get("raise"):
            case None:
                return
            case "crash":
                raise RuntimeError("boom")
            case code:
                raise AppError(400, code, "照片不清楚")

    async def on_failed(db, job):
        failed.append(job.id)

    monkeypatch.setitem(HANDLERS, "scan_grading", jobs.Handler(run=run, on_failed=on_failed))
    return failed


async def test_job_progress_only_visible_to_owner(client, student, teacher, owner, failed_jobs):
    job_id = await _enqueue(owner)
    resp = await client.get(f"/api/v1/jobs/{job_id}", headers=student)
    assert resp.json() == {
        "id": job_id,
        "status": "queued",
        "stage": None,
        "stage_label": None,
        "progress": 0,
        "error": None,
    }
    assert (await client.get(f"/api/v1/jobs/{job_id}", headers=teacher)).status_code == 404
    assert (await client.get(f"/api/v1/jobs/{job_id}")).status_code == 401

    assert await _claim() == job_id
    async with SessionLocal() as db:
        await jobs.set_stage(db, await db.get_one(Job, job_id), "grade_questions", 60)
    body = (await client.get(f"/api/v1/jobs/{job_id}", headers=student)).json()
    assert body["status"] == "running"
    assert body["stage"] == "grade_questions"
    assert (body["stage_label"], body["progress"]) == ("逐题批改", 60)


async def test_claim_takes_due_jobs_once_and_skips_locked(owner):
    first = await _enqueue(owner)
    second = await _enqueue(owner)
    later = await _enqueue(owner)
    async with SessionLocal() as db:
        await db.execute(
            update(Job).where(Job.id == later).values(run_after=func.now() + timedelta(hours=1))
        )
        await db.commit()

    # 另一个 Worker 正在取 first（锁住还没提交），这边直接跳过它
    async with SessionLocal() as other:
        await other.execute(select(Job).where(Job.id == first).with_for_update())
        assert await _claim() == second
    assert await _claim() == first
    assert await _claim() is None

    job = await _job(first)
    assert (job.status, job.tries) == ("running", 1)
    assert job.started_at is not None


async def test_run_job_succeeds(owner, failed_jobs):
    job_id = await _enqueue(owner)
    await worker.run_job(await _claim())
    job = await _job(job_id)
    assert (job.status, job.stage, job.progress, job.error) == (
        "succeeded",
        "recognize_questions",
        100,
        None,
    )
    assert job.finished_at is not None


async def test_ai_errors_retry_after_10s_and_60s_then_fail(owner, failed_jobs):
    job_id = await _enqueue(owner, {"raise": "AI_TIMEOUT"})
    for delay in (10, 60):
        await worker.run_job(await _claim())
        job = await _job(job_id)
        assert job.status == "queued"
        assert job.error is None
        wait = (job.run_after - job.updated_at).total_seconds()
        assert delay - 1 < wait < delay + 1
        # 没到时间不会被取走
        assert await _claim() is None
        await _make_due(job_id)

    await worker.run_job(await _claim())
    job = await _job(job_id)
    assert (job.status, job.tries) == ("failed", 3)
    assert job.error == {"code": "AI_TIMEOUT", "message": "照片不清楚"}
    assert failed_jobs == [job_id]


async def test_business_error_fails_without_retry(owner, failed_jobs):
    job_id = await _enqueue(owner, {"raise": "PHOTO_UNCLEAR"})
    await worker.run_job(await _claim())
    job = await _job(job_id)
    assert (job.status, job.tries) == ("failed", 1)
    assert job.error == {"code": "PHOTO_UNCLEAR", "message": "照片不清楚"}
    assert failed_jobs == [job_id]


async def test_crash_retries_with_internal_error(owner, failed_jobs):
    job_id = await _enqueue(owner, {"raise": "crash"})
    await worker.run_job(await _claim())
    # 抛错前更新的进度随任务一起保留，异常本身不影响下一次执行
    job = await _job(job_id)
    assert (job.status, job.tries, job.stage) == ("queued", 1, "recognize_questions")

    for _ in range(2):
        await _make_due(job_id)
        await worker.run_job(await _claim())
    job = await _job(job_id)
    assert job.status == "failed"
    assert job.error == jobs.INTERNAL_ERROR


async def test_stale_running_jobs_are_requeued_or_failed(owner, failed_jobs):
    stuck = await _enqueue(owner)
    exhausted = await _enqueue(owner)
    busy = await _enqueue(owner)
    for _ in range(3):
        await _claim()
    async with SessionLocal() as db:
        long_ago = func.now() - timedelta(minutes=11)
        await db.execute(update(Job).where(Job.id == stuck).values(updated_at=long_ago))
        await db.execute(
            update(Job).where(Job.id == exhausted).values(updated_at=long_ago, tries=3)
        )
        await db.commit()

    await worker.fail_stale()
    assert (await _job(stuck)).status == "queued"
    assert (await _job(exhausted)).status == "failed"
    assert (await _job(exhausted)).error == jobs.INTERNAL_ERROR
    assert (await _job(busy)).status == "running"
    assert failed_jobs == [exhausted]

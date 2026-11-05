from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.db import DB
from app.schemas.job import JobOut
from app.services import jobs

router = APIRouter(prefix="/jobs", tags=["公共"])


@router.get("/{job_id}")
async def get_job(db: DB, user: CurrentUser, job_id: int) -> JobOut:
    return jobs.job_out(await jobs.get(db, user, job_id))

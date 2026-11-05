from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job
from app.services import scans
from app.services.jobs import Handler


async def _keep_item(db: AsyncSession, job: Job) -> None:
    """重批失败时这道题保持原样，失败原因在任务的 error 里。"""


GRADING = Handler(run=scans.grade_page, on_failed=scans.mark_failed)
REGRADE = Handler(run=scans.regrade, on_failed=_keep_item)

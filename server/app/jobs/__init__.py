"""长任务处理函数，按 jobs.type 登记，由 Worker 调用。"""

from app.jobs import scans
from app.services.jobs import Handler

HANDLERS: dict[str, Handler] = {
    "scan_grading": scans.GRADING,
    "regrade": scans.REGRADE,
}

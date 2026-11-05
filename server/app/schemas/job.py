from typing import Literal

from pydantic import BaseModel


class JobError(BaseModel):
    code: str
    message: str


class JobOut(BaseModel):
    """长任务进度，见接口约定 2.2。"""

    id: int
    status: Literal["queued", "running", "succeeded", "failed"]
    stage: str | None
    stage_label: str | None
    progress: int
    error: JobError | None

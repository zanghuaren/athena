from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.attempt import AttemptResult, ErrorReason, StudentAnswer
from app.schemas.question import QuestionOut

MistakeSource = Literal["ask", "scan", "practice", "homework", "manual"]
MistakeStatus = Literal["pending", "reviewing", "mastered"]


class MistakeOut(BaseModel):
    """列表项：复习状态显示为“待复习 / 复习中 · 第 review_count 次 / 已掌握”。"""

    id: int
    question: QuestionOut
    source: MistakeSource
    wrong_count: int
    error_reason: ErrorReason | None
    tip: str | None
    status: MistakeStatus
    review_stage: int
    review_count: int
    next_review_on: date | None
    created_at: datetime


class MistakeDetail(MistakeOut):
    """answer、attempt 来自最近一次做错的作答记录；手动添加的没有记录，用 my_answer。"""

    answer: StudentAnswer | None
    attempt: AttemptResult | None
    my_answer: str | None
    note: str | None


class MistakePage(BaseModel):
    items: list[MistakeOut]
    total: int
    page: int
    page_size: int


class MistakePatch(BaseModel):
    """只改传了的字段；status 为 pending 是把已掌握的题恢复复习。"""

    error_reason: ErrorReason | None = None
    note: Annotated[str, Field(max_length=500)] | None = None
    status: Literal["mastered", "pending"] | None = None


class MistakeBatchIn(BaseModel):
    scan_id: int
    seqs: Annotated[list[int], Field(min_length=1, max_length=20)]


class MistakeBatchOut(BaseModel):
    items: list[MistakeOut]


class MistakeTip(BaseModel):
    """入本时模型的输出，见 prompts/mistakes/tip.md。"""

    tip: Annotated[str, Field(min_length=1, max_length=60)]
    error_reason: ErrorReason

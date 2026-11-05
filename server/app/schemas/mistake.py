from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from app.schemas.attempt import AttemptResult, ErrorReason, StudentAnswer
from app.schemas.knowledge import KnowledgePointBrief
from app.schemas.question import QuestionBody, QuestionOut
from app.schemas.user import Subject

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


class QuestionDraft(QuestionBody):
    """从答疑里提取出、等学生确认的题目；确认时原样带回，可以改题干。"""

    subject: Subject
    knowledge_points: Annotated[list[KnowledgePointBrief], Field(min_length=1, max_length=3)]


class ExtractOut(BaseModel):
    """这条讲解已经加入过错题本时，mistake_id 是那道错题。"""

    question: QuestionDraft
    mistake_id: int | None


class AskQuestionIn(QuestionBody):
    subject: Subject
    knowledge_point_ids: Annotated[list[int], Field(min_length=1, max_length=3)]


class AskMistakeIn(BaseModel):
    """答疑里加入错题本（ASK-05）：题目是 extract-question 返回、学生确认过的。"""

    source: Literal["ask"]
    message_id: int
    question: AskQuestionIn


Short = Annotated[str, Field(min_length=1, max_length=1000)]


class ManualMistakeIn(BaseModel):
    """手动添加（S-15）：题目、正确答案都是文字，存成解答题。"""

    source: Literal["manual"]
    subject: Subject
    stem: Short
    answer: Short
    my_answer: Annotated[str, Field(max_length=1000)] = ""
    knowledge_point_ids: Annotated[list[int], Field(min_length=1, max_length=3)]


MistakeIn = Annotated[AskMistakeIn | ManualMistakeIn, Field(discriminator="source")]


class Extracted(BaseModel):
    """从答疑里提取题目时模型的输出，见 prompts/mistakes/extract.md。

    context 的 codes 是每个学科可选的知识点编号。
    """

    status: Literal["ok", "none"]
    subject: Subject | None = None
    question: QuestionBody | None = None
    knowledge_points: list[str] | None = None

    @model_validator(mode="after")
    def _ok_has_question(self, info: ValidationInfo):
        if self.status == "none":
            return self
        if self.subject is None or self.question is None or not self.knowledge_points:
            raise ValueError("找到题目时要有学科、题目和知识点")
        if not 1 <= len(self.knowledge_points) <= 3:
            raise ValueError("知识点选 1～3 个")
        if not set(self.knowledge_points) <= info.context["codes"].get(self.subject, set()):
            raise ValueError("知识点要从这个学科的目录里选")
        return self

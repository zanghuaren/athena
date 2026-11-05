import logging
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.schemas.attempt import AttemptResult, Confidence, StudentAnswer, check_answer
from app.schemas.file import FileOut
from app.schemas.question import QuestionContent, QuestionOut
from app.schemas.user import Subject

logger = logging.getLogger(__name__)


class RecognizeIn(BaseModel):
    image_file_id: int


class RecognizeOut(BaseModel):
    """text 是题干和选项的 Markdown，学生核对修改后作为提问发出。"""

    subject: Subject
    text: Annotated[str, Field(min_length=1)]


class Recognized(BaseModel):
    """识题时模型的输出，见 prompts/scan/recognize.md。"""

    status: Literal["ok", "empty", "multiple"]
    subject: Subject | None
    text: str

    @model_validator(mode="after")
    def _ok_has_question(self):
        if self.status == "ok" and (self.subject is None or not self.text.strip()):
            raise ValueError("识别成功时要有学科和题目")
        return self


PageQuestionType = Literal["single", "multiple", "judge", "blank", "solution", "cloze", "reading"]


class PageQuestion(BaseModel):
    seq: int
    type: PageQuestionType
    content: QuestionContent
    # [x1, y1, x2, y2]，按图片宽高换算成 0～1000
    bbox: Annotated[list[Annotated[int, Field(ge=0, le=1000)]], Field(min_length=4, max_length=4)]
    confidence: Confidence

    @model_validator(mode="before")
    @classmethod
    def _drop_stray_fields(cls, data):
        # 带 ____ 的解答题，模型常顺手给出空数；这一项对解答题没有意义，去掉即可
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(content, dict) and data.get("type") not in ("blank", None):
            content.pop("blank_count", None)
        return data

    @model_validator(mode="after")
    def _check(self):
        x1, y1, x2, y2 = self.bbox
        if x1 >= x2 or y1 >= y2:
            raise ValueError("坐标框的左上角要在右下角之前")
        check_content(self.type, self.content)
        return self


class PageRecognized(BaseModel):
    """整页识别题目时模型的输出，见 prompts/scan/page.md。"""

    status: Literal["ok", "unclear", "empty"]
    subject: Subject | None
    questions: list[PageQuestion]

    @field_validator("questions", mode="before")
    @classmethod
    def _drop_invalid(cls, value):
        """单道题不合格（多半是页面边上被裁掉一半的题）只丢掉这一道，不让整页重新识别。"""
        if not isinstance(value, list):
            return value
        kept = []
        for item in value:
            try:
                kept.append(PageQuestion.model_validate(item))
            except ValidationError as exc:
                logger.warning("scan page drop question: %s", exc.errors()[:1])
        return kept

    @model_validator(mode="after")
    def _ok_has_subject(self):
        if self.status == "ok" and self.questions and self.subject is None:
            raise ValueError("识别到题目时要有学科")
        return self


class AnswerRecognized(BaseModel):
    """识别一道题的作答时模型的输出，见 prompts/scan/answer.md；context 里是题型和题目内容。"""

    status: Literal["ok", "unclear"]
    answer: StudentAnswer | None
    confidence: Confidence

    @model_validator(mode="before")
    @classmethod
    def _blanks_to_text(cls, data, info: ValidationInfo):
        # 解答题里有 ____ 时，模型常按空给出作答；按顺序拼成文字就是解答的作答
        answer = data.get("answer") if isinstance(data, dict) else None
        if info.context["type"] == "solution" and isinstance(answer, dict) and "blanks" in answer:
            data["answer"] = {"text": "；".join(str(b) for b in answer["blanks"])}
        return data

    @model_validator(mode="after")
    def _fits_question(self, info: ValidationInfo):
        if self.status == "ok":
            if self.answer is None:
                raise ValueError("识别成功时要有作答")
            check_answer(info.context["type"], info.context["content"], self.answer)
        return self


def check_content(type_: str, content: QuestionContent) -> None:
    """题目内容要和题型对得上（选择题有选项、填空题有空数、完形阅读有材料和小题）。"""
    _check_fields(type_, content.options, content.blank_count)
    has_material = content.material is not None or content.sub_questions is not None
    if has_material != (type_ in ("cloze", "reading")):
        raise ValueError("只有完形填空和阅读理解有材料和小题")
    if type_ in ("cloze", "reading"):
        if content.material is None or not content.sub_questions:
            raise ValueError("完形填空和阅读理解必须有材料和小题")
        for sub in content.sub_questions:
            _check_fields(sub.type, sub.options, sub.blank_count)


def _check_fields(type_: str, options: list | None, blank_count: int | None) -> None:
    if (type_ in ("single", "multiple")) != (options is not None):
        raise ValueError("只有选择题有选项")
    if options is not None and len(options) < 2:
        raise ValueError("选择题至少要有 2 个选项")
    if (type_ == "blank") != (blank_count is not None):
        raise ValueError("只有填空题有空数")


class BBox(BaseModel):
    """归一化坐标，0～1。"""

    x: float
    y: float
    w: float
    h: float


class ScanIn(BaseModel):
    image_file_id: int


class ScanOut(BaseModel):
    id: int
    status: Literal["processing", "done", "failed"]
    fail_reason: Literal["unclear", "no_question", "error"] | None
    subject: Subject | None
    image: FileOut
    job_id: int | None
    truncated: bool
    total: int
    correct: int
    unknown: int
    created_at: datetime


class ScanCreated(BaseModel):
    scan: ScanOut
    job_id: int


class ScanPage(BaseModel):
    items: list[ScanOut]
    total: int
    page: int
    page_size: int


class ScanItemOut(BaseModel):
    """attempt 为空就是“？”：看不清或置信度低，没有判分；mistake_id 是已加入错题本的错题。"""

    seq: int
    bbox: BBox
    confidence: float
    question: QuestionOut
    answer: StudentAnswer | None
    attempt: AttemptResult | None
    mistake_id: int | None


class ScanDetail(ScanOut):
    items: list[ScanItemOut]


class RegradeIn(BaseModel):
    """改了题目时带 content，题型不变。"""

    answer: StudentAnswer
    content: QuestionContent | None = None


class RegradeOut(BaseModel):
    job_id: int


class ConfirmIn(BaseModel):
    result: Literal["correct", "wrong"]

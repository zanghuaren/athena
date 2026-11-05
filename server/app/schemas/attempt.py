"""学生作答和批改明细的结构（数据库设计 10.2、10.3），以及判分时模型的输出。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from app.schemas.question import AnalysisStep, OptionKey, QuestionBody, ScoringPoint

Result = Literal["correct", "partial", "wrong"]
ErrorReason = Literal["concept", "calculation", "reading", "method", "careless", "other"]
Confidence = Annotated[float, Field(ge=0, le=1)]


class _Strict(BaseModel):
    # 和题目答案一样靠字段名区分结构，多余字段必须报错
    model_config = ConfigDict(extra="forbid")


# 学生作答：和题目答案的结构一一对应，但每空只有一个答案，而且都可以不作答
class ChoiceInput(_Strict):
    choice: list[OptionKey]


class JudgeInput(_Strict):
    judge: bool | None


class BlanksInput(_Strict):
    blanks: list[str]


class TextInput(_Strict):
    text: str


class SubInputItem(_Strict):
    seq: int
    choice: list[OptionKey] | None = None
    judge: bool | None = None
    blanks: list[str] | None = None


class SubInput(_Strict):
    sub: list[SubInputItem]


StudentAnswer = ChoiceInput | JudgeInput | BlanksInput | TextInput | SubInput


class GradingItem(BaseModel):
    """每空、每小题或每个评分要点的结果；key 形如 blank_1、sub_3、point_2。"""

    key: str
    result: Result
    score: float
    max_score: float
    comment: str | None = None


class GradingDetail(BaseModel):
    confidence: Confidence
    items: list[GradingItem]
    summary: str | None = None


class BlankVerdict(BaseModel):
    seq: int
    correct: bool
    confidence: Confidence


class BlankVerdicts(BaseModel):
    """填空等价判断时模型的输出，见 prompts/grading/blank.md；context 的 count 是问了几个空。"""

    blanks: list[BlankVerdict]

    @model_validator(mode="after")
    def _all_answered(self, info: ValidationInfo):
        if sorted(b.seq for b in self.blanks) != list(range(1, info.context["count"] + 1)):
            raise ValueError("每个空都要给出判断")
        return self


class PointScore(BaseModel):
    seq: int
    score: Annotated[float, Field(ge=0)]
    comment: str = ""


class SolutionGrading(BaseModel):
    """解答题批改时模型的输出，见 prompts/grading/solution.md。

    context 的 max_scores 是各评分要点的分值。
    """

    points: list[PointScore]
    confidence: Confidence
    summary: str
    error_reason: ErrorReason | None

    @model_validator(mode="after")
    def _points_match(self, info: ValidationInfo):
        max_scores = info.context["max_scores"]
        if [p.seq for p in self.points] != list(range(1, len(max_scores) + 1)):
            raise ValueError("每个评分要点都要给分")
        if any(p.score > m for p, m in zip(self.points, max_scores, strict=True)):
            raise ValueError("得分不能超过要点的分值")
        return self


class Solved(BaseModel):
    """没有答案的题目由模型解出时的输出，见 prompts/grading/solve.md。

    context 里是题型和题目内容，拼成完整的题目后按题型校验。
    """

    answer: dict
    analysis: list[AnalysisStep]
    scoring_points: list[ScoringPoint] | None = None
    difficulty: int

    @model_validator(mode="after")
    def _valid_question(self, info: ValidationInfo):
        self.to_body(info.context["type"], info.context["content"])
        return self

    def to_body(self, type: str, content: dict) -> QuestionBody:
        return QuestionBody.model_validate(
            {"type": type, "content": content, **self.model_dump(exclude_none=True)}
        )

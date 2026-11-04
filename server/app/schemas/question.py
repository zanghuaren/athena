"""题目内容和答案的结构（数据库设计 10.1），按题型校验。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuestionType = Literal[
    "single", "multiple", "judge", "blank", "solution", "cloze", "reading", "essay"
]
SubQuestionType = Literal["single", "multiple", "judge", "blank"]
OptionKey = Annotated[str, Field(pattern=r"^[A-H]$")]
Text = Annotated[str, Field(min_length=1)]


class _Strict(BaseModel):
    # 答案靠字段名区分是哪一种，多余的字段必须报错，否则会被认成别的结构
    model_config = ConfigDict(extra="forbid")


class Option(_Strict):
    key: OptionKey
    text: Text


class SubQuestion(_Strict):
    seq: Annotated[int, Field(ge=1)]
    type: SubQuestionType
    # 完形填空的小题通常只有选项，没有题干
    stem: str = ""
    options: list[Option] | None = None
    blank_count: Annotated[int, Field(ge=1)] | None = None
    score: Annotated[float, Field(gt=0)]


class QuestionContent(_Strict):
    stem: Text
    images: list[int] = []
    options: list[Option] | None = None
    blank_count: Annotated[int, Field(ge=1)] | None = None
    material: Text | None = None
    sub_questions: list[SubQuestion] | None = None


Blanks = Annotated[list[Annotated[list[Text], Field(min_length=1)]], Field(min_length=1)]


class ChoiceAnswer(_Strict):
    choice: Annotated[list[OptionKey], Field(min_length=1)]


class JudgeAnswer(_Strict):
    judge: bool


class BlanksAnswer(_Strict):
    """每空一个列表，列表里是这一空的所有等价答案。"""

    blanks: Blanks


class TextAnswer(_Strict):
    text: Text
    final: Text | None = None


class SubAnswerItem(_Strict):
    seq: int
    choice: list[OptionKey] | None = None
    judge: bool | None = None
    blanks: Blanks | None = None


class SubAnswer(_Strict):
    sub: Annotated[list[SubAnswerItem], Field(min_length=1)]


Answer = ChoiceAnswer | JudgeAnswer | BlanksAnswer | TextAnswer | SubAnswer


class AnalysisStep(_Strict):
    title: Text
    body: Text


class ScoringPoint(_Strict):
    point: Text
    score: Annotated[float, Field(gt=0)]


class QuestionBody(_Strict):
    """题目本身的内容，不含来源、归属、知识点。"""

    type: QuestionType
    content: QuestionContent
    answer: Answer
    analysis: Annotated[list[AnalysisStep], Field(min_length=1)]
    scoring_points: list[ScoringPoint] | None = None
    difficulty: Annotated[int, Field(ge=1, le=5)]

    @model_validator(mode="after")
    def _check_by_type(self) -> "QuestionBody":
        c, a = self.content, self.answer
        match self.type:
            case "single" | "multiple" | "judge" | "blank":
                _forbid_material(c)
                _check_simple(self.type, c.options, c.blank_count, a)
            case "solution" | "essay":
                _forbid_material(c)
                _forbid_options(c.options, c.blank_count)
                _expect(a, TextAnswer, "答案应为文字答案")
            case "cloze" | "reading":
                _check_with_material(self.type, c, a)
        if self.type == "solution" and not self.scoring_points:
            raise ValueError("解答题必须有评分要点")
        if self.type not in ("solution", "essay") and self.scoring_points is not None:
            raise ValueError("只有解答题和作文有评分要点")
        return self


def _expect[T](answer: object, cls: type[T], message: str) -> T:
    if not isinstance(answer, cls):
        raise ValueError(message)
    return answer


def _forbid_material(c: QuestionContent) -> None:
    if c.material is not None or c.sub_questions is not None:
        raise ValueError("只有完形填空和阅读理解有材料和小题")


def _forbid_options(options: list[Option] | None, blank_count: int | None) -> None:
    if options is not None:
        raise ValueError("只有选择题有选项")
    if blank_count is not None:
        raise ValueError("只有填空题有空数")


def _check_simple(
    type_: SubQuestionType,
    options: list[Option] | None,
    blank_count: int | None,
    answer: object,
) -> None:
    """单选、多选、判断、填空：大题和完形 / 阅读的小题共用。"""
    if type_ in ("single", "multiple"):
        if blank_count is not None:
            raise ValueError("只有填空题有空数")
        choice = _expect(answer, ChoiceAnswer, "答案应为选项").choice
        _check_choice(type_, options, choice)
    elif type_ == "judge":
        _forbid_options(options, blank_count)
        _expect(answer, JudgeAnswer, "答案应为对或错")
    else:
        if options is not None:
            raise ValueError("只有选择题有选项")
        blanks = _expect(answer, BlanksAnswer, "答案应为每空的答案").blanks
        if blank_count is None or len(blanks) != blank_count:
            raise ValueError("答案的空数和题目的空数不一致")


def _check_choice(
    type_: Literal["single", "multiple"], options: list[Option] | None, choice: list[str]
) -> None:
    if not options or len(options) < 2:
        raise ValueError("选择题至少要有 2 个选项")
    keys = [o.key for o in options]
    if len(set(keys)) != len(keys):
        raise ValueError("选项字母不能重复")
    if len(set(choice)) != len(choice) or not set(choice) <= set(keys):
        raise ValueError("答案里有不存在的选项")
    if type_ == "single" and len(choice) != 1:
        raise ValueError("单选题只能有 1 个答案")
    if type_ == "multiple" and len(choice) < 2:
        raise ValueError("多选题至少要有 2 个答案")


def _check_with_material(
    type_: Literal["cloze", "reading"], c: QuestionContent, answer: object
) -> None:
    if c.material is None or not c.sub_questions:
        raise ValueError("完形填空和阅读理解必须有材料和小题")
    _forbid_options(c.options, c.blank_count)
    seqs = [s.seq for s in c.sub_questions]
    if seqs != list(range(1, len(seqs) + 1)):
        raise ValueError("小题序号应从 1 开始连续编号")
    items = {i.seq: i for i in _expect(answer, SubAnswer, "答案应为每道小题的答案").sub}
    if sorted(items) != seqs:
        raise ValueError("每道小题都要有答案")
    for sub in c.sub_questions:
        if type_ == "cloze" and sub.type != "single":
            raise ValueError("完形填空的小题只能是单选")
        _check_simple(sub.type, sub.options, sub.blank_count, _sub_answer(items[sub.seq]))


def _sub_answer(item: SubAnswerItem) -> Answer | None:
    if item.choice is not None:
        return ChoiceAnswer(choice=item.choice)
    if item.judge is not None:
        return JudgeAnswer(judge=item.judge)
    if item.blanks is not None:
        return BlanksAnswer(blanks=item.blanks)
    return None

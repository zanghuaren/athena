import pytest
from pydantic import ValidationError

from app.schemas.question import QuestionBody

ANALYSIS = [{"title": "思路", "body": "直接计算。"}]
OPTIONS = [{"key": k, "text": t} for k, t in zip("ABCD", ["1", "2", "3", "4"], strict=True)]


def body(type_, content, answer, **extra):
    return {
        "type": type_,
        "content": content,
        "answer": answer,
        "analysis": ANALYSIS,
        "difficulty": 2,
        **extra,
    }


VALID = {
    "single": body("single", {"stem": "$1+1=$", "options": OPTIONS}, {"choice": ["B"]}),
    "multiple": body("multiple", {"stem": "偶数有", "options": OPTIONS}, {"choice": ["B", "D"]}),
    "judge": body("judge", {"stem": "$0$ 是正数"}, {"judge": False}),
    "blank": body(
        "blank",
        {"stem": "$\\frac{1}{2}=$____，$1+2=$____", "blank_count": 2},
        {"blanks": [["0.5", "1/2"], ["3"]]},
    ),
    "solution": body(
        "solution",
        {"stem": "解方程 $2x+1=7$"},
        {"text": "移项得 $2x=6$，所以 $x=3$。", "final": "$x=3$"},
        scoring_points=[{"point": "移项正确", "score": 2}, {"point": "结果正确", "score": 2}],
    ),
    "cloze": body(
        "cloze",
        {
            "stem": "阅读短文，选择最佳答案。",
            "material": "I __1__ a student.",
            "sub_questions": [
                {
                    "seq": 1,
                    "type": "single",
                    "options": [{"key": "A", "text": "am"}, {"key": "B", "text": "is"}],
                    "score": 1,
                }
            ],
        },
        {"sub": [{"seq": 1, "choice": ["A"]}]},
    ),
    "reading": body(
        "reading",
        {
            "stem": "阅读短文，回答问题。",
            "material": "Tom likes apples.",
            "sub_questions": [
                {"seq": 1, "type": "judge", "stem": "Tom likes bananas.", "score": 2},
                {"seq": 2, "type": "blank", "stem": "He likes ____.", "blank_count": 1, "score": 2},
            ],
        },
        {"sub": [{"seq": 1, "judge": False}, {"seq": 2, "blanks": [["apples"]]}]},
    ),
}


@pytest.mark.parametrize("type_", VALID)
def test_valid_question_of_each_type(type_):
    q = QuestionBody.model_validate(VALID[type_])
    assert q.type == type_


def with_(type_, **changes):
    return {**VALID[type_], **changes}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (with_("single", answer={"choice": ["B", "C"]}), "单选题只能有 1 个答案"),
        (with_("single", answer={"choice": ["E"]}), "答案里有不存在的选项"),
        (with_("single", answer={"judge": True}), "答案应为选项"),
        (with_("single", content={"stem": "?", "options": OPTIONS[:1]}), "至少要有 2 个选项"),
        (with_("multiple", answer={"choice": ["B"]}), "多选题至少要有 2 个答案"),
        (with_("judge", content={"stem": "?", "options": OPTIONS}), "只有选择题有选项"),
        (with_("blank", answer={"blanks": [["0.5"]]}), "空数不一致"),
        (with_("blank", answer={"blanks": [["0.5"], []]}), "at least 1 item"),
        (with_("solution", scoring_points=None), "解答题必须有评分要点"),
        (with_("single", scoring_points=[{"point": "x", "score": 1}]), "只有解答题和作文"),
        (with_("solution", content={"stem": "?", "material": "x"}), "只有完形填空和阅读理解"),
        (with_("cloze", answer={"sub": [{"seq": 2, "choice": ["A"]}]}), "每道小题都要有答案"),
        (with_("reading", answer={"sub": [{"seq": 1, "judge": False}, {"seq": 2}]}), "每空的答案"),
        (with_("single", difficulty=6), "less than or equal to 5"),
        (with_("single", answer={"choice": ["B"], "extra": 1}), "Extra inputs"),
    ],
)
def test_invalid_question_is_rejected(data, message):
    with pytest.raises(ValidationError, match=message):
        QuestionBody.model_validate(data)


def test_cloze_sub_questions_must_be_single():
    data = with_("cloze")
    data["content"] = {
        **data["content"],
        "sub_questions": [{"seq": 1, "type": "judge", "score": 1}],
    }
    data["answer"] = {"sub": [{"seq": 1, "judge": True}]}
    with pytest.raises(ValidationError, match="完形填空的小题只能是单选"):
        QuestionBody.model_validate(data)

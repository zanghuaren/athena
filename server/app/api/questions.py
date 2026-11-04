from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.db import DB
from app.schemas.question import QuestionOut
from app.services import questions

router = APIRouter(prefix="/questions", tags=["知识点与题目"])


@router.get("/{question_id}")
async def get_question(db: DB, user: CurrentUser, question_id: int) -> QuestionOut:
    question = await questions.get_visible(db, user, question_id)
    out = QuestionOut.model_validate(question)
    # 学生端要等有了作答记录（判分完成后）才能看答案，见接口约定第 3 节
    if user.role == "student":
        out = out.model_copy(update={"answer": None, "analysis": None, "scoring_points": None})
    return out

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import AppError
from app.models import Question, QuestionKnowledgePoint, User
from app.schemas.question import QuestionBody


async def get_visible(db: AsyncSession, user: User, question_id: int) -> Question:
    """预置题公开，其余只归创建者；看不到的题和不存在的题一样返回 404。"""
    question = await db.scalar(
        select(Question)
        .where(
            Question.id == question_id,
            or_(Question.owner_id.is_(None), Question.owner_id == user.id),
        )
        .options(selectinload(Question.knowledge_points))
    )
    if question is None:
        raise AppError(404, "NOT_FOUND", "题目不存在或已被删除")
    return question


def columns(body: QuestionBody) -> dict:
    """校验过的题目内容对应的列；content_text 是题干、选项和材料的纯文本。"""
    data = body.model_dump(exclude_none=True)
    content = body.content
    text = "\n".join(
        [content.stem, *(o.text for o in content.options or []), content.material or ""]
    )
    return {
        "type": body.type,
        "content": data["content"],
        "answer": data["answer"],
        "analysis": data["analysis"],
        "scoring_points": data.get("scoring_points"),
        "difficulty": body.difficulty,
        "content_text": text.strip(),
    }


def link_points(db: AsyncSession, question_id: int, point_ids: list[int]) -> None:
    db.add_all(
        QuestionKnowledgePoint(question_id=question_id, knowledge_point_id=i) for i in point_ids
    )

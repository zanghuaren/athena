from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import AppError
from app.models import Question, User


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

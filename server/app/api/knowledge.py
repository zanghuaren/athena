from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.db import DB
from app.schemas.knowledge import ChapterNode, KnowledgePointOut, KnowledgeTree
from app.schemas.user import Subject
from app.services import knowledge

router = APIRouter(tags=["知识点与题目"])


@router.get("/knowledge-tree")
async def get_knowledge_tree(
    db: DB,
    _: CurrentUser,
    subject: Subject,
    # 查询参数是字符串，Literal[7, 8, 9] 不会把 "7" 转成整数
    grade: Annotated[int | None, Query(ge=7, le=9)] = None,
) -> KnowledgeTree:
    chapters = await knowledge.tree(db, subject, grade)
    return KnowledgeTree(
        subject=subject, chapters=[ChapterNode.model_validate(ch) for ch in chapters]
    )


@router.get("/knowledge-points/{point_id}")
async def get_knowledge_point(db: DB, _: CurrentUser, point_id: int) -> KnowledgePointOut:
    return KnowledgePointOut.model_validate(await knowledge.get_point(db, point_id))

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.errors import AppError
from app.models import Chapter, KnowledgePoint
from app.schemas.user import Grade, Subject

SUBJECT_PREFIX = {"chinese": "C", "math": "M", "physics": "P", "english": "E"}
SUBJECT_GRADES = {
    "chinese": {7, 8, 9},
    "math": {7, 8, 9},
    "physics": {8, 9},
    "english": {7, 8, 9},
}


class SeedPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    description: str
    # 不写就用章节的年级；英语、语文章节不分年级，每个知识点必须写
    grades: Annotated[list[Grade], Field(min_length=1)] | None = None


class SeedChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    grade: Grade | None
    title: str
    points: Annotated[list[SeedPoint], Field(min_length=1)]

    @model_validator(mode="after")
    def _fill_points(self) -> "SeedChapter":
        for p in self.points:
            if not p.code.startswith(f"{self.code}-"):
                raise ValueError(f"知识点 {p.code} 的编号应以章节编号 {self.code}- 开头")
            if p.grades is None:
                if self.grade is None:
                    raise ValueError(f"知识点 {p.code} 没有适用年级")
                p.grades = [self.grade]
        return self


class KnowledgeCatalog(BaseModel):
    """`seed/knowledge/*.json` 的格式，一个文件一个学科。"""

    model_config = ConfigDict(extra="forbid")

    subject: Subject
    chapters: list[SeedChapter]

    @model_validator(mode="after")
    def _check(self) -> "KnowledgeCatalog":
        prefix = SUBJECT_PREFIX[self.subject]
        for ch in self.chapters:
            expected = f"{prefix}{ch.grade or ''}-"
            if not ch.code.startswith(expected):
                raise ValueError(f"章节 {ch.code} 的编号应以 {expected} 开头")
            for p in ch.points:
                if not set(p.grades or []) <= SUBJECT_GRADES[self.subject]:
                    raise ValueError(f"知识点 {p.code} 的年级不在本学科范围内")
        return self


async def import_catalog(db: AsyncSession, catalog: KnowledgeCatalog) -> None:
    """按编号写入，已有的就更新，可以重复导入。种子里删掉的条目不会从数据库删除。"""
    for ch_sort, ch in enumerate(catalog.chapters, start=1):
        chapter_id = await _upsert(
            db,
            Chapter,
            code=ch.code,
            subject=catalog.subject,
            grade=ch.grade,
            title=ch.title,
            sort=ch_sort,
        )
        for p_sort, p in enumerate(ch.points, start=1):
            await _upsert(
                db,
                KnowledgePoint,
                code=p.code,
                chapter_id=chapter_id,
                name=p.name,
                description=p.description,
                grades=p.grades,
                sort=p_sort,
            )
    await db.commit()


async def _upsert(db: AsyncSession, model: type[Chapter | KnowledgePoint], **values) -> int:
    stmt = insert(model).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[model.code],
        set_={**{k: v for k, v in values.items() if k != "code"}, "updated_at": func.now()},
    ).returning(model.id)
    return await db.scalar(stmt)


async def tree(db: AsyncSession, subject: str, grade: int | None) -> list[Chapter]:
    """按年级筛选时，只加载适用于这个年级的知识点，没有知识点的章节不返回。"""
    points = Chapter.knowledge_points
    if grade is not None:
        points = points.and_(KnowledgePoint.grades.contains([grade]))
    chapters = await db.scalars(
        select(Chapter)
        .where(Chapter.subject == subject)
        .order_by(Chapter.sort)
        .options(selectinload(points))
    )
    return [ch for ch in chapters if ch.knowledge_points]


async def get_point(db: AsyncSession, point_id: int) -> KnowledgePoint:
    point = await db.scalar(
        select(KnowledgePoint)
        .where(KnowledgePoint.id == point_id)
        .options(joinedload(KnowledgePoint.chapter))
    )
    if point is None:
        raise AppError(404, "NOT_FOUND", "知识点不存在")
    return point


async def catalog(db: AsyncSession, subject: str) -> dict[str, tuple[int, str]]:
    """这个学科的知识点：编号 → (ID, 名称)，交给模型选知识点时用。"""
    rows = await db.execute(
        select(KnowledgePoint.code, KnowledgePoint.id, KnowledgePoint.name)
        .join(Chapter)
        .where(Chapter.subject == subject)
        .order_by(KnowledgePoint.code)
    )
    return {code: (id_, name) for code, id_, name in rows}

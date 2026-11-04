from pydantic import BaseModel, ConfigDict

from app.schemas.user import Grade, Subject


class KnowledgePointBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    grades: list[Grade]


class ChapterNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    grade: Grade | None
    knowledge_points: list[KnowledgePointBrief]


class KnowledgeTree(BaseModel):
    subject: Subject
    chapters: list[ChapterNode]


class ChapterBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    subject: Subject
    title: str
    grade: Grade | None


class KnowledgePointOut(KnowledgePointBrief):
    description: str
    chapter: ChapterBrief

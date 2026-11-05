# 所有表都要在这里导入，Alembic 才能发现
from app.models.attempt import Attempt
from app.models.base import Base
from app.models.conversation import Conversation, Message
from app.models.file import File
from app.models.job import Job
from app.models.knowledge import Chapter, KnowledgePoint
from app.models.mistake import Mistake
from app.models.question import Question, QuestionKnowledgePoint
from app.models.scan import Scan, ScanItem
from app.models.user import Session, User

__all__ = [
    "Attempt",
    "Base",
    "Chapter",
    "Conversation",
    "File",
    "Job",
    "KnowledgePoint",
    "Message",
    "Mistake",
    "Question",
    "QuestionKnowledgePoint",
    "Scan",
    "ScanItem",
    "Session",
    "User",
]

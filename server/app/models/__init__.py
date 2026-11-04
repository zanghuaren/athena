# 所有表都要在这里导入，Alembic 才能发现
from app.models.base import Base
from app.models.conversation import Conversation, Message
from app.models.file import File
from app.models.knowledge import Chapter, KnowledgePoint
from app.models.question import Question, QuestionKnowledgePoint
from app.models.user import Session, User

__all__ = [
    "Base",
    "Chapter",
    "Conversation",
    "File",
    "KnowledgePoint",
    "Message",
    "Question",
    "QuestionKnowledgePoint",
    "Session",
    "User",
]

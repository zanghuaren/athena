from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.user import ExplainMode, Subject

Title = Annotated[str, Field(min_length=1, max_length=30)]
MAX_CONTENT_LENGTH = 1000
MessageAction = Literal["hint", "full", "example", "continue", "regenerate"]


class ConversationIn(BaseModel):
    # subject 为空表示自动识别；explain_mode 只对学生有效，不传时取学生的讲解偏好
    subject: Subject | None = None
    explain_mode: ExplainMode | None = None


class ConversationPatch(BaseModel):
    """只改传了的字段；subject 传 null 表示改成自动识别。"""

    title: Title | None = None
    subject: Subject | None = None
    explain_mode: ExplainMode | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject: Subject | None
    explain_mode: ExplainMode | None
    turn_count: int
    created_at: datetime
    updated_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    total: int
    page: int
    page_size: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    action: Literal["hint", "full", "example"] | None
    content: str
    status: Literal["done", "interrupted", "blocked"]
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class MessageIn(BaseModel):
    """普通提问只传 content；点按钮的动作只传 action，见接口约定 2.1。"""

    content: str = ""
    action: MessageAction | None = None

    @field_validator("content")
    @classmethod
    def _content_length(cls, value: str) -> str:
        if len(value) > MAX_CONTENT_LENGTH:
            raise ValueError(f"问题不能超过 {MAX_CONTENT_LENGTH} 字")
        return value

    @model_validator(mode="after")
    def _content_required(self):
        if self.action is None and not self.content.strip():
            raise ValueError("请输入问题")
        return self

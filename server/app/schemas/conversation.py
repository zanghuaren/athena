from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.file import FileOut
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
    # 带签名的地址要由接口层填，不从表里直接读
    image: FileOut | None = None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class MessageIn(BaseModel):
    """普通提问传 content，可以附一张图；点按钮的动作只传 action，见接口约定 2.1。"""

    content: str = ""
    image_file_id: int | None = None
    action: MessageAction | None = None

    @field_validator("content")
    @classmethod
    def _content_length(cls, value: str) -> str:
        if len(value) > MAX_CONTENT_LENGTH:
            raise ValueError(f"问题不能超过 {MAX_CONTENT_LENGTH} 字")
        return value

    @model_validator(mode="after")
    def _content_required(self):
        if self.action is None and not self.content.strip() and self.image_file_id is None:
            raise ValueError("请输入问题")
        if self.action and self.image_file_id is not None:
            raise ValueError("这个操作不能附图")
        return self


class Suggestion(BaseModel):
    """对话页空状态的示例问题（S-01），每次由 AI 按语文知识点现编一个。"""

    subject: Subject
    text: Annotated[str, Field(min_length=4, max_length=80)]


class Suggested(BaseModel):
    """生成示例问题时模型的输出，见 prompts/ask/suggest.md。"""

    text: Annotated[str, Field(min_length=4, max_length=80)]

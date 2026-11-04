from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.user import Subject


class RecognizeIn(BaseModel):
    image_file_id: int


class RecognizeOut(BaseModel):
    """text 是题干和选项的 Markdown，学生核对修改后作为提问发出。"""

    subject: Subject
    text: Annotated[str, Field(min_length=1)]


class Recognized(BaseModel):
    """识题时模型的输出，见 prompts/scan/recognize.md。"""

    status: Literal["ok", "empty", "multiple"]
    subject: Subject | None
    text: str

    @model_validator(mode="after")
    def _ok_has_question(self):
        if self.status == "ok" and (self.subject is None or not self.text.strip()):
            raise ValueError("识别成功时要有学科和题目")
        return self

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["student", "teacher"]
Subject = Literal["chinese", "math", "physics", "english"]
Grade = Literal[7, 8, 9]
ExplainMode = Literal["guided", "direct"]
DisplayName = Annotated[str, Field(min_length=1, max_length=20)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    display_name: str
    avatar: str
    grade: Grade | None
    teach_subjects: list[Subject] | None
    teach_grades: list[Grade] | None
    explain_mode: ExplainMode | None
    preferred_subject: Subject | None

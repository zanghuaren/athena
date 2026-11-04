import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from app.schemas.user import DisplayName, Grade, Subject, UserOut


def _check_username(v: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{4,20}", v):
        raise ValueError("用户名为 4～20 位字母、数字或下划线")
    return v


def _check_password(v: str) -> str:
    if not (8 <= len(v) <= 32 and re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("密码为 8～32 位，必须同时包含字母和数字")
    return v


Username = Annotated[str, AfterValidator(_check_username)]
Password = Annotated[str, AfterValidator(_check_password)]


class StudentRegister(BaseModel):
    role: Literal["student"]
    username: Username
    password: Password
    display_name: DisplayName
    grade: Grade


class TeacherRegister(BaseModel):
    role: Literal["teacher"]
    username: Username
    password: Password
    display_name: DisplayName
    teach_subjects: Annotated[list[Subject], Field(min_length=1)]
    teach_grades: Annotated[list[Grade], Field(min_length=1)]


RegisterIn = Annotated[StudentRegister | TeacherRegister, Field(discriminator="role")]


class LoginIn(BaseModel):
    username: str
    password: str


class AuthOut(BaseModel):
    token: str
    user: UserOut

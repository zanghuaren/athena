from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import DB
from app.errors import AppError
from app.models import User
from app.services import auth

_bearer = HTTPBearer(auto_error=False)


async def get_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None:
        raise AppError(401, "UNAUTHORIZED", "请先登录")
    return credentials.credentials


Token = Annotated[str, Depends(get_token)]


async def get_current_user(db: DB, token: Token) -> User:
    user = await auth.user_by_token(db, token)
    if user is None:
        raise AppError(401, "UNAUTHORIZED", "登录已过期，请重新登录")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

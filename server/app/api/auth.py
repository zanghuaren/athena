from fastapi import APIRouter, status

from app.api.deps import CurrentUser, Token
from app.db import DB
from app.schemas.auth import AuthOut, LoginIn, RegisterIn
from app.schemas.user import UserOut
from app.services import auth

router = APIRouter(prefix="/auth", tags=["账号"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(db: DB, body: RegisterIn) -> AuthOut:
    token, user = await auth.register(db, body)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.post("/login")
async def login(db: DB, body: LoginIn) -> AuthOut:
    token, user = await auth.login(db, body.username, body.password)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db: DB, token: Token, _: CurrentUser) -> None:
    await auth.logout(db, token)

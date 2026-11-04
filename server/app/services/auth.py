import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from math import ceil

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import Session, User
from app.schemas.auth import RegisterIn

SESSION_TTL = timedelta(days=30)
MAX_FAILED_LOGINS = 5
LOCK_DURATION = timedelta(minutes=10)
DEFAULT_AVATAR = "1"

_hasher = PasswordHasher()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _create_session(db: AsyncSession, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(UTC) + SESSION_TTL,
        )
    )
    return token


async def _find_user(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(select(User).where(func.lower(User.username) == username.lower()))


async def register(db: AsyncSession, data: RegisterIn) -> tuple[str, User]:
    if await _find_user(db, data.username):
        raise AppError(400, "USERNAME_TAKEN", "用户名已被使用", {"username": "用户名已被使用"})
    user = User(
        **data.model_dump(exclude={"password"}),
        password_hash=_hasher.hash(data.password),
        avatar=DEFAULT_AVATAR,
        explain_mode="guided" if data.role == "student" else None,
    )
    db.add(user)
    await db.flush()
    token = await _create_session(db, user)
    await db.commit()
    return token, user


async def login(db: AsyncSession, username: str, password: str) -> tuple[str, User]:
    user = await _find_user(db, username)
    if user is None:
        raise AppError(401, "LOGIN_FAILED", "用户名或密码错误")
    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        raise _locked_error(user.locked_until - now)

    try:
        _hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        if await _record_failure(db, user, now):
            raise _locked_error(LOCK_DURATION) from None
        raise AppError(401, "LOGIN_FAILED", "用户名或密码错误") from None

    user.failed_logins = 0
    user.locked_until = None
    token = await _create_session(db, user)
    await db.commit()
    return token, user


async def _record_failure(db: AsyncSession, user: User, now: datetime) -> bool:
    """记一次输错，返回这次是否触发了锁定。"""
    user.failed_logins += 1
    locked = user.failed_logins >= MAX_FAILED_LOGINS
    if locked:
        user.failed_logins = 0
        user.locked_until = now + LOCK_DURATION
    await db.commit()
    return locked


def _locked_error(remaining: timedelta) -> AppError:
    minutes = ceil(remaining.total_seconds() / 60)
    return AppError(423, "ACCOUNT_LOCKED", f"密码错误次数过多，请 {minutes} 分钟后再试")


async def logout(db: AsyncSession, token: str) -> None:
    await db.execute(delete(Session).where(Session.token_hash == _hash_token(token)))
    await db.commit()


async def user_by_token(db: AsyncSession, token: str) -> User | None:
    return await db.scalar(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(Session.token_hash == _hash_token(token), Session.expires_at > func.now())
    )

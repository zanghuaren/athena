import asyncio
import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy.engine import make_url

# 测试库和开发库同一个 PostgreSQL，库名加 _test；必须在导入 app 之前改掉
_dev_url = make_url(os.environ["DATABASE_URL"])
TEST_URL = _dev_url.set(database=f"{_dev_url.database}_test")
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


async def _recreate_test_database() -> None:
    conn = await asyncpg.connect(
        host=TEST_URL.host,
        port=TEST_URL.port,
        user=TEST_URL.username,
        password=TEST_URL.password,
        database="postgres",
    )
    await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_URL.database}" WITH (FORCE)')
    await conn.execute(f'CREATE DATABASE "{TEST_URL.database}"')
    await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _database():
    await _recreate_test_database()
    # 用迁移建表，顺便验证迁移本身能跑通
    proc = await asyncio.create_subprocess_exec("alembic", "upgrade", "head")
    assert await proc.wait() == 0
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables():
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    if tables:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

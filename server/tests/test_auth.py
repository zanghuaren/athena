from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.db import SessionLocal
from app.models import User

STUDENT = {
    "role": "student",
    "username": "xiaoya2026",
    "password": "abc12345",
    "display_name": "小雅",
    "grade": 8,
}
TEACHER = {
    "role": "teacher",
    "username": "teacher_li",
    "password": "abc12345",
    "display_name": "李老师",
    "teach_subjects": ["math"],
    "teach_grades": [8, 9],
}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client, username="xiaoya2026", password="abc12345"):
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


async def test_register_student_returns_token_for_me(client):
    resp = await client.post("/api/v1/auth/register", json=STUDENT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "student"
    assert body["user"]["explain_mode"] == "guided"

    me = await client.get("/api/v1/me", headers=auth(body["token"]))
    assert me.json()["display_name"] == "小雅"


async def test_register_teacher(client):
    resp = await client.post("/api/v1/auth/register", json=TEACHER)
    assert resp.status_code == 201
    user = resp.json()["user"]
    assert user["teach_grades"] == [8, 9]
    assert user["explain_mode"] is None


async def test_username_taken_ignores_case(client):
    await client.post("/api/v1/auth/register", json=STUDENT)
    resp = await client.post("/api/v1/auth/register", json={**STUDENT, "username": "XiaoYa2026"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "USERNAME_TAKEN"
    assert resp.json()["error"]["fields"] == {"username": "用户名已被使用"}


async def test_register_validation_messages(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={**STUDENT, "username": "ab", "password": "onlyletters"},
    )
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["fields"]["username"] == "用户名为 4～20 位字母、数字或下划线"
    assert error["fields"]["password"] == "密码为 8～32 位，必须同时包含字母和数字"


async def test_teacher_requires_subjects(client):
    resp = await client.post("/api/v1/auth/register", json={**TEACHER, "teach_subjects": []})
    assert resp.status_code == 400
    assert "teach_subjects" in resp.json()["error"]["fields"]


async def test_login_wrong_password_and_unknown_user_same_message(client):
    await client.post("/api/v1/auth/register", json=STUDENT)
    wrong = await login(client, password="wrong1234")
    unknown = await login(client, username="nobody")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["message"] == "用户名或密码错误"


async def test_fifth_failure_locks_account(client):
    await client.post("/api/v1/auth/register", json=STUDENT)
    for _ in range(4):
        assert (await login(client, password="wrong1234")).status_code == 401
    fifth = await login(client, password="wrong1234")
    assert fifth.status_code == 423
    assert fifth.json()["error"]["message"] == "密码错误次数过多，请 10 分钟后再试"

    correct = await login(client)
    assert correct.status_code == 423


async def test_login_works_after_lock_expires(client):
    await client.post("/api/v1/auth/register", json=STUDENT)
    for _ in range(5):
        await login(client, password="wrong1234")
    async with SessionLocal() as db:
        await db.execute(update(User).values(locked_until=datetime.now(UTC) - timedelta(seconds=1)))
        await db.commit()

    assert (await login(client)).status_code == 200
    # 锁定过期后重新计数：再错一次不应该立即锁定
    assert (await login(client, password="wrong1234")).status_code == 401


async def test_logout_invalidates_token(client):
    token = (await client.post("/api/v1/auth/register", json=STUDENT)).json()["token"]
    assert (await client.post("/api/v1/auth/logout", headers=auth(token))).status_code == 204
    resp = await client.get("/api/v1/me", headers=auth(token))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_requires_token(client):
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"

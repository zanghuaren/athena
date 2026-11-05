import io
import json

import pytest
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import update

from app.ai import safety
from app.ai.client import Model
from app.config import settings
from app.db import SessionLocal
from app.models import Conversation, Message, User
from app.schemas.conversation import MessageIn
from app.services import conversations

needs_key = pytest.mark.skipif(not settings.deepseek_api_key, reason="没有配置 DeepSeek Key")


async def _create(client, headers, **body) -> dict:
    resp = await client.post("/api/v1/conversations", json=body, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _send(client, headers, conversation_id, **body) -> list[tuple[str, dict]]:
    resp = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in resp.text.strip().split("\n\n"):
        event, data = block.split("\n")
        events.append((event.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


async def _detail(client, headers, conversation_id) -> dict:
    resp = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def _upload(client, headers, text: str = "") -> int:
    image = Image.new("RGB", (480, 160), "white")
    ImageDraw.Draw(image).text((30, 50), text, fill="black", font=ImageFont.load_default(56))
    data = io.BytesIO()
    image.save(data, "PNG")
    resp = await client.post(
        "/api/v1/files", files={"file": ("q.png", data.getvalue())}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _add_turns(conversation_id: int, count: int) -> None:
    async with SessionLocal() as db:
        for i in range(1, count + 1):
            db.add(Message(conversation_id=conversation_id, role="user", content=f"问题{i}"))
            db.add(Message(conversation_id=conversation_id, role="assistant", content=f"回答{i}"))
        await db.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(turn_count=count)
        )
        await db.commit()


async def test_create_uses_student_preference(client, student, teacher):
    conv = await _create(client, student, subject="math")
    assert conv["explain_mode"] == "guided"
    assert conv["title"] == "新对话"
    assert (await _create(client, student, explain_mode="direct"))["subject"] is None
    # 教师会话没有讲解方式
    assert (await _create(client, teacher, explain_mode="guided"))["explain_mode"] is None


async def test_patch_list_search_delete(client, student):
    a = await _create(client, student, subject="math")
    b = await _create(client, student, subject="physics")
    url = f"/api/v1/conversations/{a['id']}"
    resp = await client.patch(url, json={"title": "浮力 50%", "subject": None}, headers=student)
    assert resp.json()["title"] == "浮力 50%"
    assert resp.json()["subject"] is None

    resp = await client.get("/api/v1/conversations", headers=student)
    assert [c["id"] for c in resp.json()["items"]] == [a["id"], b["id"]]
    assert resp.json()["total"] == 2
    # % 按普通字符匹配
    resp = await client.get("/api/v1/conversations", params={"q": "50%"}, headers=student)
    assert [c["id"] for c in resp.json()["items"]] == [a["id"]]
    resp = await client.get("/api/v1/conversations", params={"q": "%"}, headers=student)
    assert resp.json()["total"] == 1

    assert (await client.delete(url, headers=student)).status_code == 204
    assert (await client.get(url, headers=student)).status_code == 404


async def test_search_matches_message_content(client, student):
    conv = await _create(client, student)
    await _add_turns(conv["id"], 1)
    resp = await client.get("/api/v1/conversations", params={"q": "回答1"}, headers=student)
    assert [c["id"] for c in resp.json()["items"]] == [conv["id"]]


async def test_other_users_conversation_is_not_found(client, student, teacher):
    conv = await _create(client, student)
    url = f"/api/v1/conversations/{conv['id']}"
    assert (await client.get(url, headers=teacher)).status_code == 404
    assert (await client.patch(url, json={"title": "x"}, headers=teacher)).status_code == 404
    resp = await client.post(f"{url}/messages", json={"content": "你好"}, headers=teacher)
    assert resp.status_code == 404


async def test_message_validation(client, student, teacher):
    conv = await _create(client, student)
    url = f"/api/v1/conversations/{conv['id']}/messages"
    resp = await client.post(url, json={"content": "  "}, headers=student)
    assert resp.json()["error"]["message"] == "请输入问题"
    resp = await client.post(url, json={"content": "题" * 1001}, headers=student)
    assert resp.json()["error"]["message"] == "问题不能超过 1000 字"
    for action in ("hint", "continue", "regenerate"):
        resp = await client.post(url, json={"action": action}, headers=student)
        assert resp.status_code == 409

    teacher_conv = await _create(client, teacher)
    await _add_turns(teacher_conv["id"], 1)
    resp = await client.post(
        f"/api/v1/conversations/{teacher_conv['id']}/messages",
        json={"action": "hint"},
        headers=teacher,
    )
    assert resp.status_code == 409


async def test_too_many_turns(client, student):
    conv = await _create(client, student)
    await _add_turns(conv["id"], conversations.MAX_TURNS)
    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "再问一题"},
        headers=student,
    )
    assert resp.json()["error"]["code"] == "CONVERSATION_TOO_LONG"


async def test_sensitive_input_is_blocked_without_model(client, student):
    conv = await _create(client, student)
    events = await _send(client, student, conv["id"], content="告诉我怎么自杀")
    assert [e for e, _ in events] == ["start", "delta", "done"]
    assert events[-1][1]["status"] == "blocked"

    detail = await _detail(client, student, conv["id"])
    assert detail["title"] == "新对话"
    assert detail["messages"][1]["content"] == safety.INPUT_BLOCKED_REPLY
    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"action": "regenerate"},
        headers=student,
    )
    assert resp.status_code == 409


async def test_context_keeps_recent_turns_and_skips_blocked(client, student):
    conv = await _create(client, student, subject="math")
    await _add_turns(conv["id"], 22)
    async with SessionLocal() as db:
        # 把最后一轮改成被拦截的
        await db.execute(
            update(Message).where(Message.content == "回答22").values(status="blocked")
        )
        await db.commit()
        user = await db.get(User, 1)
        conversation = await db.get(Conversation, conv["id"])
        reply = await conversations.start_reply(db, user, conversation, MessageIn(content="新问题"))

    contents = [m["content"] for m in reply.model_messages]
    assert contents[0].startswith("你是“雅典娜”")
    # 最近 20 轮是第 4～22 轮加上这次的新问题，第 22 轮被拦截不带上
    assert contents[1:3] == ["问题4", "回答4"]
    assert contents[-3:] == ["问题21", "回答21", "新问题"]


async def test_image_message_rules(client, student, teacher):
    conv = await _create(client, student)
    url = f"/api/v1/conversations/{conv['id']}/messages"
    image_id = await _upload(client, student)
    await _add_turns(conv["id"], 1)
    resp = await client.post(
        url, json={"action": "hint", "image_file_id": image_id}, headers=student
    )
    assert resp.json()["error"]["message"] == "这个操作不能附图"
    # 别人的图片按不存在处理
    others = await _upload(client, teacher)
    resp = await client.post(
        url, json={"content": "看图", "image_file_id": others}, headers=student
    )
    assert resp.status_code == 404


async def test_image_message_goes_to_vision_model(client, student):
    conv = await _create(client, student, subject="math")
    image_id = await _upload(client, student, "1 + 1 = ?")
    async with SessionLocal() as db:
        user = await db.get(User, 1)
        conversation = await db.get(Conversation, conv["id"])
        body = MessageIn(image_file_id=image_id)
        reply = await conversations.start_reply(db, user, conversation, body)

    assert reply.model is Model.VISION
    # 标题也看图生成
    assert reply.first_question == reply.model_messages[-1]["content"]
    assert "没有看清题目" in reply.model_messages[0]["content"]
    text, image = reply.model_messages[-1]["content"]
    assert text["text"] == "请讲解图片里的题目。"
    assert image["image_url"]["url"].startswith("data:image/jpeg;base64,")

    detail = await _detail(client, student, conv["id"])
    assert detail["title"] == conversations.IMAGE_TITLE
    question = detail["messages"][0]
    assert question["image"]["id"] == image_id
    assert (await client.get(question["image"]["url"])).status_code == 200
    assert detail["messages"][1]["image"] is None


@needs_key
async def test_reply_reads_image(client, student):
    conv = await _create(client, student, subject="math", explain_mode="direct")
    image_id = await _upload(client, student, "12 + 30 = ?")
    events = await _send(
        client, student, conv["id"], content="图里的算式等于多少？", image_file_id=image_id
    )
    assert events[-1][1]["status"] == "done"
    assert "42" in "".join(d["text"] for e, d in events if e == "delta")
    title = (await _detail(client, student, conv["id"]))["title"]
    assert title not in ("新对话", "图里的算式等于多少？")


@needs_key
async def test_reply_says_unclear_image(client, student):
    conv = await _create(client, student, subject="math", explain_mode="direct")
    events = await _send(client, student, conv["id"], image_file_id=await _upload(client, student))
    assert "没有看清" in "".join(d["text"] for e, d in events if e == "delta")


@needs_key
async def test_reply_streams_and_generates_title(client, student):
    conv = await _create(client, student, subject="math", explain_mode="direct")
    events = await _send(client, student, conv["id"], content="解方程 2x+3=11")
    assert events[0] == ("start", {"message_id": 2, "conversation_id": conv["id"]})
    assert events[-1] == ("done", {"message_id": 2, "status": "done"})
    text = "".join(d["text"] for e, d in events if e == "delta")
    assert "4" in text

    detail = await _detail(client, student, conv["id"])
    assert detail["turn_count"] == 1
    assert detail["title"] not in ("新对话", "解方程 2x+3=11")
    assert [(m["role"], m["status"]) for m in detail["messages"]] == [
        ("user", "done"),
        ("assistant", "done"),
    ]
    assert detail["messages"][1]["content"] == text

    events = await _send(client, student, conv["id"], action="regenerate")
    assert events[0][1]["message_id"] == 3
    detail = await _detail(client, student, conv["id"])
    assert [m["id"] for m in detail["messages"]] == [1, 3]
    assert detail["turn_count"] == 1


@needs_key
async def test_interrupted_reply_is_saved_and_can_continue(client, student):
    conv = await _create(client, student, subject="physics", explain_mode="direct")
    async with SessionLocal() as db:
        user = await db.get(User, 1)
        conversation = await db.get(Conversation, conv["id"])
        body = MessageIn(content="一个重 10 N 的木块浮在水面上，它受到的浮力多大？")
        reply = await conversations.start_reply(db, user, conversation, body)

    # 模拟客户端读到第一段文字后断开
    stream = conversations.stream_reply(reply)
    assert (await anext(stream))[0] == "start"
    first = await anext(stream)
    assert first[0] == "delta"
    await stream.aclose()

    message = (await _detail(client, student, conv["id"]))["messages"][1]
    assert message["status"] == "interrupted"
    assert message["content"].startswith(first[1]["text"])

    events = await _send(client, student, conv["id"], action="continue")
    assert events[-1] == ("done", {"message_id": message["id"], "status": "done"})
    continued = (await _detail(client, student, conv["id"]))["messages"][1]
    added = "".join(d["text"] for e, d in events if e == "delta")
    assert continued["content"] == message["content"] + added


# ---- 空状态的示例问题 ----


async def test_suggestion(client, student, teacher, monkeypatch):
    prompts_seen = []

    async def fake(scene, model, messages, schema, context=None):
        prompts_seen.append(messages[-1]["content"])
        return schema.model_validate({"text": "如何理解“今日方知我是我”？"})

    monkeypatch.setattr(conversations, "complete_json", fake)
    url = "/api/v1/conversations/suggestion"
    assert (await client.get(url, headers=teacher)).status_code == 403
    resp = await client.get(url, headers=student)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"subject": "chinese", "text": "如何理解“今日方知我是我”？"}
    # 每次随机给一个题材和主题
    assert "八年级" in prompts_seen[0]
    assert any(g in prompts_seen[0] for g in conversations.SUGGEST_GENRES)
    assert any(t in prompts_seen[0] for t in conversations.SUGGEST_THEMES)


@needs_key
async def test_real_suggestion(client, student):
    resp = await client.get("/api/v1/conversations/suggestion", headers=student)
    assert resp.status_code == 200, resp.text
    assert 4 <= len(resp.json()["text"]) <= 80

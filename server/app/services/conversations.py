"""AI 答疑（ASK）：会话管理和流式回答，技术方案 5.3。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass

import anyio
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts, safety
from app.ai.client import Model, complete_json, complete_text, stream_text
from app.db import SessionLocal
from app.errors import AppError
from app.models import Chapter, Conversation, KnowledgePoint, Message, User
from app.schemas.conversation import (
    ConversationIn,
    ConversationPatch,
    MessageIn,
    Suggested,
    Suggestion,
)
from app.services import files

logger = logging.getLogger(__name__)

MAX_TURNS = 50
CONTEXT_TURNS = 20
DEFAULT_TITLE = "新对话"
IMAGE_TITLE = "图片提问"
_GRADE_NAMES = {7: "七年级（初一）", 8: "八年级（初二）", 9: "九年级（初三）"}


@dataclass
class Reply:
    """一次回答要用到的全部信息，在建立流之前准备好。"""

    conversation_id: int
    message_id: int
    model_messages: list[dict]
    # 继续生成时接在已有内容后面
    prefix: str = ""
    # 输入命中敏感词时不调用模型，直接回复这段话
    blocked_reply: str | None = None
    # 会话的第一个问题（和交给模型的内容一样，可能带图）：回答的同时用它生成标题
    first_question: str | list[dict] | None = None

    @property
    def model(self) -> Model:
        has_image = any(isinstance(m["content"], list) for m in self.model_messages)
        return Model.VISION if has_image else Model.FAST


# ---------- 会话管理 ----------


async def list_page(
    db: AsyncSession, user: User, q: str | None, page: int, page_size: int
) -> tuple[list[Conversation], int]:
    query = select(Conversation).where(Conversation.user_id == user.id)
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        in_messages = exists().where(
            Message.conversation_id == Conversation.id, Message.content.ilike(pattern)
        )
        query = query.where(or_(Conversation.title.ilike(pattern), in_messages))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    items = await db.scalars(
        query.order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items), total or 0


async def create(db: AsyncSession, user: User, data: ConversationIn) -> Conversation:
    explain_mode = (data.explain_mode or user.explain_mode) if user.role == "student" else None
    conversation = Conversation(
        user_id=user.id, title=DEFAULT_TITLE, subject=data.subject, explain_mode=explain_mode
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_owned(db: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise AppError(404, "NOT_FOUND", "会话不存在或已被删除")
    return conversation


async def messages_of(db: AsyncSession, conversation_id: int) -> list[Message]:
    rows = await db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    )
    return list(rows)


async def patch(
    db: AsyncSession, user: User, conversation_id: int, data: ConversationPatch
) -> Conversation:
    conversation = await get_owned(db, user, conversation_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("title") is None:
        changes.pop("title", None)
    # 教师会话没有讲解方式
    if user.role != "student" or changes.get("explain_mode") is None:
        changes.pop("explain_mode", None)
    for key, value in changes.items():
        setattr(conversation, key, value)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def remove(db: AsyncSession, user: User, conversation_id: int) -> None:
    conversation = await get_owned(db, user, conversation_id)
    await db.delete(conversation)
    await db.commit()


# ---------- 回答 ----------


async def start_reply(
    db: AsyncSession, user: User, conversation: Conversation, data: MessageIn
) -> Reply:
    """校验动作、写入消息，并拼好发给模型的上下文。出错时还没有建立流，照常返回 JSON 错误。"""
    history = await messages_of(db, conversation.id)
    last = history[-1] if history else None
    _check_action(user, conversation, data, last)
    image = await files.get_owned(db, user, data.image_file_id) if data.image_file_id else None

    if data.action == "continue":
        assert last is not None
        model_messages = await _model_messages(user, conversation, history[:-1])
        return Reply(conversation.id, last.id, model_messages, prefix=last.content)

    blocked = data.action is None and safety.is_sensitive(data.content)
    is_first = False
    if data.action == "regenerate":
        assert last is not None
        await db.delete(last)
        history.pop()
    else:
        content = "" if data.action else data.content.strip()
        question = Message(
            conversation_id=conversation.id,
            role="user",
            action=data.action,
            content=content,
            image_file=image,
        )
        db.add(question)
        history.append(question)
        conversation.turn_count += 1
        if conversation.turn_count == 1 and not blocked:
            is_first = True
            conversation.title = content[:20] or IMAGE_TITLE

    answer = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=safety.INPUT_BLOCKED_REPLY if blocked else "",
        # 先记为已中断：生成途中服务异常退出时，留下的就是这个状态
        status="blocked" if blocked else "interrupted",
    )
    db.add(answer)
    await db.commit()
    if blocked:
        logger.warning("ask input blocked conversation=%s", conversation.id)
        return Reply(conversation.id, answer.id, [], blocked_reply=answer.content)
    model_messages = await _model_messages(user, conversation, history)
    first_question = model_messages[-1]["content"] if is_first else None
    return Reply(conversation.id, answer.id, model_messages, first_question=first_question)


def _check_action(
    user: User, conversation: Conversation, data: MessageIn, last: Message | None
) -> None:
    def reject(message: str):
        raise AppError(409, "CONFLICT", message)

    match data.action:
        case "continue":
            if last is None or last.role != "assistant" or last.status != "interrupted":
                reject("没有可以继续生成的回答")
        case "regenerate":
            # 被拦截的问题重新生成也还是拦截，不再交给模型
            if last is None or last.role != "assistant" or last.status == "blocked":
                reject("没有可以重新生成的回答")
        case _:
            if conversation.turn_count >= MAX_TURNS:
                raise AppError(400, "CONVERSATION_TOO_LONG", "这个会话太长了，开一个新会话吧")
            if data.action and (last is None or last.role != "assistant"):
                reject("请先提一个问题")
            # 教师端没有引导式，也就没有“再给点提示”“看完整解答”（ASK-07）
            if data.action in ("hint", "full") and user.role != "student":
                reject("教师端不支持这个操作")


def _system_prompt(user: User, conversation: Conversation, has_image: bool) -> str:
    if user.role == "student":
        parts = [prompts.render("ask/student", grade=_GRADE_NAMES.get(user.grade, "初中"))]
    else:
        parts = [prompts.load("ask/teacher")]
    parts.append(prompts.load(f"ask/{conversation.subject or 'auto'}"))
    if conversation.explain_mode:
        parts.append(prompts.load(f"ask/{conversation.explain_mode}"))
    if has_image:
        parts.append(prompts.load("ask/image"))
    parts += [prompts.load("format"), prompts.load("safety")]
    if conversation.summary:
        parts.append(f"## 更早的对话摘要\n\n{conversation.summary}")
    return "\n\n".join(parts)


def _turns(history: list[Message]) -> list[list[Message]]:
    """按学生的消息切分成轮，每轮是一条学生消息加上后面的回答。"""
    turns: list[list[Message]] = []
    for message in history:
        if message.role == "user" or not turns:
            turns.append([])
        turns[-1].append(message)
    return turns


def _as_model_message(message: Message) -> dict:
    if message.role == "user" and message.action:
        # 按钮动作换成对应的指令交给模型，不作为学生的原话
        return {"role": "user", "content": prompts.load(f"ask/{message.action}")}
    return {"role": message.role, "content": message.content}


async def _model_messages(
    user: User, conversation: Conversation, history: list[Message]
) -> list[dict]:
    # 被拦截的一轮不再交给模型；还没有内容的回答（正在生成的这条）也跳过
    turns = [
        turn
        for turn in _turns(history)[-CONTEXT_TURNS:]
        if not any(m.status == "blocked" for m in turn)
    ]
    has_image = any(m.image_file for turn in turns for m in turn)
    messages = [{"role": "system", "content": _system_prompt(user, conversation, has_image)}]
    for message in (m for turn in turns for m in turn if m.role == "user" or m.content):
        entry = _as_model_message(message)
        if message.image_file:
            entry["content"] = [
                {"type": "text", "text": entry["content"] or "请讲解图片里的题目。"},
                {
                    "type": "image_url",
                    "image_url": {"url": await files.data_url(message.image_file)},
                },
            ]
        messages.append(entry)
    return messages


async def stream_reply(reply: Reply) -> AsyncIterator[tuple[str, dict]]:
    """产出 SSE 事件（接口约定 2.1）。客户端断开时已生成的部分照样保存，状态为已中断。"""
    yield "start", {"message_id": reply.message_id, "conversation_id": reply.conversation_id}
    if reply.blocked_reply:
        yield "delta", {"text": reply.blocked_reply}
        yield "done", {"message_id": reply.message_id, "status": "blocked"}
        return

    # 标题只看问题就够了，和回答同时生成，回答结束时通常已经好了
    title_task = asyncio.create_task(_title(reply.first_question)) if reply.first_question else None
    text = reply.prefix
    status = "interrupted"
    try:
        async with aclosing(
            stream_text("ask", reply.model, reply.model_messages, reply.prefix)
        ) as pieces:
            async for piece in pieces:
                text += piece
                # 敏感词可能被切在两段之间，往前多看几个字
                if safety.is_sensitive(text[-len(piece) - 10 :]):
                    logger.warning("ask output blocked message=%s", reply.message_id)
                    text, status = safety.OUTPUT_BLOCKED_REPLY, "blocked"
                    yield "replace", {"text": text}
                    break
                yield "delta", {"text": piece}
            else:
                status = "done"
        yield "done", {"message_id": reply.message_id, "status": status}
    except AppError as exc:
        yield "error", {"code": exc.code, "message": exc.message}
    finally:
        # 客户端断开时这里会被取消，保存不能跟着取消
        with anyio.CancelScope(shield=True):
            async with SessionLocal() as db:
                await db.execute(
                    update(Message)
                    .where(Message.id == reply.message_id)
                    .values(content=text, status=status)
                )
                if title_task and (title := await title_task):
                    await db.execute(
                        update(Conversation)
                        .where(Conversation.id == reply.conversation_id)
                        .values(title=title)
                    )
                await db.commit()


# ---------- 空状态的示例问题 ----------

SUBJECT_ORDER = ("math", "physics", "english")


async def suggestions(db: AsyncSession, user: User) -> list[Suggestion]:
    """每科随机取一个学生所在年级的知识点，让 MODEL_FAST 用学生的口吻各问一个问题。"""
    points = []
    for subject in SUBJECT_ORDER:
        query = (
            select(KnowledgePoint, Chapter)
            .join(Chapter)
            .where(Chapter.subject == subject)
            .order_by(func.random())
            .limit(1)
        )
        if user.grade is not None:
            query = query.where(KnowledgePoint.grades.contains([user.grade]))
        row = (await db.execute(query)).first()
        if row is not None:
            points.append(row)
    if not points:
        return []
    lines = [f"{p.code}｜{c.subject}｜{c.title}｜{p.name}｜{p.description}" for p, c in points]
    grade = _GRADE_NAMES.get(user.grade or 0, "初中")
    messages = [
        {"role": "system", "content": f"{prompts.load('ask/suggest')}\n\n{prompts.load('safety')}"},
        {"role": "user", "content": f"年级：{grade}\n\n" + "\n".join(lines)},
    ]
    suggested = await complete_json(
        "ask_suggest",
        Model.FAST,
        messages,
        Suggested,
        context={"codes": [p.code for p, _ in points]},
    )
    return [
        Suggestion(subject=c.subject, text=q.text.strip())
        for (_, c), q in zip(points, suggested.questions, strict=True)
    ]


# ---------- 标题和摘要：失败了不影响对话 ----------


async def _title(question: str | list[dict]) -> str | None:
    messages = [
        {"role": "system", "content": prompts.load("ask/title")},
        {"role": "user", "content": question},
    ]
    # 学生可能只写了“讲一下第一题”，题目在图里，标题也要看图
    model = Model.VISION if isinstance(question, list) else Model.FAST
    try:
        title = await complete_text("ask_title", model, messages)
    except AppError as exc:
        logger.warning("ask title failed: %s", exc.code)
        return None
    return title.strip().strip('“”"《》。')[:30] or None


async def after_reply(conversation_id: int, new_turn: bool) -> None:
    """超过 20 轮后，把刚移出上下文的那一轮并进摘要。"""
    if not new_turn:
        return
    async with SessionLocal() as db:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None or conversation.turn_count <= CONTEXT_TURNS:
            return
        turns = _turns(await messages_of(db, conversation_id))
        try:
            await _merge_summary(conversation, turns[-CONTEXT_TURNS - 1])
        except AppError as exc:
            logger.warning("ask summary failed conversation=%s: %s", conversation_id, exc.code)
            return
        await db.commit()


def _turn_text(turn: list[Message]) -> str:
    names = {"user": "学生", "assistant": "老师"}
    lines = []
    for m in turn:
        image = "（附了一张图片）" if m.image_file_id else ""
        lines.append(f"{names[m.role]}：{_as_model_message(m)['content']}{image}")
    return "\n\n".join(lines)


async def _merge_summary(conversation: Conversation, turn: list[Message]) -> None:
    if any(m.status == "blocked" for m in turn):
        return
    text = f"已有摘要：\n{conversation.summary or '（无）'}\n\n这一轮对话：\n{_turn_text(turn)}"
    messages = [
        {"role": "system", "content": prompts.load("ask/summary")},
        {"role": "user", "content": text},
    ]
    conversation.summary = (await complete_text("ask_summary", Model.FAST, messages)).strip()

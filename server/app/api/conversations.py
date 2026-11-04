import json
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.deps import CurrentUser
from app.db import DB
from app.schemas.conversation import (
    ConversationDetail,
    ConversationIn,
    ConversationOut,
    ConversationPage,
    ConversationPatch,
    MessageIn,
    MessageOut,
)
from app.services import conversations

router = APIRouter(prefix="/conversations", tags=["答疑"])


@router.get("")
async def list_conversations(
    db: DB,
    user: CurrentUser,
    q: Annotated[str | None, Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationPage:
    items, total = await conversations.list_page(db, user, q, page, page_size)
    return ConversationPage(
        items=[ConversationOut.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(db: DB, user: CurrentUser, body: ConversationIn) -> ConversationOut:
    return ConversationOut.model_validate(await conversations.create(db, user, body))


@router.get("/{conversation_id}")
async def get_conversation(db: DB, user: CurrentUser, conversation_id: int) -> ConversationDetail:
    conversation = await conversations.get_owned(db, user, conversation_id)
    messages = await conversations.messages_of(db, conversation_id)
    return ConversationDetail(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.patch("/{conversation_id}")
async def patch_conversation(
    db: DB, user: CurrentUser, conversation_id: int, body: ConversationPatch
) -> ConversationOut:
    return ConversationOut.model_validate(
        await conversations.patch(db, user, conversation_id, body)
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(db: DB, user: CurrentUser, conversation_id: int) -> None:
    await conversations.remove(db, user, conversation_id)


@router.post(
    "/{conversation_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE，见接口约定 2.1"}},
)
async def send_message(db: DB, user: CurrentUser, conversation_id: int, body: MessageIn):
    conversation = await conversations.get_owned(db, user, conversation_id)
    reply = await conversations.start_reply(db, user, conversation, body)

    async def events():
        async for event, data in conversations.stream_reply(reply):
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    new_turn = body.action not in ("continue", "regenerate")
    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # nginx 默认会缓冲响应，流式输出要关掉
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=BackgroundTask(conversations.after_reply, conversation_id, new_turn),
    )

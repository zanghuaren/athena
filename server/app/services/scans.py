"""拍照识题与批改（SCAN），技术方案 5.4。"""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts
from app.ai.client import Model, complete_json
from app.errors import AppError
from app.models import User
from app.schemas.scan import Recognized, RecognizeOut
from app.services import files


async def recognize(db: AsyncSession, user: User, image_file_id: int) -> RecognizeOut:
    image = await files.get_owned(db, user, image_file_id)
    messages = [
        {"role": "system", "content": prompts.load("scan/recognize")},
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": await files.data_url(image)}}],
        },
    ]
    result = await complete_json("scan_recognize", Model.VISION, messages, Recognized)
    if result.status == "empty":
        raise AppError(400, "NO_QUESTION_FOUND", "没有识别到题目")
    if result.status == "multiple":
        raise AppError(400, "MULTIPLE_QUESTIONS", "请只框选一道题")
    return RecognizeOut(subject=result.subject, text=_table_separators(result.text.strip()))


_SEPARATOR = re.compile(r"\|(\s*:?-+:?\s*\|)+")


def _table_separators(text: str) -> str:
    # 提示词里要求了，模型仍常漏掉表头下面的分隔行，Markdown 就不把它当表格
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        header = line.startswith("|") and (i == 0 or not lines[i - 1].startswith("|"))
        below = lines[i + 1] if i + 1 < len(lines) else ""
        if header and below.startswith("|") and not _SEPARATOR.fullmatch(below.strip()):
            out.append("|" + " --- |" * (line.count("|") - 1))
    return "\n".join(out)

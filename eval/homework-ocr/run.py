"""用产品里的看图模型整页识别 30 张作业照片，原始输出存到 runs/<时间>/。

在项目根目录运行（需要 api 容器里的依赖和模型密钥）：

    docker compose -f deploy/compose.dev.yml run --rm -v "$PWD/eval:/eval" -e PYTHONPATH=/app \
        api python /eval/homework-ocr/run.py

参考转写没有全部冻结（status 为 frozen）时拒绝运行；加 --draft 可以先试跑，
结果记为非正式，不能作为准确率结论。
--try <图片> 只识别一张图并打印结果，用来检查脚本。
"""

import argparse
import asyncio
import base64
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from app.ai.client import Model, complete_json
from app.config import settings
from app.errors import AppError
from app.services.files import _to_jpeg
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
PROMPT = (ROOT / "prompt.md").read_text(encoding="utf-8").strip()
CONCURRENCY = 5


class PageQuestion(BaseModel):
    printed: str = ""
    handwritten: list[str] = []


class PageOut(BaseModel):
    questions: list[PageQuestion]


async def recognize(image: bytes) -> tuple[PageOut, int]:
    # 和产品上传一样先转 JPEG、长边压到 2048，模型看到的就是线上的图
    jpeg, _, _ = _to_jpeg(image)
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}]},
    ]
    started = time.monotonic()
    out = await complete_json("eval_homework_ocr", Model.VISION, messages, PageOut)
    return out, int((time.monotonic() - started) * 1000)


async def run_all(out_dir: Path) -> None:
    entries = [json.loads(line) for line in (ROOT / "manifest.jsonl").read_text().splitlines()]
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def one(entry: dict) -> None:
        async with semaphore:
            try:
                page, ms = await recognize((ROOT / entry["file"]).read_bytes())
                result = {"id": entry["id"], "ms": ms, "output": page.model_dump()}
            except AppError as exc:  # 记下失败继续跑，失败的页按全错计分
                result = {"id": entry["id"], "error": exc.code}
        (out_dir / f"{entry['id']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(entry["id"], result.get("ms", result.get("error")), flush=True)

    await asyncio.gather(*(one(e) for e in entries))


def check_frozen() -> None:
    drafts = [
        p.stem
        for p in sorted((ROOT / "references").glob("*.json"))
        if json.loads(p.read_text())["status"] != "frozen"
    ]
    if drafts:
        sys.exit(f"参考转写还没冻结：{', '.join(drafts)}。复核后把 status 改成 frozen 再运行")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--try", dest="try_image", type=Path, help="只识别这一张图并打印结果")
    parser.add_argument(
        "--draft", action="store_true", help="参考转写没冻结也运行，结果只作方向判断"
    )
    args = parser.parse_args()
    if args.try_image:
        page, ms = asyncio.run(recognize(args.try_image.read_bytes()))
        print(json.dumps(page.model_dump(), ensure_ascii=False, indent=2), f"\n{ms} ms")
        return

    if not args.draft:
        check_frozen()
    out_dir = ROOT / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    meta = {
        "draft": args.draft,
        "model": settings.model_vision,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "references_sha256": hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted((ROOT / "references").glob("*.json")))
        ).hexdigest(),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    asyncio.run(run_all(out_dir))
    print(f"输出在 {out_dir.relative_to(ROOT)}，用 score.py 计分")


if __name__ == "__main__":
    main()

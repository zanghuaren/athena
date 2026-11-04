"""导入预置数据：python -m seed。可以重复运行。"""

import asyncio
from pathlib import Path

from app.db import SessionLocal, engine
from app.services.knowledge import KnowledgeCatalog, import_catalog

SEED_DIR = Path(__file__).parent


async def main() -> None:
    async with SessionLocal() as db:
        for path in sorted((SEED_DIR / "knowledge").glob("*.json")):
            catalog = KnowledgeCatalog.model_validate_json(path.read_text())
            await import_catalog(db, catalog)
            count = sum(len(ch.points) for ch in catalog.chapters)
            print(f"{path.name}: {len(catalog.chapters)} 个章节，{count} 个知识点")
    await engine.dispose()


asyncio.run(main())

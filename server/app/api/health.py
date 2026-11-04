from fastapi import APIRouter
from sqlalchemy import text

from app.db import DB

router = APIRouter(tags=["公共"])


@router.get("/health")
async def health(db: DB) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}

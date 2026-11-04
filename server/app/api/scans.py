from fastapi import APIRouter

from app.api.deps import CurrentStudent
from app.db import DB
from app.schemas.scan import RecognizeIn, RecognizeOut
from app.services import scans

router = APIRouter(tags=["拍照识题与批改"])


@router.post("/recognize")
async def recognize(db: DB, user: CurrentStudent, body: RecognizeIn) -> RecognizeOut:
    return await scans.recognize(db, user, body.image_file_id)

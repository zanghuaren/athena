from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser
from app.config import settings
from app.db import DB
from app.schemas.file import FileOut
from app.services import files

router = APIRouter(prefix="/files", tags=["文件"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(db: DB, user: CurrentUser, file: UploadFile) -> FileOut:
    # 多读 1 个字节，就能知道是否超过上限
    data = await file.read(files.MAX_SIZE + 1)
    return files.file_out(await files.save_image(db, user, data))


@router.get("/{file_id}", response_class=FileResponse)
async def download_file(db: DB, file_id: int, exp: int, sig: str):
    """凭签名访问，不需要登录，这样 <img> 可以直接用。"""
    file = await files.get_signed(db, file_id, exp, sig)
    return FileResponse(
        settings.files_dir / file.path,
        media_type=file.mime,
        headers={"Cache-Control": f"private, max-age={files.URL_TTL}"},
    )

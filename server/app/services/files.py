"""文件：上传的图片统一转成 JPEG，访问地址带过期时间和签名，见接口约定 2.3、技术方案第 8 节。"""

import hashlib
import hmac
import io
import time
import uuid
from datetime import date

import anyio
import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.models import File, User
from app.schemas.file import FileOut

MAX_SIZE = 10 * 1024 * 1024
MAX_SIDE = 2048
URL_TTL = 3600
# MPO 是部分手机相机拍出的 jpg
_FORMATS = {"JPEG", "MPO", "PNG", "HEIF", "WEBP"}

pillow_heif.register_heif_opener()


async def save_image(db: AsyncSession, user: User, data: bytes) -> File:
    if len(data) > MAX_SIZE:
        raise AppError(413, "FILE_TOO_LARGE", "图片不能超过 10 MB")
    jpeg, width, height = await anyio.to_thread.run_sync(_to_jpeg, data)
    path = f"{date.today():%Y/%m}/{uuid.uuid4().hex}.jpg"
    target = anyio.Path(settings.files_dir / path)
    await target.parent.mkdir(parents=True, exist_ok=True)
    await target.write_bytes(jpeg)
    file = File(
        owner_id=user.id,
        kind="image",
        path=path,
        mime="image/jpeg",
        size=len(jpeg),
        width=width,
        height=height,
    )
    db.add(file)
    await db.commit()
    return file


def _to_jpeg(data: bytes) -> tuple[bytes, int, int]:
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in _FORMATS:
            raise UnidentifiedImageError
        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        image = _on_white(image)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise AppError(
            400, "FILE_TYPE_UNSUPPORTED", "只支持 jpg、png、heic、webp 格式的图片"
        ) from exc
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue(), image.width, image.height


def _on_white(image: Image.Image) -> Image.Image:
    # 透明背景直接转 RGB 会变成黑底，截图里的黑字就看不见了
    if image.mode not in ("RGBA", "LA", "P"):
        return image.convert("RGB")
    image = image.convert("RGBA")
    background = Image.new("RGB", image.size, "white")
    background.paste(image, mask=image.getchannel("A"))
    return background


async def get_owned(db: AsyncSession, user: User, file_id: int) -> File:
    file = await db.get(File, file_id)
    if file is None or file.owner_id != user.id:
        raise AppError(404, "NOT_FOUND", "图片不存在或已过期，请重新上传")
    return file


def file_out(file: File) -> FileOut:
    # 过期时间取整点：同一小时内拿到的地址相同，浏览器可以缓存图片；有效期在 1～2 小时之间
    exp = (int(time.time()) // URL_TTL + 2) * URL_TTL
    url = f"/api/v1/files/{file.id}?exp={exp}&sig={_sign(file.id, exp)}"
    return FileOut(id=file.id, url=url, width=file.width, height=file.height)


async def get_signed(db: AsyncSession, file_id: int, exp: int, sig: str) -> File:
    if exp < time.time() or not hmac.compare_digest(sig, _sign(file_id, exp)):
        raise AppError(403, "FORBIDDEN", "图片链接已过期，请刷新页面")
    file = await db.get(File, file_id)
    if file is None:
        raise AppError(404, "NOT_FOUND", "图片不存在或已被删除")
    return file


def _sign(file_id: int, exp: int) -> str:
    message = f"{file_id}:{exp}".encode()
    return hmac.new(settings.file_secret.encode(), message, hashlib.sha256).hexdigest()

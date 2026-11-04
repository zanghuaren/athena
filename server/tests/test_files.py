import io
import time
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from app.services import files


def _image(fmt: str, size=(300, 100), mode="RGB", color="red", **save) -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, fmt, **save)
    return out.getvalue()


async def _upload(client, headers, data: bytes, name="a.jpg"):
    return await client.post("/api/v1/files", files={"file": (name, data)}, headers=headers)


async def _download(client, url: str) -> Image.Image:
    resp = await client.get(url)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    return Image.open(io.BytesIO(resp.content))


async def test_upload_converts_to_jpeg(client, student):
    for fmt in ("JPEG", "PNG", "WEBP", "HEIF"):
        resp = await _upload(client, student, _image(fmt))
        assert resp.status_code == 201, fmt
        body = resp.json()
        assert (body["width"], body["height"]) == (300, 100)
        image = await _download(client, body["url"])
        assert image.format == "JPEG"
        assert image.size == (300, 100)


async def test_upload_resizes_rotates_and_fills_transparency(client, student):
    big = await _upload(client, student, _image("JPEG", size=(4000, 3000)))
    assert (big.json()["width"], big.json()["height"]) == (2048, 1536)

    # EXIF 方向 6：相机横着存、要顺时针转 90° 才是正的
    exif = Image.Exif()
    exif[0x0112] = 6
    rotated = await _upload(client, student, _image("JPEG", exif=exif))
    assert (rotated.json()["width"], rotated.json()["height"]) == (100, 300)

    clear = await _upload(client, student, _image("PNG", mode="RGBA", color=(0, 0, 0, 0)))
    image = await _download(client, clear.json()["url"])
    assert min(image.getpixel((10, 10))) > 240


async def test_upload_rejects_bad_files(client, student):
    for data in (b"not an image", _image("GIF")):
        resp = await _upload(client, student, data)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "FILE_TYPE_UNSUPPORTED"

    resp = await _upload(client, student, b"\0" * (files.MAX_SIZE + 1))
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"

    assert (await _upload(client, {}, _image("JPEG"))).status_code == 401


async def test_download_needs_valid_signature(client, student):
    url = (await _upload(client, student, _image("JPEG"))).json()["url"]
    path = urlsplit(url).path
    query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    # 地址按整点过期，有效期 1～2 小时
    assert 3600 <= int(query["exp"]) - time.time() <= 7200

    tampered = {**query, "sig": "0" * 64}
    assert (await client.get(path, params=tampered)).status_code == 403
    # 改了过期时间，签名就对不上
    longer = {**query, "exp": int(query["exp"]) + 3600}
    assert (await client.get(path, params=longer)).status_code == 403
    assert (await client.get(path)).status_code == 400

    # 签名正确但已过期
    file_id = int(path.rsplit("/", 1)[1])
    past = int(time.time()) - 1
    expired = {"exp": past, "sig": files._sign(file_id, past)}
    assert (await client.get(path, params=expired)).status_code == 403

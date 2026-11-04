from pydantic import BaseModel


class FileOut(BaseModel):
    """返回里的文件统一用这个结构，url 带签名，见接口约定 2.3。"""

    id: int
    url: str
    width: int | None
    height: int | None

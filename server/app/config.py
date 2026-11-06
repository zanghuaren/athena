from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    expose_api_docs: bool = False
    # Android App 里的页面来源是 https://localhost，跨域访问 API；Web 端同源，不需要配置
    cors_origins: list[str] = ["https://localhost"]
    # 只接 DeepSeek（技术方案 5.1）；Key 只放在 .env 里
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    model_fast: str = "deepseek-flash"
    model_vision: str = "deepseek-flash"
    model_reasoning: str = "deepseek-v4-pro"
    # 上传的图片和导出文件放在本地目录（技术方案第 3 节）；文件链接用 file_secret 签名
    files_dir: Path = Path("/data/files")
    file_secret: str


settings = Settings()

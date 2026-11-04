from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Android App 里的页面来源是 https://localhost，跨域访问 API；Web 端同源，不需要配置
    cors_origins: list[str] = ["https://localhost"]


settings = Settings()

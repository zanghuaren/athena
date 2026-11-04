from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Android App 里的页面来源是 https://localhost，跨域访问 API；Web 端同源，不需要配置
    cors_origins: list[str] = ["https://localhost"]
    # 只接 DeepSeek（技术方案 5.1）；Key 只放在 .env 里
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    model_fast: str = "deepseek-flash"
    model_vision: str = "deepseek-flash"
    model_reasoning: str = "deepseek-v4-pro"


settings = Settings()

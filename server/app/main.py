import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings
from app.errors import register_error_handlers

# 应用日志（如模型调用记录）输出到标准输出；uvicorn 只配置了它自己的日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="雅典娜 API",
    version="0.1.0",
    docs_url="/api/docs" if settings.expose_api_docs else None,
    openapi_url="/api/openapi.json" if settings.expose_api_docs else None,
    redoc_url=None,
)
register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router)

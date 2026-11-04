from fastapi import FastAPI

from app.api import api_router
from app.errors import register_error_handlers

app = FastAPI(
    title="雅典娜 API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
register_error_handlers(app)
app.include_router(api_router)

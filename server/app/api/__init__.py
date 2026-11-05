from fastapi import APIRouter

from app.api import (
    auth,
    conversations,
    files,
    health,
    jobs,
    knowledge,
    me,
    questions,
    scans,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(knowledge.router)
api_router.include_router(questions.router)
api_router.include_router(conversations.router)
api_router.include_router(files.router)
api_router.include_router(scans.router)
api_router.include_router(jobs.router)
api_router.include_router(health.router)

from fastapi import APIRouter

from app.api import auth, health, knowledge, me, questions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(knowledge.router)
api_router.include_router(questions.router)
api_router.include_router(health.router)

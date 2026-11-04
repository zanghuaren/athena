from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.user import UserOut

router = APIRouter(prefix="/me", tags=["我的"])


@router.get("")
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

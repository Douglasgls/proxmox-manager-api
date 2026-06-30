from fastapi import APIRouter
from fastapi import Depends

from app.dto.request.create_user import (
    CreateUserDTO
)

from app.core.dependencies import (
    get_user_service
)
from app.services.user_service import UserService


router = APIRouter()


@router.post("/users")
def create(
    dto: CreateUserDTO,
    service: UserService = Depends(
        get_user_service
    )
):

    return service.create(
        username=dto.username,
        password_hash=dto.password,
        role=dto.role
    )
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

    # TODO: Implementar validação de email e senha e
    #  desestruturar o dto sem precisar passar cada campo individualmente.
    return service.create(
        username=dto.username,
        password=dto.password,
        email=dto.email,
        role=dto.role,
    )
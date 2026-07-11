from fastapi import APIRouter
from fastapi import Depends

from app.dto.request.create_user import (
    CreateUserDTO
)
from app.dto.response.user import AuthenticatedUserDTO

from app.core.dependencies import (
    get_auth_service,
)
from app.services.auth_service import AuthService


router = APIRouter()


@router.post("/users", response_model=AuthenticatedUserDTO)
def create(
    dto: CreateUserDTO,
    service: AuthService = Depends(
        get_auth_service
    )
):

    return service.create_user(
        username=dto.username,
        password=dto.password,
        email=dto.email,
        role=dto.role,
    )

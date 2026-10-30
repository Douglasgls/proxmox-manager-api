from fastapi import APIRouter, Depends, HTTPException
from app.core.exceptions import DomainValidationError
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
    try:
        return service.create_user(
            username=dto.username,
            password=dto.password,
            email=dto.email,
            role=dto.role,
        )
    except (DomainValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

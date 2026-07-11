from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_auth_service
from app.dto.request.login import LoginRequestDTO
from app.dto.request.refresh import RefreshRequestDTO
from app.dto.response.token import TokenResponseDTO
from app.dto.response.user import AuthenticatedUserDTO
from app.models.user import User
from app.security.dependencies import get_current_user
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth")


@router.post("/login", response_model=TokenResponseDTO)
def login(
    dto: LoginRequestDTO,
    service: AuthService = Depends(get_auth_service),
):
    return service.login(dto.email, dto.password)


@router.post("/refresh", response_model=TokenResponseDTO)
def refresh(
    dto: RefreshRequestDTO,
    service: AuthService = Depends(get_auth_service),
):
    return service.refresh(dto.refresh_token)


@router.get("/me", response_model=AuthenticatedUserDTO)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    service.logout(current_user)

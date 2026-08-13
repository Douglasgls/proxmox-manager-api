from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.dependencies import get_component_service
from app.security.dependencies import get_current_user
from app.services.component_service import ComponentService


class ComponentResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    category: str
    description: str | None = None
    version: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


router = APIRouter(
    prefix="/components",
    tags=["components"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[ComponentResponseDTO],
    status_code=status.HTTP_200_OK,
)
def list_components(
    category: str | None = None,
    service: ComponentService = Depends(get_component_service),
):
    """Lista todos os componentes ativos disponíveis no catálogo."""
    return service.list_components(category=category)


@router.get(
    "/{slug}",
    response_model=ComponentResponseDTO,
    status_code=status.HTTP_200_OK,
)
def get_component_by_slug(
    slug: str,
    service: ComponentService = Depends(get_component_service),
):
    """Obtém detalhes de um componente específico do catálogo pelo slug."""
    try:
        return service.get_component_by_slug(slug)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

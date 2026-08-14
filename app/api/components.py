from typing import Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.dependencies import get_component_service
from app.security.dependencies import get_current_user
from app.services.component_service import ComponentService
from app.components.registry import ComponentRegistry


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
    metadata: dict[str, Any] | None = None


def _to_component_dto(comp: Any) -> ComponentResponseDTO:
    meta_dict: dict[str, Any] | None = None
    try:
        impl = ComponentRegistry.get(comp.slug)
        meta_dict = impl.metadata()
    except Exception:
        meta_dict = None

    return ComponentResponseDTO(
        id=str(comp.id),
        name=str(comp.name),
        slug=str(comp.slug),
        category=str(comp.category),
        description=comp.description,
        version=str(comp.version),
        is_default=bool(comp.is_default),
        is_active=bool(comp.is_active),
        created_at=comp.created_at,
        updated_at=comp.updated_at,
        metadata=meta_dict,
    )


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
    """Lista todos os componentes ativos disponíveis no catálogo com seus metadados de template."""
    components = service.list_components(category=category)
    return [_to_component_dto(c) for c in components]


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
        component = service.get_component_by_slug(slug)
        return _to_component_dto(component)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

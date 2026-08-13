import logging
from app.components.base_components import BaseComponent
from app.components.registry import ComponentRegistry
from app.models.component import Component, ComponentCategory
from app.repositories.component_repository import ComponentRepository

logger = logging.getLogger(__name__)


DEFAULT_CATALOG_SEEDS = [
    {
        "slug": "curl",
        "name": "cURL",
        "category": ComponentCategory.NATIVE.value,
        "version": "7.x+",
        "description": "Utilitário de transferência de dados com sintaxe URL.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "git",
        "name": "Git",
        "category": ComponentCategory.NATIVE.value,
        "version": "2.x+",
        "description": "Sistema de Controle de Versões Distribuído Git.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "tailscale",
        "name": "Tailscale",
        "category": ComponentCategory.NATIVE.value,
        "version": "1.x+",
        "description": "Infraestrutura de conectividade e rede mesh VPN Tailscale.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "game",
        "name": "Game",
        "category": ComponentCategory.DOCKER_APPLICATION.value,
        "version": "latest",
        "description": "Aplicação Web Game executada isoladamente via container Docker.",
        "is_default": True,
        "is_active": True,
    },
]


class ComponentService:
    """Serviço responsável pelas regras de negócio e sincronização do catálogo de componentes."""

    def __init__(self, repository: ComponentRepository):
        self.repository = repository

    def sync_default_catalog(self) -> list[Component]:
        """Sincroniza de forma idempotente os componentes padrão no banco de dados local."""
        synced_components = []
        for seed in DEFAULT_CATALOG_SEEDS:
            existing = self.repository.get_by_slug(seed["slug"])
            if not existing:
                logger.info("Criando componente default no catálogo: %s", seed["slug"])
                component = Component(
                    slug=seed["slug"],
                    name=seed["name"],
                    category=seed["category"],
                    version=seed["version"],
                    description=seed["description"],
                    is_default=seed["is_default"],
                    is_active=seed["is_active"],
                )
                created = self.repository.create(component)
                synced_components.append(created)
            else:
                # Atualização idempotente de metadados se necessário
                existing.name = seed["name"]
                existing.category = seed["category"]
                existing.version = seed["version"]
                existing.description = seed["description"]
                updated = self.repository.update(existing)
                synced_components.append(updated)

        return synced_components

    def list_components(self, category: str | None = None) -> list[Component]:
        """Lista os componentes ativos do catálogo, com suporte a filtro por categoria."""
        return self.repository.list_active(category=category)

    def get_component_by_slug(self, slug: str) -> Component:
        """Obtém um componente pelo slug ou levanta exceção caso não exista."""
        component = self.repository.get_by_slug(slug)
        if not component:
            raise ValueError(f"Componente com slug '{slug}' não foi encontrado no catálogo.")
        return component

    def resolve_component_implementation(self, slug: str) -> BaseComponent:
        """Resolve o slug persistido para a classe implementadora correspondente."""
        return ComponentRegistry.get(slug)

    def validate_and_resolve_slugs(self, slugs: list[str] | None) -> list[Component]:
        """Valida e deduplica uma lista de slugs solicitados, retornando as entidades Component registradas."""
        if not slugs:
            return []

        # Deduplica mantendo a ordem original de solicitação
        unique_slugs = []
        for s in slugs:
            s_clean = s.strip().lower()
            if s_clean and s_clean not in unique_slugs:
                unique_slugs.append(s_clean)

        resolved_components = []
        invalid_slugs = []

        from app.core.exceptions import DomainValidationError

        for slug in unique_slugs:
            comp = self.repository.get_by_slug(slug)
            if not comp or not comp.is_active:
                invalid_slugs.append(slug)
                continue

            try:
                ComponentRegistry.get(slug)
            except Exception:
                invalid_slugs.append(slug)
                continue

            resolved_components.append(comp)

        if invalid_slugs:
            raise DomainValidationError(
                f"Componente(s) não disponível(is) para instalação: {', '.join(invalid_slugs)}"
            )

        return resolved_components


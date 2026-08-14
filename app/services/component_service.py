import logging
from typing import Any
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
        "slug": "filegator",
        "name": "FileGator",
        "category": ComponentCategory.DOCKER_APPS.value,
        "version": "latest",
        "description": "Gerenciador de arquivos web executado via container Docker.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "uptime-kuma",
        "name": "Uptime Kuma",
        "category": ComponentCategory.DOCKER_APPS.value,
        "version": "1.x",
        "description": "Ferramenta autohospedada de monitoramento de serviços e sites com belo painel de status.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "postgresql",
        "name": "PostgreSQL",
        "category": ComponentCategory.DOCKER_APPS.value,
        "version": "16-alpine",
        "description": "Sistema gerenciador de banco de dados relacional de alto desempenho e código aberto.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "redis",
        "name": "Redis",
        "category": ComponentCategory.DOCKER_APPS.value,
        "version": "7-alpine",
        "description": "Armazenamento de estrutura de dados em memória, utilizado como banco de dados, cache e mensagens.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "mariadb",
        "name": "MariaDB",
        "category": ComponentCategory.DOCKER_APPS.value,
        "version": "11.x",
        "description": "Banco de dados relacional rápido, escalável e de alto desempenho compatível com MySQL.",
        "is_default": True,
        "is_active": True,
    },
    {
        "slug": "jellyfin",
        "name": "Jellyfin",
        "category": ComponentCategory.DOCKER_APPS.value,
        "version": "latest",
        "description": "Servidor de mídia de código aberto para organizar e transmitir filmes, séries e músicas.",
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

    def resolve_component_implementation(self, slug: str, config: dict[str, Any] | None = None) -> BaseComponent:
        """Resolve o slug persistido para a classe implementadora correspondente."""
        return ComponentRegistry.get(slug, config=config)

    def validate_and_resolve_slugs(self, items: list[str | dict[str, Any] | Any] | None) -> list[Component]:
        """Valida, verifica conflitos de portas e resolve os componentes solicitados."""
        if not items:
            return []

        from app.core.exceptions import DomainValidationError

        parsed_items: list[tuple[str, dict[str, Any]]] = []
        seen_slugs: set[str] = set()

        for item in items:
            if isinstance(item, str):
                slug = item.strip().lower()
                cfg = {}
            elif isinstance(item, dict):
                slug = str(item.get("slug", "")).strip().lower()
                raw_cfg = item.get("config") or {}
                if isinstance(raw_cfg, dict):
                    cfg = {k: v for k, v in raw_cfg.items() if v is not None}
                else:
                    cfg = {}
            elif hasattr(item, "slug"):
                slug = str(item.slug).strip().lower()
                raw_cfg = getattr(item, "config", None)
                if hasattr(raw_cfg, "model_dump"):
                    cfg = raw_cfg.model_dump(exclude_none=True)
                elif isinstance(raw_cfg, dict):
                    cfg = {k: v for k, v in raw_cfg.items() if v is not None}
                else:
                    cfg = {}
            else:
                continue

            if not slug:
                continue

            parsed_items.append((slug, cfg))

        resolved_components = []
        invalid_slugs = []
        used_ports: set[tuple[str, int]] = set()

        for slug, cfg in parsed_items:
            comp = self.repository.get_by_slug(slug)
            if not comp or not comp.is_active:
                invalid_slugs.append(slug)
                continue

            try:
                impl = ComponentRegistry.get(slug, config=cfg)
            except Exception:
                invalid_slugs.append(slug)
                continue

            # Validação de conflito de portas entre componentes docker_apps no mesmo container
            if getattr(impl, "category", None) == ComponentCategory.DOCKER_APPS.value:
                effective_cfg = getattr(impl, "get_effective_config", lambda: {})()
                host = effective_cfg.get("host", "0.0.0.0")
                host_port = effective_cfg.get("host_port") or getattr(impl, "host_port", None)
                if host_port is not None:
                    port_key = (host, host_port)

                    if port_key in used_ports:
                        raise DomainValidationError(
                            f"Conflito de porta detectado: a porta host {host_port} no bind address {host} já está atribuída a outro componente."
                        )
                    used_ports.add(port_key)

            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Anexa a configuração da requisição ao objeto Component temporário
            comp._request_config = cfg
            resolved_components.append(comp)

        if invalid_slugs:
            raise DomainValidationError(
                f"Componente(s) não disponível(is) para instalação: {', '.join(invalid_slugs)}"
            )

        return resolved_components

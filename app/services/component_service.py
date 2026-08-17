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

    def validate_and_resolve_slugs(
        self,
        items: list[str | dict[str, Any] | Any] | None,
        existing_container_components: list[Any] | None = None,
    ) -> list[Component]:
        """Valida, verifica conflitos de portas/nomes e resolve os componentes solicitados."""
        if not items:
            return []

        from app.core.exceptions import DomainValidationError

        parsed_items: list[tuple[str, dict[str, Any]]] = []

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

        existing_native_slugs: set[str] = set()
        used_container_names: set[str] = set()
        used_ports: set[tuple[str, int]] = set()

        if existing_container_components:
            for record in existing_container_components:
                rec_status = str(getattr(record, "status", ""))
                if rec_status.upper() == "FAILED":
                    continue

                comp_obj = getattr(record, "component", None)
                if not comp_obj and getattr(record, "component_id", None):
                    comp_obj = self.repository.get(record.component_id)

                cat = getattr(comp_obj, "category", None) if comp_obj else None
                slug_val = getattr(comp_obj, "slug", "") if comp_obj else ""

                if cat == ComponentCategory.NATIVE.value and slug_val:
                    existing_native_slugs.add(slug_val.lower())

                rec_cfg = getattr(record, "config", None) or {}
                if isinstance(rec_cfg, dict) and slug_val:
                    try:
                        impl_existing = ComponentRegistry.get(slug_val, config=rec_cfg)
                        eff_existing = impl_existing.get_effective_config()
                        c_name_ex = eff_existing.get("container_name")
                        if c_name_ex:
                            used_container_names.add(str(c_name_ex).strip())
                        h_port_ex = eff_existing.get("host_port")
                        if h_port_ex is not None:
                            h_host_ex = str(eff_existing.get("host", "0.0.0.0"))
                            used_ports.add((h_host_ex, int(h_port_ex)))
                    except Exception:
                        c_name = rec_cfg.get("container_name")
                        if c_name:
                            used_container_names.add(str(c_name).strip())
                        h_port = rec_cfg.get("host_port")
                        if h_port is not None:
                            try:
                                h_port_int = int(h_port)
                                h_host = str(rec_cfg.get("host", "0.0.0.0"))
                                used_ports.add((h_host, h_port_int))
                            except (ValueError, TypeError):
                                pass

        seen_native_batch: set[str] = set()

        for slug, cfg in parsed_items:
            comp_db = self.repository.get_by_slug(slug)
            if not comp_db or not comp_db.is_active:
                invalid_slugs.append(slug)
                continue

            try:
                impl = ComponentRegistry.get(slug, config=cfg)
                impl.validate_config()
            except Exception as exc:
                if isinstance(exc, DomainValidationError):
                    raise
                raise DomainValidationError(
                    f"Configuração inválida para o componente '{comp_db.name}' ({slug}): {exc}"
                )

            category = getattr(impl, "category", comp_db.category)

            # 1. Validação de componentes NATIVOS
            if category == ComponentCategory.NATIVE.value:
                if slug in existing_native_slugs:
                    raise DomainValidationError(
                        f"O componente nativo '{comp_db.name}' ({slug}) já está instalado neste container."
                    )
                if slug in seen_native_batch:
                    continue
                seen_native_batch.add(slug)

            # 2. Validação de DOCKER APPS
            elif category == ComponentCategory.DOCKER_APPS.value:
                effective_cfg = getattr(impl, "get_effective_config", lambda: {})()
                c_name = effective_cfg.get("container_name")
                h_host = effective_cfg.get("host", "0.0.0.0")
                h_port = effective_cfg.get("host_port")

                # Conflito de nome do container Docker
                if c_name:
                    c_name_str = str(c_name).strip()
                    if c_name_str in used_container_names:
                        raise DomainValidationError(
                            f"Conflito de nome: o container Docker com o nome '{c_name_str}' já está em uso neste container LXC."
                        )
                    used_container_names.add(c_name_str)

                # Conflito de porta publicada no host
                if h_port is not None:
                    try:
                        port_int = int(h_port)
                        if not (1 <= port_int <= 65535):
                            raise DomainValidationError(
                                f"A porta publicada no host ({port_int}) deve estar entre 1 e 65535."
                            )
                        port_key = (h_host, port_int)
                        if port_key in used_ports:
                            raise DomainValidationError(
                                f"Conflito de porta: a porta host {port_int} no bind address {h_host} já está atribuída a outro componente no mesmo container LXC."
                            )
                        used_ports.add(port_key)
                    except DomainValidationError:
                        raise
                    except (ValueError, TypeError):
                        raise DomainValidationError(f"Porta host inválida: {h_port}")

            # Instancia o objeto Component com a configuração da requisição anexada
            comp_instance = Component(
                id=comp_db.id,
                name=comp_db.name,
                slug=comp_db.slug,
                category=comp_db.category,
                version=comp_db.version,
                description=comp_db.description,
                is_default=comp_db.is_default,
                is_active=comp_db.is_active,
            )
            comp_instance._request_config = cfg
            resolved_components.append(comp_instance)

        if invalid_slugs:
            raise DomainValidationError(
                f"Componente(s) não disponível(is) para instalação: {', '.join(invalid_slugs)}"
            )

        return resolved_components

from typing import Any
from app.components.base_components import BaseComponent
from app.components.curl_component import CurlComponent
from app.components.definition import ComponentDefinition
from app.components.git_component import GitComponent
from app.components.tailscale_component import TailscaleComponent
from app.components.filegator_component import FileGatorComponent
from app.components.uptime_kuma_component import UptimeKumaComponent
from app.components.postgresql_component import PostgresqlComponent
from app.components.redis_component import RedisComponent
from app.components.mariadb_component import MariadbComponent
from app.components.jellyfin_component import JellyfinComponent


class ComponentRegistry:
    """Mapeador entre o identificador técnico (slug) do componente e sua classe implementadora."""

    _components: dict[str, type[BaseComponent]] = {
        # Native components
        "curl": CurlComponent,
        "git": GitComponent,
        "tailscale": TailscaleComponent,
        # Docker Application components
        "filegator": FileGatorComponent,
        "uptime-kuma": UptimeKumaComponent,
        "postgresql": PostgresqlComponent,
        "redis": RedisComponent,
        "mariadb": MariadbComponent,
        "jellyfin": JellyfinComponent,
    }

    @classmethod
    def get(
        cls,
        definition: ComponentDefinition | str,
        config: dict[str, Any] | None = None,
    ) -> BaseComponent:
        if isinstance(definition, ComponentDefinition):
            name = definition.name
            merged_config = definition.config or config
        else:
            name = definition
            merged_config = config

        component_class = cls._components.get(name.lower())

        if component_class is None:
            raise ValueError(
                f"Component '{name}' not registered in ComponentRegistry."
            )

        return component_class(config=merged_config)

    @classmethod
    def list_registered_slugs(cls) -> list[str]:
        return list(cls._components.keys())

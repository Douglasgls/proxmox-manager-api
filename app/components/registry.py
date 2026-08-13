from typing import Any
from app.components.base_components import BaseComponent
from app.components.curl_component import CurlComponent
from app.components.definition import ComponentDefinition
from app.components.git_component import GitComponent
from app.components.tailscale_component import TailscaleComponent
from app.components.filegator_component import FileGatorComponent


class ComponentRegistry:
    """Mapeador entre o identificador técnico (slug) do componente e sua classe implementadora."""

    _components: dict[str, type[BaseComponent]] = {
        # Native components
        "curl": CurlComponent,
        "git": GitComponent,
        "tailscale": TailscaleComponent,
        # Docker Application components
        "filegator": FileGatorComponent,
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

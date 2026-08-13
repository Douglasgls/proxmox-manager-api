from app.components.base_components import BaseComponent
from app.components.curl_component import CurlComponent
from app.components.definition import ComponentDefinition
from app.components.dummy_component import DummyComponent
from app.components.EchoComponent import EchoComponent
from app.components.git_component import GitComponent
from app.components.tailscale_component import TailscaleComponent
from app.components.game_component import GameComponent
from app.components.programming.python import PythonComponent
from app.components.database.mysql import MySQLComponent


class ComponentRegistry:
    """Mapeador entre o identificador técnico (slug) do componente e sua classe implementadora."""

    _components: dict[str, type[BaseComponent]] = {
        # Native components
        "curl": CurlComponent,
        "git": GitComponent,
        "tailscale": TailscaleComponent,
        "python": PythonComponent,
        # Docker application components
        "game": GameComponent,
        # Legacy / Outros componentes
        "mysql": MySQLComponent,
        "dummy": DummyComponent,
        "echo": EchoComponent,
    }

    @classmethod
    def get(
        cls,
        definition: ComponentDefinition | str,
    ) -> BaseComponent:
        name = definition.name if isinstance(definition, ComponentDefinition) else definition
        config = definition.config if isinstance(definition, ComponentDefinition) else {}

        component_class = cls._components.get(name.lower())

        if component_class is None:
            raise ValueError(
                f"Component '{name}' not registered in ComponentRegistry."
            )

        return component_class(config=config)

    @classmethod
    def list_registered_slugs(cls) -> list[str]:
        return list(cls._components.keys())

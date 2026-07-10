from app.components.base_components import BaseComponent
from app.components.curl_component import CurlComponent
from app.components.definition import ComponentDefinition
from app.components.dummy_component import DummyComponent
from app.components.EchoComponent import EchoComponent
from app.components.git_component import GitComponent
from app.components.tailscale_component import TailscaleComponent


class ComponentRegistry:

    _components: dict[str, type[BaseComponent]] = {
        "dummy": DummyComponent,
        "echo": EchoComponent,
        "curl": CurlComponent,
        "git": GitComponent,
        "tailscale": TailscaleComponent,
    }

    @classmethod
    def get(
        cls,
        definition: ComponentDefinition,
    ) -> BaseComponent:

        component_class = cls._components.get(
            definition.name
        )

        if component_class is None:
            raise ValueError(
                f"Component '{definition.name}' not registered."
            )

        return component_class(
            config=definition.config
        )

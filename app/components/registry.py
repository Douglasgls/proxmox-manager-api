from app.components.base_components import BaseComponent
from app.components.definition import ComponentDefinition
from app.components.dummy_component import DummyComponent
from app.components.EchoComponent import EchoComponent


class ComponentRegistry:

    _components: dict[str, type[BaseComponent]] = {
        "dummy": DummyComponent,
        "echo": EchoComponent,
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
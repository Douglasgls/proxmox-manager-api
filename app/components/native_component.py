from abc import ABC
from app.components.base_components import BaseComponent
from app.models.component import ComponentCategory


class NativeComponent(BaseComponent, ABC):
    """Classe base para componentes instalados diretamente no container LXC (categoria native)."""

    @property
    def category(self) -> str:
        return ComponentCategory.NATIVE.value

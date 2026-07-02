
from collections.abc import Sequence

from app.components.base_components import BaseComponent


class ProvisionPlan:
    def __init__(
        self,
        name: str,
        description: str,
        components: Sequence[BaseComponent] | None = None,
        id: str | None = None,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.components = list(components)

    def __repr__(self):
        return f"ProvisionPlan(name={self.name}, description={self.description}, components={self.components})"

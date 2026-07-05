from dataclasses import dataclass, field

from typing import Any


@dataclass
class ComponentDefinition:
    name: str
    config: dict[str, Any] = field(default_factory=dict)


    
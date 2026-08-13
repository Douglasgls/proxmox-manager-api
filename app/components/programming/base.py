from abc import ABC
from app.components.base_components import BaseComponent


class ProgrammingLanguageComponent(BaseComponent, ABC):
    """Classe base intermediária para componentes de linguagem de programação."""

    @property
    def category(self) -> str:
        return "programming_language"

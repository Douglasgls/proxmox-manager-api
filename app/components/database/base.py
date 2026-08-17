from abc import ABC
from app.components.base_components import BaseComponent


class DatabaseComponent(BaseComponent, ABC):
    """Classe base intermediária para componentes de banco de dados."""

    @property
    def category(self) -> str:
        return "database"

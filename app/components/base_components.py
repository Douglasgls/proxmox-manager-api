from abc import ABC, abstractmethod
from typing import Any
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class BaseComponent(ABC):
    """Contrato base declarativo para componentes do sistema.
    
    Componentes produzem seu ProvisionPlan declarativo descrevendo comandos
    de instalação e validação. A execução física é conduzida exclusivamente pela ProvisionEngine.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    def get_plan(self) -> ProvisionPlan:
        """Constrói e retorna o ProvisionPlan declarativo para este componente."""

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Retorna dados descritivos do componente."""

    @property
    def name(self) -> str:
        return self.metadata()["name"]

    def get_installed_version(self, session: Any) -> str | None:
        """Tenta consultar a versão real instalada no container através da sessão.

        Retorna None se a inspeção dinâmica não for suportada ou falhar.
        """
        return None



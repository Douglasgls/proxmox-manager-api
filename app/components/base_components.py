from abc import ABC, abstractmethod
from typing import Any
from app.components.definition import ComponentDefinition
from app.integrations.proxmox.container_session import ContainerSession


class BaseComponent(ABC):
    """Contrato base para componentes executados pelo provisionamento."""

    def __init__(self, config: dict[str, Any] | None = None,):
        self.config = config or {}

    @abstractmethod
    def install(self, session: ContainerSession) -> str | None:
        """Executa a etapa de instalacao do componente."""

    @abstractmethod
    def validate(self,session: ContainerSession) -> str | None:
        """Valida se o componente foi provisionado corretamente."""

    @abstractmethod
    def rollback(self,session: ContainerSession) -> str | None:
        """Desfaz alteracoes feitas pelo componente quando suportado."""

    @abstractmethod
    def metadata(self,session: ContainerSession) -> dict[str, Any]:
        """Retorna dados descritivos do componente."""

    @property
    def name(self) -> str:
        return self.metadata()["name"]

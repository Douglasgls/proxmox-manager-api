import logging
from typing import Any

from app.components.base_components import BaseComponent
from app.integrations.proxmox.container_session import ContainerSession


logger = logging.getLogger(__name__)


class DummyComponent(BaseComponent):
    """Componente em memoria para validar o fluxo do provisionamento."""

    def install(self,session: ContainerSession,) -> str | None:
        message = "Instalando Dummy..."
        logger.info(message)

        return message

    def validate(self,session: ContainerSession,) -> str | None:
        message = "Validando Dummy..."
        success_message = "Finalizado."
        logger.info(message)
        logger.info(success_message)

        return success_message

    def rollback(self,session: ContainerSession,) -> str | None:
        message = "Rollback Dummy..."
        logger.info(message)

        return message

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "Dummy",
            "description": "Componente de teste do framework de provisionamento.",
            "version": "0.1.0",
        }

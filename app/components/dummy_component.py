import logging
from typing import Any

from app.components.base_components import BaseComponent


logger = logging.getLogger(__name__)


class DummyComponent(BaseComponent):
    """Componente em memoria para validar o fluxo do provisionamento."""

    def install(self) -> str | None:
        message = "Instalando Dummy..."
        logger.info(message)

        return message

    def validate(self) -> str | None:
        message = "Validando Dummy..."
        success_message = "Finalizado."
        logger.info(message)
        logger.info(success_message)

        return success_message

    def rollback(self) -> str | None:
        message = "Rollback Dummy..."
        logger.info(message)

        return message

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "Dummy",
            "description": "Componente de teste do framework de provisionamento.",
            "version": "0.1.0",
        }

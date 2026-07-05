from typing import Any

from app.components.base_components import BaseComponent
from app.integrations.proxmox.container_session import ContainerSession


class EchoComponent(BaseComponent):

    def install(
        self,
        session: ContainerSession,
    ) -> str:

        result = session.exec(
            "echo 'Provision funcionando!'"
        )

        if not result.success:
            raise RuntimeError(result.stderr)

        return result.stdout.strip()

    def validate(
        self,
        session: ContainerSession,
    ) -> str:

        result = session.exec(
            "echo 'Validado'"
        )

        if not result.success:
            raise RuntimeError(result.stderr)

        return "Componente validado"

    def rollback(
        self,
        session: ContainerSession,
    ) -> str:
        return "Nada para desfazer"

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "Echo",
            "description": "Componente de teste",
            "version": "1.0",
        }
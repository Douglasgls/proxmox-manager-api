import logging

from app.integrations.proxmox.models import CommandResult
from app.integrations.proxmox.proxmox_client import ProxmoxClient


logger = logging.getLogger(__name__)


class ContainerSession:
    """Sessao administrativa para executar comandos em um container LXC."""

    def __init__(
        self,
        proxmox_client: ProxmoxClient,
        container_id: int,
    ):
        self.proxmox_client = proxmox_client
        self.container_id = container_id

    def exec(
        self,
        command: str,
        timeout: int = 90,
    ) -> CommandResult:
        logger.info(
            "Executando comando no container %s: %s",
            self.container_id,
            command,
        )

        return self.proxmox_client.exec(
            container_id=self.container_id,
            command=command,
            timeout=timeout
        )

    def exec_many(
        self,
        commands: list[str],
    ) -> list[CommandResult]:
        results: list[CommandResult] = []

        for command in commands:
            result = self.exec(
                command
            )
            results.append(
                result
            )

            if not result.success:
                logger.warning(
                    "Execucao interrompida no container %s apos falha: %s",
                    self.container_id,
                    command,
                )
                break

        return results

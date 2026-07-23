import asyncio
import logging
from sqlalchemy.orm import Session

from app.cloud.dto import ContainerProvisionPayloadDTO
from app.core.event_bus import internal_event_bus, ContainerProvisionCompleted
from app.repositories.container_repository import ContainerRepository
from app.tailscale.domain import TailscaleProvisionParams
from app.tailscale.provision_service import TailscaleProvisionService

logger = logging.getLogger(__name__)


class ContainerNotFoundError(RuntimeError):
    """Lançado quando o container solicitado não é encontrado no banco local."""

    pass


class ContainerNotPublishedError(RuntimeError):
    """Lançado quando o container não possui registro de publicação TailscaleNode."""

    pass


class ContainerNotRunningError(RuntimeError):
    """Lançado quando o container não está em execução (status != 'running')."""

    pass


class ContainerProvisionService:
    """Orquestrador do fluxo de provisionamento disparado pela Cloud.

    Responsável por validar a elegibilidade local do container,
    instanciar os parâmetros de domínio, delegar o provisionamento
    ao `TailscaleProvisionService` e emitir o evento `ContainerProvisionCompleted`.
    """

    def __init__(
        self,
        db: Session,
        tailscale_provision_service: TailscaleProvisionService | None = None,
    ) -> None:
        self.db = db
        self.container_repo = ContainerRepository(db)
        self.tailscale_provision_service = (
            tailscale_provision_service or TailscaleProvisionService(db)
        )

    async def provision_container(
        self,
        payload: ContainerProvisionPayloadDTO,
    ) -> None:
        """Orquestra o provisionamento do container.

        Executa as validações de elegibilidade e delega a execução para o serviço
        de Tailscale (em thread pool para não bloquear o loop do asyncio).
        """
        request_id = payload.request_id
        container_id = payload.container_id

        logger.info(
            "[%s] Container localizado. Verificando elegibilidade para provisionamento (container_id=%s)",
            request_id,
            container_id,
        )

        # 1. Buscar o container no banco de dados local
        container = self.container_repo.get(container_id)
        if not container:
            logger.error("[%s] Container %s não foi encontrado no banco de dados local.", request_id, container_id)
            raise ContainerNotFoundError(f"Container '{container_id}' não foi encontrado.")

        logger.info("[%s] Container %s encontrado no banco local.", request_id, container_id)

        # 2. Verificar se o container possui registro de TailscaleNode prévio
        if not hasattr(container, "tailscale_node") or container.tailscale_node is None:
            logger.error(
                "[%s] Container %s não possui registro prévio de TailscaleNode (não está publicado).",
                request_id,
                container_id,
            )
            raise ContainerNotPublishedError(
                f"Container '{container_id}' não possui um registro de TailscaleNode (não está publicado)."
            )

        # 3. Verificar se o container está em execução
        if container.status != "running":
            logger.error(
                "[%s] Container %s não está em execução (status=%s).",
                request_id,
                container_id,
                container.status,
            )
            raise ContainerNotRunningError(
                f"Container '{container_id}' não está em execução (status atual: {container.status})."
            )

        logger.info("[%s] Container %s elegível para provisionamento.", request_id, container_id)

        # 4. Instanciar parâmetros de domínio
        hostname = payload.hostname or container.name or f"ct-{container.container_number}"
        print(f"\n[PROVISION SERVICE] Container {container_id} elegível! Chamando TailscaleProvisionService.provision (hostname={hostname})...\n")

        params = TailscaleProvisionParams(
            login_server=payload.login_server,
            auth_key=payload.auth_key,
            hostname=hostname,
        )


        # 5. Executar o provisionamento via TailscaleProvisionService (em thread separada)
        logger.info("[%s] Executando serviço de provisionamento Tailscale...", request_id)
        await asyncio.to_thread(
            self.tailscale_provision_service.provision,
            container_id=container.id,
            proxmox_container_id=container.container_number,
            params=params,
            request_id=request_id,
        )

        # 6. Disparar evento interno ContainerProvisionCompleted
        logger.info(
            "[%s] Provisionamento concluído com sucesso. Disparando evento ContainerProvisionCompleted...",
            request_id,
        )
        print(f"\n[PROVISION SERVICE] Provisionamento finalizado com sucesso! Emitindo evento ContainerProvisionCompleted...\n")

        event = ContainerProvisionCompleted(
            container_id=container.id,
            request_id=request_id,
        )
        internal_event_bus.publish(event)
        logger.info("[%s] Evento ContainerProvisionCompleted publicado.", request_id)

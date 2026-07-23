from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.integrations.proxmox.container_session import ContainerSession
from app.integrations.proxmox.proxmox_client import ProxmoxClient
from app.tailscale.domain import TailscaleProvisionParams
from app.tailscale.model import TailscaleNode
from app.tailscale.repository import TailscaleRepository
from app.tailscale.service import TailscaleService, mask_auth_key

logger = logging.getLogger(__name__)


class TailscaleNotInstalledError(RuntimeError):
    """Lançado quando o Tailscale não está instalado no container."""

    pass


class TailscaleServiceNotRunningError(RuntimeError):
    """Lançado quando o serviço tailscaled não está ativo no container."""

    pass


class TailscaleNodeNotFoundError(RuntimeError):
    """Lançado quando o container não possui um registro de TailscaleNode prévio."""

    pass


class TailscaleProvisionService:
    """Serviço exclusivo responsável pelo provisionamento do Tailscale.

    Concentra todas as validações do daemon, execução do `tailscale up`,
    coleta do estado atualizado e persistência no banco local.
    """

    def __init__(
        self,
        db: Session,
        proxmox_client: ProxmoxClient | None = None,
    ) -> None:
        self.db = db
        self.repository = TailscaleRepository(db)
        self.proxmox_client = proxmox_client or ProxmoxClient()

    def provision(
        self,
        container_id: str,
        proxmox_container_id: int,
        params: TailscaleProvisionParams,
        request_id: str,
    ) -> TailscaleNode:
        """Executa o fluxo de provisionamento do Tailscale dentro do container LXC.

        1. Verifica existência prévia do registro TailscaleNode.
        2. Instancia a sessão no container e o TailscaleService.
        3. Valida se o Tailscale está instalado.
        4. Valida se o daemon tailscaled está em execução.
        5. Executa `tailscale up` utilizando o parâmetro de domínio.
        6. Coleta todas as informações atualizadas do daemon.
        7. Persiste a atualização no banco de dados local.
        """
        masked_key = mask_auth_key(params.auth_key)
        logger.info(
            "[%s] Iniciando provisionamento Tailscale no container %s (proxmox_id=%s, login_server=%s, hostname=%s, auth_key=%s)",
            request_id,
            container_id,
            proxmox_container_id,
            params.login_server,
            params.hostname,
            masked_key,
        )

        # 1. Verificar se o registro TailscaleNode já existe no banco local
        node = self.repository.get_by_container_id(container_id)
        if not node:
            logger.error(
                "[%s] Container %s não possui registro prévio em tailscale_nodes.",
                request_id,
                container_id,
            )
            raise TailscaleNodeNotFoundError(
                f"Container '{container_id}' não possui um registro TailscaleNode prévio. "
                "Sincronização prévia é necessária."
            )

        print(f"\n[TAILSCALE PROVISION] Registro TailscaleNode localizado para container {container_id}.")

        # 2. Instanciar sessão no container e serviço do Tailscale
        session = ContainerSession(self.proxmox_client, proxmox_container_id)
        service = TailscaleService(session)

        # 3. Validar se o Tailscale está instalado
        logger.info("[%s] Verificando se Tailscale está instalado no container %s...", request_id, container_id)
        if not service.is_installed():
            logger.error("[%s] Tailscale não está instalado no container %s.", request_id, container_id)
            raise TailscaleNotInstalledError(
                f"Tailscale não está instalado no container '{container_id}'."
            )

        print(f"[TAILSCALE PROVISION] Tailscale está instalado no container {container_id}.")

        # 4. Validar se o daemon tailscaled está em execução
        logger.info("[%s] Verificando se serviço tailscaled está ativo no container %s...", request_id, container_id)
        if not service.is_service_running():
            logger.error("[%s] Serviço tailscaled inativo no container %s.", request_id, container_id)
            raise TailscaleServiceNotRunningError(
                f"O serviço 'tailscaled' não está ativo no container '{container_id}'."
            )

        print(f"[TAILSCALE PROVISION] Serviço tailscaled está ativo no container {container_id}.")

        # 5. Executar tailscale up
        logger.info("[%s] Executando tailscale up no container %s...", request_id, container_id)
        print(f"[TAILSCALE PROVISION] Chamando exec_tailscale_up...")
        service.exec_tailscale_up(params)
        logger.info("[%s] Provisionamento tailscale up concluído com sucesso.", request_id)
        print(f"[TAILSCALE PROVISION] exec_tailscale_up concluído!")


        # 6. Coletar o estado atualizado do daemon
        logger.info("[%s] Coletando novo estado do Tailscale...", request_id)
        version = service.get_version()
        machine_id = service.get_machine_id()
        node_key = service.get_node_key()
        tailscale_ip = service.get_ip()
        status_json = service.get_status_json()

        # 7. Persistir informações atualizadas no banco de dados
        logger.info("[%s] Atualizando registro TailscaleNode no banco local...", request_id)
        node.installed = True
        node.service_running = True
        node.version = version
        node.machine_id = machine_id
        node.node_key = node_key
        node.tailscale_ip = tailscale_ip
        node.status_json = status_json
        node.last_sync = datetime.utcnow()

        updated_node = self.repository.update(node)
        logger.info("[%s] Registro TailscaleNode atualizado com sucesso no banco.", request_id)
        return updated_node

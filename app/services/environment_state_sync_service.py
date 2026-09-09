import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.cloud.dto import NodeSyncEventDataDTO
from app.cloud.models import AgentSettings
from app.cloud.repository import AgentSettingsRepository
from app.models.container import Container
from app.repositories.container_repository import ContainerRepository
from app.models.client_connection import ClientConnection
from app.models.container import Container
from app.repositories.container_repository import ContainerRepository
from app.tailscale.model import TailscaleNode

logger = logging.getLogger(__name__)


class EnvironmentStateSyncService:
    """Serviço responsável pela reconciliação e sincronização de estado remoto vindo da Cloud.

    Aplica as alterações de nós Headscale/Tailscale e conexões de clientes de forma atômica,
    parcial e idempotente no banco de dados local do Agent.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.agent_settings_repo = AgentSettingsRepository(db)
        self.container_repo = ContainerRepository(db)

    def validate_context(self, received_env_id: str | None) -> bool:
        """Valida se o environment_id recebido no evento confere com o Agent local."""
        settings = self.agent_settings_repo.get()
        if not settings:
            logger.warning("AgentSettings not configured yet. Rejecting event context.")
            return False

        configured_env_id = settings.cloud_environment_id

        if configured_env_id and received_env_id:
            if configured_env_id != received_env_id:
                logger.warning(
                    "Environment ID mismatch! Configured: '%s', Received: '%s'. Event rejected.",
                    configured_env_id,
                    received_env_id,
                )
                return False

        return True

    def upsert_node_state(self, dto: NodeSyncEventDataDTO) -> TailscaleNode | ClientConnection | None:
        """Atualiza (PATCH) ou cria o registro local de TailscaleNode (container) ou ClientConnection (cliente VPN)."""
        # 1. Checar se já existe um TailscaleNode (container publicado) registrado
        node = self._find_tailscale_node(dto)
        if node:
            logger.info("Existing TailscaleNode found (id=%s). Applying delta update...", node.id)
            self._patch_node(node, dto)
            self.db.commit()
            self.db.refresh(node)
            return node

        # 2. Checar se o nó pertence a um Container local existente
        container = self._find_container(dto)
        if container or dto.proxmox_container_id or dto.container_id:
            if container:
                logger.info("Creating new Container TailscaleNode linked to Container %s (vmid=%s)", container.id, container.container_number)
                online_status = dto.online if dto.online is not None else True
                status_json = {
                    "Self": {
                        "Online": online_status,
                        "HostName": dto.hostname or container.name,
                        "LastSeen": dto.last_seen,
                    }
                }
                hs_id = str(dto.headscale_node_id or dto.node_id or "")
                new_node = TailscaleNode(
                    container_id=container.id,
                    proxmox_container_id=container.container_number,
                    node_type="container",
                    headscale_node_id=hs_id or None,
                    machine_id=dto.machine_id or dto.node_id,
                    tailscale_ip=dto.tailscale_ip,
                    installed=True,
                    service_running=online_status,
                    status_json=status_json,
                    last_sync=datetime.now(timezone.utc),
                )
                self.db.add(new_node)
                self.db.commit()
                self.db.refresh(new_node)
                return new_node

        # 3. Caso seja um nó de cliente VPN (dispositivo/usuário externo)
        client_conn = self._find_client_connection(dto)
        hs_id = str(dto.headscale_node_id or dto.node_id or "")
        is_online = dto.online if dto.online is not None else (dto.connected if dto.connected is not None else True)
        hostname_val = dto.hostname or "client-device"

        if client_conn:
            logger.info("Existing ClientConnection found (id=%s). Applying delta update...", client_conn.id)
            if hs_id:
                client_conn.headscale_node_id = hs_id
            if dto.node_id:
                client_conn.cloud_connection_id = dto.node_id
            if dto.hostname:
                client_conn.hostname = dto.hostname
            if dto.tailscale_ip:
                client_conn.tailscale_ip = dto.tailscale_ip

            if is_online is not None:
                client_conn.online = is_online
                client_conn.status = "ACTIVE" if is_online else "DISCONNECTED"

            if dto.last_seen:
                try:
                    client_conn.last_seen = datetime.fromisoformat(dto.last_seen.replace("Z", "+00:00"))
                except Exception:
                    pass
            client_conn.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(client_conn)
            return client_conn

        logger.info("Creating new ClientConnection for external VPN device (hostname=%s, ip=%s)", hostname_val, dto.tailscale_ip)
        last_seen_dt = None
        if dto.last_seen:
            try:
                last_seen_dt = datetime.fromisoformat(dto.last_seen.replace("Z", "+00:00"))
            except Exception:
                pass

        new_conn = ClientConnection(
            cloud_connection_id=dto.node_id,
            headscale_node_id=hs_id or None,
            container_id=container.id if container else None,
            hostname=hostname_val,
            tailscale_ip=dto.tailscale_ip,
            online=online_status,
            status="ACTIVE" if online_status else "DISCONNECTED",
            last_seen=last_seen_dt,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(new_conn)
        self.db.commit()
        self.db.refresh(new_conn)
        return new_conn


    def remove_node_state(self, dto: NodeSyncEventDataDTO) -> bool:
        """Remove o registro em client_connections ou tailscale_nodes quando o nó for desconnectado/removido."""
        client_conn = self._find_client_connection(dto)
        if client_conn:
            logger.info("Removing ClientConnection record (id=%s, headscale_node_id=%s)", client_conn.id, client_conn.headscale_node_id)
            self.db.delete(client_conn)
            self.db.commit()
            return True

        node = self._find_tailscale_node(dto)
        if node:
            logger.info("Removing TailscaleNode record (id=%s, headscale_node_id=%s)", node.id, node.headscale_node_id)
            self.db.delete(node)
            self.db.commit()
            return True

        logger.warning("Node for removal not found (node_id=%s, headscale_node_id=%s)", dto.node_id, dto.headscale_node_id)
        return False


    def _find_tailscale_node(self, dto: NodeSyncEventDataDTO) -> TailscaleNode | None:
        """Busca nó Tailscale por headscale_node_id -> node_id -> machine_id -> tailscale_ip -> container_id."""
        query = self.db.query(TailscaleNode)

        target_hs_id = str(dto.headscale_node_id or dto.node_id or "")
        if target_hs_id:
            found = query.filter(TailscaleNode.headscale_node_id == target_hs_id).first()
            if found:
                return found

        if dto.machine_id:
            found = query.filter(TailscaleNode.machine_id == dto.machine_id).first()
            if found:
                return found

        if dto.node_id:
            found = query.filter(TailscaleNode.machine_id == dto.node_id).first()
            if found:
                return found

        if dto.tailscale_ip:
            found = query.filter(TailscaleNode.tailscale_ip == dto.tailscale_ip).first()
            if found:
                return found

        if dto.container_id:
            found = query.filter(TailscaleNode.container_id == dto.container_id).first()
            if found:
                return found

        if dto.proxmox_container_id:
            found = query.filter(TailscaleNode.proxmox_container_id == dto.proxmox_container_id).first()
            if found:
                return found

        return None

    def _find_client_connection(self, dto: NodeSyncEventDataDTO) -> ClientConnection | None:
        """Busca conexão de cliente VPN por headscale_node_id -> cloud_connection_id -> tailscale_ip -> hostname."""
        query = self.db.query(ClientConnection)

        target_hs_id = str(dto.headscale_node_id or dto.node_id or "")
        if target_hs_id:
            found = query.filter(ClientConnection.headscale_node_id == target_hs_id).first()
            if found:
                return found

        if dto.node_id:
            found = query.filter(ClientConnection.cloud_connection_id == dto.node_id).first()
            if found:
                return found

        if dto.tailscale_ip:
            found = query.filter(ClientConnection.tailscale_ip == dto.tailscale_ip).first()
            if found:
                return found

        if dto.hostname:
            found = query.filter(ClientConnection.hostname == dto.hostname).first()
            if found:
                return found

        return None

    # Alias para compatibilidade com suítes de testes pré-existentes
    _find_node = _find_tailscale_node




    def _find_container(self, dto: NodeSyncEventDataDTO) -> Container | None:
        """Busca container por container_id -> cloud_container_id -> proxmox_container_id."""
        query = self.db.query(Container)

        if dto.container_id:
            c = query.filter(Container.id == dto.container_id).first()
            if c:
                return c

        if dto.cloud_container_id:
            c = query.filter(Container.cloud_container_id == dto.cloud_container_id).first()
            if c:
                return c

        if dto.proxmox_container_id:
            c = query.filter(Container.container_number == dto.proxmox_container_id).first()
            if c:
                return c

        return None

    def reconcile_full_snapshot(self, dto_list: list[NodeSyncEventDataDTO]) -> dict[str, int]:
        """Reconcilia a lista completa de nós recebidos no snapshot da Cloud.

        1. Aplica upsert/patch em cada nó recebido.
        2. Realiza o expurgo (pruning) dos registros locais que não existem mais no snapshot da Cloud.
        """
        print(f"\n--- [RECONCILIAÇÃO BD LOCAL] Iniciando atualização para {len(dto_list)} nós da Cloud ---")
        logger.info("Starting full snapshot reconciliation for %d nodes...", len(dto_list))
        valid_hs_ids: set[str] = set()

        for dto in dto_list:
            hs_id = str(dto.headscale_node_id or dto.node_id or "")
            if hs_id:
                valid_hs_ids.add(hs_id)
            if dto.machine_id:
                valid_hs_ids.add(str(dto.machine_id))
            if dto.cloud_container_id:
                valid_hs_ids.add(str(dto.cloud_container_id))
            if dto.tailscale_ip:
                valid_hs_ids.add(str(dto.tailscale_ip))
            if dto.hostname:
                valid_hs_ids.add(str(dto.hostname))

            self.upsert_node_state(dto)

        # Expurgo (Pruning) de ClientConnections inexistentes no snapshot
        pruned_count = 0
        all_clients = self.db.query(ClientConnection).all()
        for client in all_clients:
            c_hs_id = str(client.headscale_node_id or client.cloud_connection_id or "")
            c_ip = str(client.tailscale_ip or "")
            c_host = str(client.hostname or "")

            is_valid = (
                (c_hs_id and c_hs_id in valid_hs_ids) or
                (c_ip and c_ip in valid_hs_ids) or
                (c_host and c_host in valid_hs_ids)
            )

            if not is_valid:
                print(f"  ❌ Expurgo (Deletando do BD local): ClientConnection (hostname={client.hostname}, IP={client.tailscale_ip}, hs_id={client.headscale_node_id})")
                logger.info("Pruning obsolete ClientConnection (id=%s, headscale_node_id=%s)", client.id, client.headscale_node_id)
                self.db.delete(client)
                pruned_count += 1

        # Expurgo/Desativação de TailscaleNodes inexistentes no snapshot
        all_tailscale_nodes = self.db.query(TailscaleNode).all()
        for node in all_tailscale_nodes:
            n_hs_id = str(node.headscale_node_id or node.machine_id or "")
            n_ip = str(node.tailscale_ip or "")
            n_host = str(node.hostname or "")

            is_valid = (
                (n_hs_id and n_hs_id in valid_hs_ids) or
                (n_ip and n_ip in valid_hs_ids) or
                (n_host and n_host in valid_hs_ids)
            )

            if not is_valid:
                if not node.container_id:
                    print(f"  ❌ Expurgo (Deletando do BD local): TailscaleNode não vinculado (hs_id={node.headscale_node_id}, IP={node.tailscale_ip})")
                    logger.info("Pruning unlinked obsolete TailscaleNode (id=%s, headscale_node_id=%s)", node.id, node.headscale_node_id)
                    self.db.delete(node)
                    pruned_count += 1
                else:
                    # Se está vinculado a um container local, marcar como offline/desconectado
                    print(f"  ⚠️ Marcando Container TailscaleNode como offline (container_id={node.container_id})")
                    logger.info("Marking container TailscaleNode offline as it was not in Cloud snapshot (id=%s)", node.id)
                    node.service_running = False
                    status_dict = dict(node.status_json) if (node.status_json and isinstance(node.status_json, dict)) else {"Self": {}}
                    self_info = dict(status_dict.get("Self", {}))
                    self_info["Online"] = False
                    status_dict["Self"] = self_info
                    node.status_json = status_dict

        self.db.commit()
        print(f"--- [RECONCILIAÇÃO CONCLUÍDA] Reconciliados: {len(dto_list)} | Deletados do BD: {pruned_count} ---\n")
        logger.info("Full snapshot reconciliation finished. Processed=%d, Pruned=%d", len(dto_list), pruned_count)
        return {"processed": len(dto_list), "pruned": pruned_count}

    @staticmethod
    def _patch_node(node: TailscaleNode, dto: NodeSyncEventDataDTO) -> None:
        """Atualiza atomicamente apenas os campos fornecidos no DTO."""
        if dto.node_id is not None:
            node.headscale_node_id = dto.node_id

        if dto.machine_id is not None:
            node.machine_id = dto.machine_id

        if dto.node_key is not None:
            node.node_key = dto.node_key

        if dto.tailscale_ip is not None:
            node.tailscale_ip = dto.tailscale_ip

        # Manter/Atualizar a estrutura status_json
        status_dict = dict(node.status_json) if (node.status_json and isinstance(node.status_json, dict)) else {"Self": {}}
        self_info = dict(status_dict.get("Self", {}))

        is_online = dto.online if dto.online is not None else dto.connected
        if is_online is not None:
            self_info["Online"] = is_online
            node.service_running = is_online

        if dto.hostname is not None:
            self_info["HostName"] = dto.hostname

        if dto.name is not None:
            self_info["Name"] = dto.name

        if dto.machine_key is not None:
            self_info["MachineKey"] = dto.machine_key

        if dto.node_key is not None:
            self_info["NodeKey"] = dto.node_key

        if dto.headscale_user is not None:
            self_info["User"] = dto.headscale_user

        if dto.tags is not None:
            self_info["Tags"] = dto.tags

        if dto.ephemeral is not None:
            self_info["Ephemeral"] = dto.ephemeral

        if dto.expiration is not None:
            self_info["Expiration"] = dto.expiration

        if dto.expired is not None:
            self_info["Expired"] = dto.expired

        if dto.last_seen is not None:
            self_info["LastSeen"] = dto.last_seen

        status_dict["Self"] = self_info
        node.status_json = status_dict
        node.last_sync = datetime.now(timezone.utc)

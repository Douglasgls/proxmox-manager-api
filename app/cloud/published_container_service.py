import logging
from sqlalchemy.orm import Session

from app.cloud.dto import (
    PublishedContainerSnapshotDTO,
    PublishedTailscaleNodeSnapshotDTO,
    PublishedAccessTokenSnapshotDTO,
    PublishedPortDTO,
)
from app.core.hostname import normalize_hostname
from app.models.container import Container
from app.repositories.container_repository import ContainerRepository

logger = logging.getLogger(__name__)

# Mapeamento de portas conhecidas por slug do componente
KNOWN_COMPONENT_PORTS: dict[str, int] = {
    "postgres": 5432,
    "postgresql": 5432,
    "redis": 6379,
    "mysql": 3306,
    "mariadb": 3306,
    "mongodb": 27017,
    "mongo": 27017,
    "nginx": 80,
    "caddy": 80,
    "apache": 80,
    "web": 80,
}


class PublishedContainerService:
    """Serviço responsável por identificar e expor os containers publicados deste ambiente."""

    def __init__(self, db: Session) -> None:
        self._container_repo = ContainerRepository(db)

    def _extract_container_ports(self, container: Container) -> list[PublishedPortDTO]:
        """Extrai as portas TCP expostas/disponíveis no container a partir dos seus componentes."""
        extracted_ports: set[int] = set()

        if hasattr(container, "container_components") and container.container_components:
            for cc in container.container_components:
                # 1. Tentar ler porta explícita da configuração do componente
                if cc.config and isinstance(cc.config, dict):
                    port_val = cc.config.get("container_port") or cc.config.get("host_port")
                    if port_val and isinstance(port_val, int) and 1 <= port_val <= 65535:
                        extracted_ports.add(port_val)

                # 2. Tentar mapear porta padrão pelo slug do componente
                if hasattr(cc, "component") and cc.component and cc.component.slug:
                    slug = cc.component.slug.lower()
                    if slug in KNOWN_COMPONENT_PORTS:
                        extracted_ports.add(KNOWN_COMPONENT_PORTS[slug])

        # Se nenhuma porta foi identificada pelos componentes, assume porta 80 por padrão
        if not extracted_ports:
            extracted_ports.add(80)

        return [
            PublishedPortDTO(port=p, protocol="tcp")
            for p in sorted(extracted_ports)
        ]

    def get_published_containers(self) -> list[PublishedContainerSnapshotDTO]:
        """Recupera e mapeia os containers publicados com informações do Tailscale e access tokens."""
        containers = self._container_repo.get_published_containers()

        snapshots = []
        for container in containers:
            # Identificar node do Tailscale associado
            ts_node = None
            if hasattr(container, "tailscale_node") and container.tailscale_node:
                if isinstance(container.tailscale_node, list):
                    ts_node = container.tailscale_node[0] if container.tailscale_node else None
                else:
                    ts_node = container.tailscale_node

            # Extrair hostname normalizado e dns_name
            raw_host = (ts_node.hostname if ts_node else None) or container.name
            hostname = normalize_hostname(raw_host)
            dns_name = f"{hostname}.interno"

            # Extrair portas publicadas
            ports = self._extract_container_ports(container)

            ts_snapshot = None
            if ts_node:
                ts_snapshot = PublishedTailscaleNodeSnapshotDTO(
                    installed=ts_node.installed,
                    service_running=ts_node.service_running,
                    version=ts_node.version,
                    machine_id=ts_node.machine_id,
                    node_key=ts_node.node_key,
                    tailscale_ip=ts_node.tailscale_ip,
                    online=ts_node.online,
                    last_sync=ts_node.last_sync,
                    hostname=hostname,
                    dns_name=dns_name,
                    last_seen=ts_node.last_seen,
                    advertised_routes=ts_node.advertised_routes or [],
                    ports=ports,
                )

            # Mapear tokens de acesso associados
            tokens = []
            if hasattr(container, "access_tokens") and container.access_tokens:
                for token in container.access_tokens:
                    tokens.append(
                        PublishedAccessTokenSnapshotDTO(
                            id=token.id,
                            token_hash=token.token_hash,
                            created_at=token.created_at,
                            expires_at=token.expires_at,
                            active=token.active,
                            revoked_at=token.revoked_at,
                        )
                    )

            # Validação de consistência do snapshot
            if not hostname or not dns_name or not dns_name.endswith(".interno"):
                logger.warning("Snapshot do container %s ignorado por inconsistência no hostname/dns_name.", container.id)
                continue

            snapshot = PublishedContainerSnapshotDTO(
                api_local_container_id=container.id,
                container_number=container.container_number,
                name=container.name,
                hostname=hostname,
                dns_name=dns_name,
                status=container.status,
                tailscale=ts_snapshot,
                access_tokens=tokens,
                ports=ports,
            )

            snapshots.append(snapshot)

        logger.debug("Containers publicados mapeados: %d", len(snapshots))
        return snapshots

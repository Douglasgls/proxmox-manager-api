import logging
from sqlalchemy.orm import Session

from app.cloud.dto import (
    PublishedContainerSnapshotDTO,
    PublishedTailscaleNodeSnapshotDTO,
    PublishedAccessTokenSnapshotDTO,
)
from app.repositories.container_repository import ContainerRepository

logger = logging.getLogger(__name__)


class PublishedContainerService:
    """Serviço responsável por identificar e expor os containers publicados deste ambiente."""

    def __init__(self, db: Session) -> None:
        self._container_repo = ContainerRepository(db)

    def get_published_containers(self) -> list[PublishedContainerSnapshotDTO]:
        """Recupera e mapeia os containers publicados com informações do Tailscale e access tokens."""
        containers = self._container_repo.get_published_containers()

        snapshots = []
        for container in containers:
            # Identificar node do Tailscale associado
            ts_snapshot = None
            
            # Como a relação tailscale_node é 1:1 física mas declarada sem uselist=False,
            # tratamos caso venha como lista ou objeto único.
            ts_node = None
            if hasattr(container, "tailscale_node") and container.tailscale_node:
                if isinstance(container.tailscale_node, list):
                    ts_node = container.tailscale_node[0] if container.tailscale_node else None
                else:
                    ts_node = container.tailscale_node

            if ts_node:
                # O status online é inferido pela propriedade .online do próprio model
                ts_snapshot = PublishedTailscaleNodeSnapshotDTO(
                    installed=ts_node.installed,
                    service_running=ts_node.service_running,
                    version=ts_node.version,
                    machine_id=ts_node.machine_id,
                    node_key=ts_node.node_key,
                    tailscale_ip=ts_node.tailscale_ip,
                    online=ts_node.online,
                    last_sync=ts_node.last_sync,
                    hostname=ts_node.hostname,
                    dns_name=ts_node.dns_name,
                    last_seen=ts_node.last_seen,
                    advertised_routes=ts_node.advertised_routes or [],
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

            snapshots.append(
                PublishedContainerSnapshotDTO(
                    api_local_container_id=container.id,
                    container_number=container.container_number,
                    name=container.name,
                    status=container.status,
                    tailscale=ts_snapshot,
                    access_tokens=tokens,
                )
            )

        print("DEBUG - containers-publicados", snapshots)
        return snapshots

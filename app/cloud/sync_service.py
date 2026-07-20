import logging
from sqlalchemy.orm import Session

from app.cloud.dto import EnvironmentSnapshotDTO, EnvironmentDetailsDTO
from app.cloud.published_container_service import PublishedContainerService
from app.cloud.repository import AgentSettingsRepository

logger = logging.getLogger(__name__)


class EnvironmentSyncService:
    """Orquestrador do snapshot do ambiente (Environment Sync).

    Combina detalhes de registro do Agent com a lista de containers publicados exposta pelo PublishedContainerService.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._agent_settings_repo = AgentSettingsRepository(db)
        self._published_container_service = PublishedContainerService(db)

    def get_public_environment_snapshot(self) -> EnvironmentSnapshotDTO:
        """Monta o snapshot público de sincronização do ambiente local."""
        logger.info("Generating public environment snapshot for Cloud sync")

        # Buscar dados do registro do Agent
        settings = self._agent_settings_repo.get()

        env_id = None
        registered_at = None
        if settings:
            env_id = settings.id
            registered_at = settings.registered_at

        env_details = EnvironmentDetailsDTO(
            id=env_id,
            registered_at=registered_at,
        )

        # Buscar containers expostos pelo PublishedContainerService
        published_containers = self._published_container_service.get_published_containers()

        return EnvironmentSnapshotDTO(
            environment=env_details,
            published_containers=published_containers,
        )

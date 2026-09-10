from app.repositories.base_repository import BaseRepository
from app.models.agent_config import AgentConfig


class AgentConfigRepository(BaseRepository[AgentConfig]):

    def __init__(self, db):
        super().__init__(db, AgentConfig)

    def get_config(self) -> AgentConfig | None:
        """Retorna o registro único de configuração do Agent, se existir."""
        return self.db.query(AgentConfig).first()

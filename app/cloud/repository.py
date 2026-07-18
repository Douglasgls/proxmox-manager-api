from sqlalchemy.orm import Session

from app.cloud.models import AgentSettings


class AgentSettingsRepository:

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> AgentSettings | None:
        """Retorna a configuração do Agent (singleton)."""

        return (
            self.db
            .query(AgentSettings)
            .first()
        )

    def save(self, entity: AgentSettings) -> AgentSettings:
        """Cria um novo registro de configuração."""

        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: AgentSettings) -> AgentSettings:
        """Atualiza o registro existente."""

        self.db.commit()
        self.db.refresh(entity)
        return entity

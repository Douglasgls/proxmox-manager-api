from datetime import datetime
from sqlalchemy.orm import Session
from app.models.container_component import ContainerComponent, ContainerComponentStatus
from app.repositories.base_repository import BaseRepository


class ContainerComponentRepository(BaseRepository[ContainerComponent]):
    """Repositório de dados para a relação container_components."""

    def __init__(self, db: Session):
        super().__init__(db, ContainerComponent)

    def get_by_container_and_component(
        self,
        container_id: str,
        component_id: str,
    ) -> ContainerComponent | None:
        return (
            self.db.query(ContainerComponent)
            .filter(
                ContainerComponent.container_id == container_id,
                ContainerComponent.component_id == component_id,
            )
            .first()
        )

    def list_by_container(self, container_id: str) -> list[ContainerComponent]:
        return (
            self.db.query(ContainerComponent)
            .filter(ContainerComponent.container_id == container_id)
            .all()
        )

    def create_pending_record(
        self,
        container_id: str,
        component_id: str,
    ) -> ContainerComponent:
        existing = self.get_by_container_and_component(container_id, component_id)
        if existing:
            return existing

        entity = ContainerComponent(
            container_id=container_id,
            component_id=component_id,
            status=ContainerComponentStatus.PENDING.value,
        )
        return self.create(entity)

    def update_status(
        self,
        container_component: ContainerComponent,
        status: str,
        error: str | None = None,
        installed_version: str | None = None,
    ) -> ContainerComponent:
        container_component.status = status
        container_component.updated_at = datetime.now()

        if status == ContainerComponentStatus.INSTALLED.value:
            container_component.installed_at = datetime.now()
            container_component.error = None
            if installed_version:
                container_component.installed_version = installed_version
        elif status == ContainerComponentStatus.FAILED.value:
            container_component.error = error

        return self.update(container_component)

from sqlalchemy.orm import Session
from app.models.component import Component
from app.repositories.base_repository import BaseRepository


class ComponentRepository(BaseRepository[Component]):
    """Repositório de dados para o catálogo de componentes."""

    def __init__(self, db: Session):
        super().__init__(db, Component)

    def get_by_slug(self, slug: str) -> Component | None:
        return (
            self.db.query(Component)
            .filter(Component.slug == slug)
            .first()
        )

    def list_active(self, category: str | None = None) -> list[Component]:
        query = self.db.query(Component).filter(Component.is_active.is_(True))
        if category:
            query = query.filter(Component.category == category)
        return query.all()

    def list_all(self) -> list[Component]:
        return self.db.query(Component).all()

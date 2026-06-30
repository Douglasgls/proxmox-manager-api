from typing import Generic
from typing import TypeVar
from typing import Type

from sqlalchemy.orm import Session


Model = TypeVar("Model")


class BaseRepository(
    Generic[Model]
):

    def __init__(
        self,
        db: Session,
        model: Type[Model]
    ):
        self.db = db
        self.model = model


    def get(
        self,
        entity_id
    ):

        return (
            self.db
            .query(self.model)
            .filter(
                self.model.id == entity_id
            )
            .first()
        )


    def list(
        self,
        limit: int = 100
    ):

        return (
            self.db
            .query(
                self.model
            )
            .limit(limit)
            .all()
        )


    def create(
        self,
        entity
    ):

        self.db.add(entity)

        self.db.commit()

        self.db.refresh(entity)

        return entity


    def update(
        self,
        entity
    ):

        self.db.commit()

        self.db.refresh(entity)

        return entity


    def delete(
        self,
        entity
    ):

        self.db.delete(entity)

        self.db.commit()
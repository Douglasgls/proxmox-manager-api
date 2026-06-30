from app.repositories.base_repository import BaseRepository

from app.models.container_action import (
    ContainerAction
)


class ContainerActionRepository(
    BaseRepository[
        ContainerAction
    ]
):

    def __init__(
        self,
        db
    ):
        super().__init__(
            db,
            ContainerAction
        )


    def list_by_container(
        self,
        container_id
    ):

        return (
            self.db
            .query(
                ContainerAction
            )
            .filter(
                ContainerAction.container_id
                ==
                container_id
            )
            .all()
        )

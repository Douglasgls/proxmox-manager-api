from app.repositories.base_repository import BaseRepository

from app.models.container import Container


class ContainerRepository(
    BaseRepository[Container]
):

    def __init__(
        self,
        db
    ):
        super().__init__(
            db,
            Container
        )


    def get_by_name(
        self,
        name: str
    ):

        return (
            self.db
            .query(Container)
            .filter(
                Container.name == name
            )
            .first()
        )


    def get_running(self):

        return (
            self.db
            .query(Container)
            .filter(
                Container.status == "running"
            )
            .all()
        )


    def exists(
        self,
        container_id
    ):

        return (
            self.db
            .query(Container)
            .filter(
                Container.id == container_id
            )
            .first()
            is not None
        )

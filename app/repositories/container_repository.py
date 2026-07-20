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

    def get_published_containers(self) -> list[Container]:
        """Retorna todos os containers que possuem registro em tailscale_nodes,

        carregando de forma eager os nodes do Tailscale e access tokens.
        """
        from sqlalchemy.orm import joinedload, selectinload
        from app.tailscale.model import TailscaleNode

        return (
            self.db.query(Container)
            .join(TailscaleNode)
            .options(
                joinedload(Container.tailscale_node),
                selectinload(Container.access_tokens)
            )
            .all()
        )


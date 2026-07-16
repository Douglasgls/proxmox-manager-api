from sqlalchemy.orm import Session
from app.tailscale.model import TailscaleNode


class TailscaleRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_container_id(self, container_id: str) -> TailscaleNode | None:
        return (
            self.session.query(TailscaleNode)
            .filter(TailscaleNode.container_id == container_id)
            .first()
        )

    def create(self, node: TailscaleNode) -> TailscaleNode:
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    def update(self, node: TailscaleNode) -> TailscaleNode:
        self.session.commit()
        self.session.refresh(node)
        return node

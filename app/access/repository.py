from sqlalchemy.orm import Session
from app.access.model import AccessToken


class AccessTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, token: AccessToken) -> AccessToken:
        self.session.add(token)
        self.session.commit()
        self.session.refresh(token)
        return token

    def get_by_container(self, container_id: str) -> list[AccessToken]:
        return self.session.query(AccessToken).filter(
            AccessToken.container_id == container_id
        ).all()

    def get_by_hash(self, token_hash: str) -> AccessToken | None:
        return self.session.query(AccessToken).filter(
            AccessToken.token_hash == token_hash
        ).first()

    def get_by_id(self, token_id: str) -> AccessToken | None:
        return self.session.query(AccessToken).filter(
            AccessToken.id == token_id
        ).first()

    def revoke(self, token: AccessToken) -> AccessToken:
        token.active = False
        self.session.commit()
        self.session.refresh(token)
        return token

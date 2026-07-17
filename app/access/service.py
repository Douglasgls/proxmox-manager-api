import secrets
import hashlib
from datetime import datetime, timedelta
from app.access.model import AccessToken
from app.access.repository import AccessTokenRepository


class AccessTokenService:
    def __init__(self, repository: AccessTokenRepository):
        self.repository = repository

    def generate_token(self) -> str:
        """Gera um token criptograficamente seguro."""
        return secrets.token_urlsafe(48)

    def hash_token(self, token: str) -> str:
        """Gera um hash SHA-256 do token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_token_record(self, container_id: str, description: str | None = None) -> tuple[AccessToken, str]:
        """Cria e persiste um novo token de acesso, retornando o registro e o token em texto puro."""
        raw_token = self.generate_token()
        token_hash = self.hash_token(raw_token)
        
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        token_record = AccessToken(
            container_id=container_id,
            token_hash=token_hash,
            description=description,
            expires_at=expires_at,
            active=True
        )
        
        token_record = self.repository.create(token_record)
        return token_record, raw_token

    def revoke_token(self, token_id: str) -> AccessToken | None:
        """Revoga um token baseado no ID."""
        token = self.repository.get_by_id(token_id)
        if not token:
            return None
            
        token.revoked_at = datetime.utcnow()
        return self.repository.revoke(token)
        
    def list_by_container(self, container_id: str) -> list[AccessToken]:
        """Lista os tokens de um container."""
        return self.repository.get_by_container(container_id)

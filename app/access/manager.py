from app.access.service import AccessTokenService
from app.access.dto import AccessTokenCreateResponseDTO, AccessTokenMetadataDTO


class AccessTokenManager:
    def __init__(self, service: AccessTokenService):
        self.service = service

    def create_token(self, container_id: str, description: str | None = None) -> AccessTokenCreateResponseDTO:
        token_record, raw_token = self.service.create_token_record(container_id, description)
        
        return AccessTokenCreateResponseDTO(
            token=raw_token,
            expires_at=token_record.expires_at,
            created_at=token_record.created_at
        )
        
    def list_tokens_metadata(self, container_id: str) -> list[AccessTokenMetadataDTO]:
        tokens = self.service.list_by_container(container_id)
        
        return [
            AccessTokenMetadataDTO(
                id=t.id,
                created_at=t.created_at,
                expires_at=t.expires_at,
                active=t.active,
                last_used_at=t.last_used_at
            ) for t in tokens
        ]
        
    def revoke_token(self, token_id: str) -> bool:
        token = self.service.revoke_token(token_id)
        return token is not None

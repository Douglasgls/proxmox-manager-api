from datetime import datetime, timezone
from app.access.service import AccessTokenService
from app.access.dto import AccessTokenCreateResponseDTO, AccessTokenMetadataDTO


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AccessTokenManager:
    def __init__(self, service: AccessTokenService):
        self.service = service

    def create_token(
        self,
        container_id: str,
        description: str | None = None,
        expires_in_days: int | None = None,
        expires_in_hours: int | None = None,
        expires_in_minutes: int | None = None,
    ) -> AccessTokenCreateResponseDTO:
        token_record, raw_token = self.service.create_token_record(
            container_id=container_id,
            description=description,
            expires_in_days=expires_in_days,
            expires_in_hours=expires_in_hours,
            expires_in_minutes=expires_in_minutes,
        )
        
        try:
            from app.core.event_bus import internal_event_bus, EnvironmentChanged
            print("\n[EVENT ACTION] Access Token criado. Publicando EnvironmentChanged...\n")
            internal_event_bus.publish(EnvironmentChanged())
        except Exception:
            # We don't import logger to avoid any issues or we can import it locally if needed,
            # but raising/log is not strictly required if we just want a simple notify.
            pass

        return AccessTokenCreateResponseDTO(
            token=raw_token,
            expires_at=_ensure_utc(token_record.expires_at),
            created_at=_ensure_utc(token_record.created_at),
            description=token_record.description
        )
        
    def list_tokens_metadata(self, container_id: str) -> list[AccessTokenMetadataDTO]:
        tokens = self.service.list_by_container(container_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        changed = False
        for t in tokens:
            if t.active and t.expires_at < now:
                t.active = False
                changed = True
        if changed:
            try:
                self.service.repository.session.commit()
            except Exception:
                pass
        
        return [
            AccessTokenMetadataDTO(
                id=t.id,
                created_at=_ensure_utc(t.created_at),
                expires_at=_ensure_utc(t.expires_at),
                active=t.active,
                last_used_at=_ensure_utc(t.last_used_at),
                description=t.description
            ) for t in tokens
        ]
        
    def revoke_token(self, token_id: str) -> bool:
        token = self.service.revoke_token(token_id)
        if token is not None:
            try:
                from app.core.event_bus import internal_event_bus, EnvironmentChanged
                print("\n[EVENT ACTION] Access Token revogado. Publicando EnvironmentChanged...\n")
                internal_event_bus.publish(EnvironmentChanged())
            except Exception:
                pass
            return True
        return False

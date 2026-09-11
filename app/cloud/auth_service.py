import logging
from datetime import datetime, timezone, timedelta

import httpx

from app.cloud import crypto
from app.cloud.models import AgentSettings

logger = logging.getLogger(__name__)

_JWT_RENEWAL_MARGIN_SECONDS = 60


class CloudAuthService:
    """Responsável por autenticar o Agent na Cloud usando Environment Token.

    Nunca conhece WebSocket.
    """

    async def authenticate(
        self,
        cloud_url: str,
        environment_token: str,
    ) -> tuple[str, datetime, str | None]:
        """Faz POST /agent/auth na Cloud e retorna (jwt, expires_at, environment_id).

        Raises:
            httpx.HTTPStatusError: se a Cloud rejeitar o token.
            httpx.ConnectError: se a Cloud estiver indisponível.
        """

        url = f"{cloud_url.rstrip('/')}/agent/auth"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json={"environment_token": environment_token},
            )
            response.raise_for_status()

        data = response.json()

        jwt_token = data["access_token"]
        expires_in = data["expires_in"]
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        env_id = data.get("environment_id") or data.get("cloud_environment_id")
        if not env_id:
            try:
                import jwt as pyjwt
                decoded = pyjwt.decode(jwt_token, options={"verify_signature": False})
                env_id = decoded.get("environment_id") or decoded.get("env_id") or decoded.get("sub")
            except Exception as exc:
                logger.debug("Could not decode JWT claims for environment_id: %s", exc)

        logger.info("Authenticated with Cloud. JWT expires in %ds (env_id=%s)", expires_in, env_id)

        return jwt_token, expires_at, env_id

    def is_jwt_expired(self, expires_at: datetime | None) -> bool:
        """Verifica se o JWT está expirado (com margem de segurança)."""

        if expires_at is None:
            return True

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        margin = timedelta(seconds=_JWT_RENEWAL_MARGIN_SECONDS)
        return datetime.now(timezone.utc) >= (expires_at - margin)

    async def renew_jwt(
        self,
        settings: AgentSettings,
        cloud_url: str,
    ) -> tuple[str, datetime, str | None]:
        """Descriptografa o Environment Token e autentica novamente."""

        token = crypto.decrypt(settings.environment_token_encrypted)
        return await self.authenticate(cloud_url, token)


from datetime import datetime, timedelta, timezone

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError as PyJWTInvalidTokenError

from app.core.exceptions import InvalidToken, TokenExpired
from app.core.settings import Settings


class JWTManager:
    ACCESS_TOKEN_TYPE = "access"
    REFRESH_TOKEN_TYPE = "refresh"

    def __init__(self, settings: Settings):
        self.settings = settings

    def create_access_token(self, user_id: str, subject: str) -> str:
        return self._create_token(
            user_id=user_id,
            subject=subject,
            token_type=self.ACCESS_TOKEN_TYPE,
            expires_in=timedelta(
                minutes=self.settings.access_token_expire_minutes
            ),
        )

    def create_refresh_token(self, user_id: str, subject: str) -> str:
        return self._create_token(
            user_id=user_id,
            subject=subject,
            token_type=self.REFRESH_TOKEN_TYPE,
            expires_in=timedelta(days=self.settings.refresh_token_expire_days),
        )

    def decode_access_token(self, token: str) -> dict:
        return self._decode(token, self.ACCESS_TOKEN_TYPE)

    def decode_refresh_token(self, token: str) -> dict:
        return self._decode(token, self.REFRESH_TOKEN_TYPE)

    def _create_token(
        self,
        user_id: str,
        subject: str,
        token_type: str,
        expires_in: timedelta,
    ) -> str:
        payload = {
            "sub": subject,
            "user_id": user_id,
            "type": token_type,
            "exp": datetime.now(timezone.utc) + expires_in,
        }
        return jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def _decode(self, token: str, expected_type: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                options={"require": ["sub", "user_id", "exp", "type"]},
            )
        except ExpiredSignatureError as exc:
            raise TokenExpired("Token expired") from exc
        except PyJWTInvalidTokenError as exc:
            raise InvalidToken("Invalid token") from exc

        if payload.get("type") != expected_type:
            raise InvalidToken("Invalid token type")

        return payload

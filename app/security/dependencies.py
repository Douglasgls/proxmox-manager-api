from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import InvalidToken
from app.core.dependencies import get_auth_service
from app.models.user import User
from app.services.auth_service import AuthService


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidToken("Missing bearer token")

    return auth_service.get_authenticated_user(credentials.credentials)

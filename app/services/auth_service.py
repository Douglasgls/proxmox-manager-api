from app.core.exceptions import InvalidCredentials, UnauthorizedUser
from app.dto.response.token import TokenResponseDTO
from app.models.user import User
from app.security.jwt import JWTManager
from app.security.password import PasswordManager
from app.services.user_service import UserService


class AuthService:
    """Coordinates stateless authentication and secure user credential handling."""

    def __init__(
        self,
        user_service: UserService,
        password_manager: PasswordManager,
        jwt_manager: JWTManager,
    ):
        self.user_service = user_service
        self.password_manager = password_manager
        self.jwt_manager = jwt_manager

    def create_user(
        self,
        username: str,
        password: str,
        email: str,
        role: str = "admin",
    ) -> User:
        return self.user_service.create(
            username=username,
            password_hash=self.password_manager.hash(password),
            email=email,
            role=role,
        )

    def login(self, email: str, password: str) -> TokenResponseDTO:
        user = self.user_service.get_by_email(email)

        if not user:
            self.password_manager.verify_missing_user_password(password)
            raise InvalidCredentials("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedUser("User is inactive")

        if not self.password_manager.verify(password, user.password_hash):
            raise InvalidCredentials("Invalid email or password")

        return self._tokens_for(user)

    def refresh(self, refresh_token: str) -> TokenResponseDTO:
        payload = self.jwt_manager.decode_refresh_token(refresh_token)
        user = self._get_active_user(payload["user_id"])
        return self._tokens_for(user)

    def get_authenticated_user(self, access_token: str) -> User:
        payload = self.jwt_manager.decode_access_token(access_token)
        return self._get_active_user(payload["user_id"])

    def logout(self, _user: User) -> None:
        """Kept as an extension point for a future token blacklist."""

    def _get_active_user(self, user_id: str) -> User:
        user = self.user_service.get(user_id)
        if not user or not user.is_active:
            raise UnauthorizedUser("User is not authorized")
        return user

    def _tokens_for(self, user: User) -> TokenResponseDTO:
        return TokenResponseDTO(
            access_token=self.jwt_manager.create_access_token(
                user_id=user.id,
                subject=user.email,
            ),
            refresh_token=self.jwt_manager.create_refresh_token(
                user_id=user.id,
                subject=user.email,
            ),
            expires_in=self.jwt_manager.settings.access_token_expire_minutes * 60,
        )

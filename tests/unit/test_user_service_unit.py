import pytest

from app.core.exceptions import DomainValidationError, InvalidCredentials, UnauthorizedUser
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.services.auth_service import AuthService


def test_user_service_create_user_success(db, password_manager):
    repo = UserRepository(db)
    service = UserService(repo)

    password_hash = password_manager.hash("Pass123!")
    user = service.create(
        username="new_user",
        password_hash=password_hash,
        email="new_user@example.com",
        role="admin",
    )

    assert user.id is not None
    assert user.username == "new_user"
    assert user.email == "new_user@example.com"
    assert user.role == "admin"


def test_user_service_create_duplicate_username_fails(db, test_user, password_manager):
    repo = UserRepository(db)
    service = UserService(repo)

    with pytest.raises(DomainValidationError, match="Usuário já existe"):
        service.create(
            username=test_user.username,
            password_hash=password_manager.hash("AnyPass123!"),
            email="different_email@example.com",
        )


def test_user_service_create_duplicate_email_fails(db, test_user, password_manager):
    repo = UserRepository(db)
    service = UserService(repo)

    with pytest.raises(DomainValidationError, match="Este e-mail já está em uso"):
        service.create(
            username="brand_new_username",
            password_hash=password_manager.hash("AnyPass123!"),
            email=test_user.email,
        )


def test_auth_service_login_success(db, test_user, password_manager, jwt_manager):
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    auth_service = AuthService(user_service, password_manager, jwt_manager)

    token_dto = auth_service.login(email=test_user.email, password="Secret123!")
    assert token_dto.access_token is not None
    assert token_dto.refresh_token is not None

    authenticated = auth_service.get_authenticated_user(token_dto.access_token)
    assert authenticated.id == test_user.id
    assert authenticated.username == test_user.username


def test_auth_service_login_invalid_password(db, test_user, password_manager, jwt_manager):
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    auth_service = AuthService(user_service, password_manager, jwt_manager)

    with pytest.raises(InvalidCredentials):
        auth_service.login(email=test_user.email, password="WrongPassword!")


def test_auth_service_login_inactive_user(db, test_user, password_manager, jwt_manager):
    test_user.is_active = False
    db.commit()

    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    auth_service = AuthService(user_service, password_manager, jwt_manager)

    with pytest.raises(UnauthorizedUser):
        auth_service.login(email=test_user.email, password="Secret123!")

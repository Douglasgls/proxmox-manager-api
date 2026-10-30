from app.core.exceptions import DomainValidationError
from app.repositories.user_repository import (
    UserRepository
)
from app.models.user import User
from sqlalchemy.exc import IntegrityError


class UserService:

    def __init__(
        self,
        repository: UserRepository
    ):
        self.repository = repository


    def create(
        self,
        username: str,
        password_hash: str,
        role: str = "admin",
        email: str | None = None,
    ):
        existing = (
            self.repository
            .get_by_username(
                username
            )
        )

        if existing:
            raise DomainValidationError(
                "Usuário já existe. Escolha outro nome de usuário."
            )

        if email and self.repository.get_by_email(email):
            raise DomainValidationError(
                "Este e-mail já está em uso por outro usuário."
            )

        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            role=role
        )

        try:
            return (
                self.repository
                .create(user)
            )
        except IntegrityError as exc:
            if hasattr(self.repository, "db"):
                self.repository.db.rollback()
            msg = str(getattr(exc, "orig", exc)).lower()
            if "username" in msg:
                raise DomainValidationError("Usuário já existe. Escolha outro nome de usuário.")
            elif "email" in msg:
                raise DomainValidationError("Este e-mail já está em uso por outro usuário.")
            raise DomainValidationError("Usuário ou e-mail já cadastrado.")


    def get(
        self,
        user_id
    ):

        return (
            self.repository
            .get(user_id)
        )


    def get_by_email(
        self,
        email: str,
    ):
        return self.repository.get_by_email(email)

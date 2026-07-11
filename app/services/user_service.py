from app.repositories.user_repository import (
    UserRepository
)

from app.models.user import User


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
            raise ValueError(
                "Usuário já existe"
            )

        if email and self.repository.get_by_email(email):
            raise ValueError(
                "Email já está em uso"
            )

        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            role=role
        )

        return (
            self.repository
            .create(user)
        )


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

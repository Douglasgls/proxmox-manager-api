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
        role: str = "admin"
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

        user = User(
            username=username,
            password_hash=password_hash,
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
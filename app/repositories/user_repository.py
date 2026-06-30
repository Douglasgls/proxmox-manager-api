from app.repositories.base_repository import BaseRepository

from app.models.user import User


class UserRepository(
    BaseRepository[User]
):

    def __init__(
        self,
        db
    ):
        super().__init__(
            db,
            User
        )


    def get_by_username(
        self,
        username: str
    ):

        return (
            self.db
            .query(User)
            .filter(
                User.username == username
            )
            .first()
        )

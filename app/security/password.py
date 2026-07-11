from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher


class PasswordManager:
    """Encapsulates BCrypt hashing and password verification."""

    def __init__(self):
        self._password_hash = PasswordHash((BcryptHasher(),))
        self._dummy_hash = self._password_hash.hash("invalid-password")

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str | None) -> bool:
        target_hash = password_hash or self._dummy_hash
        try:
            return self._password_hash.verify(password, target_hash)
        except ValueError:
            return False

    def verify_missing_user_password(self, password: str) -> None:
        self.verify(password, self._dummy_hash)

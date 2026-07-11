import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        values = {
            "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
            "JWT_ALGORITHM": os.getenv("JWT_ALGORITHM"),
            "ACCESS_TOKEN_EXPIRE_MINUTES": os.getenv(
                "ACCESS_TOKEN_EXPIRE_MINUTES"
            ),
            "REFRESH_TOKEN_EXPIRE_DAYS": os.getenv(
                "REFRESH_TOKEN_EXPIRE_DAYS"
            ),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing authentication environment variables: " + ", ".join(missing)
            )

        try:
            settings = cls(
                jwt_secret_key=values["JWT_SECRET_KEY"],
                jwt_algorithm=values["JWT_ALGORITHM"],
                access_token_expire_minutes=int(
                    values["ACCESS_TOKEN_EXPIRE_MINUTES"]
                ),
                refresh_token_expire_days=int(
                    values["REFRESH_TOKEN_EXPIRE_DAYS"]
                ),
            )
            if (
                settings.access_token_expire_minutes <= 0
                or settings.refresh_token_expire_days <= 0
            ):
                raise ValueError
            return settings
        except ValueError as exc:
            raise RuntimeError(
                "Authentication token expiration settings must be positive integers"
            ) from exc

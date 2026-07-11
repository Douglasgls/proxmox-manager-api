class DomainValidationError(ValueError):
    """Raised when application business rules reject input data."""


class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class InvalidCredentials(AuthenticationError):
    """Raised when an email/password pair is invalid."""


class TokenExpired(AuthenticationError):
    """Raised when a JWT has expired."""


class InvalidToken(AuthenticationError):
    """Raised when a JWT cannot be authenticated or validated."""


class UnauthorizedUser(AuthenticationError):
    """Raised when the authenticated user is unavailable or inactive."""

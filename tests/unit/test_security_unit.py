from datetime import datetime, timedelta, timezone
import pytest
import jwt

from app.core.exceptions import InvalidToken, TokenExpired
from app.security.password import PasswordManager
from app.security.jwt import JWTManager
from app.cloud import crypto


def test_password_manager_hash_and_verify(password_manager):
    raw_pass = "MySecretPass@123"
    hashed = password_manager.hash(raw_pass)

    assert hashed.startswith("$2")
    assert password_manager.verify(raw_pass, hashed) is True
    assert password_manager.verify("WrongPass@123", hashed) is False


def test_jwt_access_token_creation_and_payload(jwt_manager):
    token = jwt_manager.create_access_token(user_id="user-123", subject="testuser")
    payload = jwt_manager.decode_access_token(token)

    assert payload["sub"] == "testuser"
    assert payload["user_id"] == "user-123"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_jwt_refresh_token_cannot_be_used_as_access_token(jwt_manager):
    refresh_token = jwt_manager.create_refresh_token(user_id="user-123", subject="testuser")

    with pytest.raises(InvalidToken, match="Invalid token type"):
        jwt_manager.decode_access_token(refresh_token)


def test_jwt_expired_token_raises_token_expired(jwt_manager):
    settings = jwt_manager.settings
    expired_payload = {
        "sub": "testuser",
        "user_id": "user-123",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(TokenExpired):
        jwt_manager.decode_access_token(expired_token)


def test_cloud_crypto_encrypt_and_decrypt():
    original_text = "env_token_secret_123456789"
    encrypted = crypto.encrypt(original_text)

    assert isinstance(encrypted, str)
    assert encrypted != original_text

    decrypted = crypto.decrypt(encrypted)
    assert decrypted == original_text

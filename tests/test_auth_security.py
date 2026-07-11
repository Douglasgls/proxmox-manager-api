import unittest
from datetime import datetime, timedelta, timezone

import jwt

from app.core.exceptions import InvalidToken, TokenExpired
from app.core.settings import Settings
from app.security.jwt import JWTManager
from app.security.password import PasswordManager


class PasswordManagerTests(unittest.TestCase):
    def test_hashes_and_verifies_password_with_bcrypt(self):
        manager = PasswordManager()
        password_hash = manager.hash("correct-horse-battery-staple")

        self.assertTrue(password_hash.startswith("$2"))
        self.assertTrue(
            manager.verify("correct-horse-battery-staple", password_hash)
        )
        self.assertFalse(manager.verify("wrong-password", password_hash))


class JWTManagerTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            jwt_secret_key="test-secret-key-with-at-least-thirty-two-bytes",
            jwt_algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )
        self.manager = JWTManager(self.settings)

    def test_access_token_has_required_claims(self):
        token = self.manager.create_access_token("user-1", "user@example.com")
        payload = self.manager.decode_access_token(token)

        self.assertEqual(payload["sub"], "user@example.com")
        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["type"], "access")

    def test_refresh_token_cannot_be_used_as_access_token(self):
        token = self.manager.create_refresh_token("user-1", "user@example.com")

        with self.assertRaises(InvalidToken):
            self.manager.decode_access_token(token)

    def test_expired_token_is_rejected(self):
        token = jwt.encode(
            {
                "sub": "user@example.com",
                "user_id": "user-1",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

        with self.assertRaises(TokenExpired):
            self.manager.decode_access_token(token)

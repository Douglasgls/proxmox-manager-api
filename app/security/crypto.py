import base64
import hashlib
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()


import logging

logger = logging.getLogger(__name__)

def _get_fernet() -> Fernet:
    # Use AGENT_ENCRYPTION_KEY if available, else derive from JWT_SECRET_KEY as a temporary migration fallback
    key = os.getenv("AGENT_ENCRYPTION_KEY")
    if not key:
        jwt_key = os.getenv("JWT_SECRET_KEY")
        if not jwt_key:
            raise RuntimeError("AGENT_ENCRYPTION_KEY must be set in .env for persistent secrets.")
        logger.warning("AGENT_ENCRYPTION_KEY is missing! Falling back to JWT_SECRET_KEY for decryption/encryption. This is meant only as a temporary migration fallback.")
        # Derive a 32-byte key from JWT_SECRET_KEY using SHA-256
        key_bytes = hashlib.sha256(jwt_key.encode()).digest()
        key = base64.urlsafe_b64encode(key_bytes).decode()
    
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()

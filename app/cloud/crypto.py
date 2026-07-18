import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

_ENCRYPTION_KEY = os.getenv("CLOUD_ENCRYPTION_KEY")


def _get_fernet() -> Fernet:
    if not _ENCRYPTION_KEY:
        raise RuntimeError(
            "CLOUD_ENCRYPTION_KEY not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(_ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()

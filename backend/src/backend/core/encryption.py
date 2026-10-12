"""Symmetric encryption for secrets we store at rest (user-supplied LLM keys,
and later OAuth tokens for the `integrations` table). One Fernet key for the
whole app, from ENCRYPTION_KEY — rotate by re-encrypting, not by adding a mode.
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from backend.core.config import get_settings


class EncryptionNotConfiguredError(RuntimeError):
    pass


@lru_cache
def _get_fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise EncryptionNotConfiguredError("ENCRYPTION_KEY is not set")
    return Fernet(key.encode())


def encrypt_text(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()

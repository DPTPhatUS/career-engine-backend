from cryptography.fernet import Fernet

from app.core.config import Settings


def get_fernet(settings: Settings) -> Fernet:
    return Fernet(settings.encryption_key.encode("utf-8"))


def encrypt_text(value: str, fernet: Fernet) -> str:
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str, fernet: Fernet) -> str:
    return fernet.decrypt(value.encode("utf-8")).decode("utf-8")

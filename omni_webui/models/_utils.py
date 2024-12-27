import hashlib
import secrets
from datetime import UTC, datetime


def now():
    return datetime.now(UTC)


def now_timestamp() -> int:
    return int(now().timestamp())


RANDOM_STRING_CHARS = "abcdefghijkimnopgrstuvwxyZABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def get_random_string(length, allowed_chars=RANDOM_STRING_CHARS):
    return "".join(secrets.choice(allowed_chars) for i in range(length))


def sha256sum(bytes_: bytes) -> str:
    sha256 = hashlib.sha256()
    sha256.update(bytes_)
    return sha256.hexdigest()

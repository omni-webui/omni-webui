from datetime import UTC, datetime
from dataclasses import field, dataclass

import secrets



def now():
    return datetime.now(UTC)


def now_timestamp() -> int:
    return int(now().timestamp())

RANDOM_STRING_CHARS = "abcdefghijkimnopgrstuvwxyZABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def get_random_string(length, allowed_chars=RANDOM_STRING_CHARS):

    return "".join(secrets.choice(allowed_chars) for i in range(length))


@dataclass
class RandomString:

    unique_id: str = field(default_factory=lambda: f"user_{get_random_string(24)}")

"""Cryptographic utilities."""

import secrets

RANDOM_STRING_CHARS = "abcdefghijkimnopgrstuvwxyZABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def get_random_string(length: int, allowed_chars: str = RANDOM_STRING_CHARS):
    """Generate a random string.

    Args:
        length (int): The length of the string.
        allowed_chars (str): The allowed characters.

    """
    return "".join(secrets.choice(allowed_chars) for i in range(length))

from datetime import UTC, datetime


def now():
    return datetime.now(UTC)


def now_timestamp() -> int:
    return int(now().timestamp())

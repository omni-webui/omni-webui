from datetime import timedelta

import pytest


def test_parse_duration():
    from omni_webui.utils.misc import parse_duration

    assert parse_duration("-1") is None
    assert parse_duration("0") is None
    assert parse_duration("1d") == timedelta(days=1)
    assert parse_duration("1d1h") == timedelta(days=1, hours=1)
    assert parse_duration("1d1h1m") == timedelta(days=1, hours=1, minutes=1)
    assert parse_duration("1d1h1m1s") == timedelta(
        days=1, hours=1, minutes=1, seconds=1
    )
    assert parse_duration("1d1h1m1s1ms") == timedelta(
        days=1, hours=1, minutes=1, seconds=1, milliseconds=1
    )
    assert parse_duration("1w1d1h1m1s1ms") == timedelta(
        weeks=1, days=1, hours=1, minutes=1, seconds=1, milliseconds=1
    )
    with pytest.raises(ValueError):
        parse_duration("1d1w")

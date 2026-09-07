"""Unit conversion + parsing invariants for realtime_engine.sources.transforms.

Pure functions, no Django/Redis/HTTP required. Mirrors the coverage of the
navsat-bridge transforms tests these were ported from.
"""

from datetime import UTC, datetime

import pytest

from realtime_engine.sources.transforms import get_by_path, km_to_m, kmh_to_ms, parse_cr_datetime


# ---------------------------------------------------------------------------
# kmh_to_ms / km_to_m
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kmh, ms",
    [
        (0, 0.0),
        (36, 10.0),  # classic sanity pair
        (90, 25.0),
        (100, 27.77777777777778),
    ],
)
def test_kmh_to_ms(kmh, ms):
    assert kmh_to_ms(kmh) == pytest.approx(ms)


@pytest.mark.parametrize(
    "km, m",
    [
        (0, 0.0),
        (1, 1000.0),
        (112, 112_000.0),  # NavSat odometer example
    ],
)
def test_km_to_m(km, m):
    assert km_to_m(km) == pytest.approx(m)


# ---------------------------------------------------------------------------
# parse_cr_datetime
# ---------------------------------------------------------------------------


def test_parse_cr_datetime_known_value():
    # 2026-07-21 14:19:19 America/Costa_Rica (UTC-6, no DST)
    # = 2026-07-21 20:19:19 UTC
    epoch = parse_cr_datetime("2026-07-21 14:19:19")
    expected = datetime(2026, 7, 21, 20, 19, 19, tzinfo=UTC).timestamp()
    assert epoch == int(expected)


def test_parse_cr_datetime_rejects_garbage():
    with pytest.raises(ValueError):
        parse_cr_datetime("not a datetime")


def test_parse_cr_datetime_honors_custom_format_and_tz():
    # ISO-ish format, UTC — sanity check that fmt/tz are actually threaded through.
    epoch = parse_cr_datetime("2026-01-01T00:00:00", fmt="%Y-%m-%dT%H:%M:%S", tz="UTC")
    assert epoch == int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())


# ---------------------------------------------------------------------------
# get_by_path
# ---------------------------------------------------------------------------


def test_get_by_path_top_level_hit():
    assert get_by_path({"latitude": 9.93}, "latitude") == 9.93


def test_get_by_path_nested_hit():
    assert get_by_path({"a": {"b": {"c": 42}}}, "a.b.c") == 42


def test_get_by_path_missing_key_returns_none():
    assert get_by_path({"a": 1}, "b") is None


def test_get_by_path_missing_nested_key_returns_none():
    assert get_by_path({"a": {"b": 1}}, "a.x.y") is None


def test_get_by_path_non_dict_intermediate_returns_none():
    assert get_by_path({"a": 5}, "a.b") is None


def test_get_by_path_empty_path_returns_none():
    assert get_by_path({"a": 1}, "") is None

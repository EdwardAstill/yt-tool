"""Tests for FetchConfig defaults and rate-limit error detection."""

from yt_tool.core import (
    DEFAULT_PLAYER_CLIENTS,
    FetchConfig,
    _looks_rate_limited,
)


def test_defaults():
    cfg = FetchConfig()
    assert cfg.backend == "auto"
    assert cfg.cookies is None
    assert cfg.cookies_from_browser is None
    assert cfg.max_retries == 3
    assert cfg.base_delay == 1.0
    assert cfg.proxies == [None]
    assert cfg.source_address is None
    assert cfg.player_client == DEFAULT_PLAYER_CLIENTS
    assert cfg.sleep_subtitles == 0.0


def test_proxies_passes_through():
    cfg = FetchConfig(proxies=["http://a:1080", "http://b:1080"])
    assert cfg.proxies == ["http://a:1080", "http://b:1080"]


def test_proxies_empty_list_falls_back_to_direct():
    cfg = FetchConfig(proxies=[])
    assert cfg.proxies == [None]


def test_explicit_impersonate_overrides_default():
    cfg = FetchConfig(impersonate="safari-18.0")
    assert cfg.impersonate == "safari-18.0"


def test_rate_limit_detection_429():
    assert _looks_rate_limited(Exception("HTTP Error 429: Too Many Requests"))


def test_rate_limit_detection_too_many_requests():
    assert _looks_rate_limited(Exception("Server says: Too Many Requests"))


def test_rate_limit_detection_blocking_requests():
    assert _looks_rate_limited(
        Exception("YouTube is blocking requests from your IP.")
    )


def test_rate_limit_detection_negative():
    assert not _looks_rate_limited(Exception("404 Not Found"))
    assert not _looks_rate_limited(Exception("subtitle file empty"))

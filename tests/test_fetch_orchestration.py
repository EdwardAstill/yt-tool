"""Tests for fetch_transcript orchestration: backend fallback, retry, proxy rotation.

The api/ytdlp helpers are monkey-patched so no network is touched.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from yt_tool import core


@pytest.fixture(autouse=True)
def _patch_sleep(monkeypatch):
    """Skip exponential backoff sleeps so tests run instantly."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def test_api_backend_succeeds_first(monkeypatch):
    calls: list[str] = []

    def api(video_id, cfg, proxy=None):
        calls.append(f"api:{video_id}")
        return "from-api"

    def ytdlp(video_id, cfg, proxy=None):
        calls.append("ytdlp")
        raise AssertionError("ytdlp should not be called when api succeeds")

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", ytdlp)

    assert core.fetch_transcript("vid1") == "from-api"
    assert calls == ["api:vid1"]


def test_falls_back_to_ytdlp_when_api_fails_with_non_rate_limit(monkeypatch):
    calls: list[str] = []

    def api(video_id, cfg, proxy=None):
        calls.append("api")
        raise RuntimeError("transcript disabled")

    def ytdlp(video_id, cfg, proxy=None):
        calls.append("ytdlp")
        return "from-ytdlp"

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", ytdlp)

    assert core.fetch_transcript("vid1") == "from-ytdlp"
    assert calls == ["api", "ytdlp"]


def test_retries_on_rate_limit_then_succeeds(monkeypatch):
    attempts = {"n": 0}

    def api(video_id, cfg, proxy=None):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return "ok"

    def ytdlp(video_id, cfg, proxy=None):
        raise AssertionError("ytdlp should not be called when api eventually succeeds")

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", ytdlp)

    cfg = core.FetchConfig(backend="api", max_retries=3)
    assert core.fetch_transcript("v", cfg=cfg) == "ok"
    assert attempts["n"] == 3


def test_proxy_rotation_on_rate_limit(monkeypatch):
    attempts: list[Any] = []

    def api(video_id, cfg, proxy=None):
        attempts.append(proxy)
        if proxy != "http://b:1080":
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return "ok"

    def ytdlp(video_id, cfg, proxy=None):
        raise AssertionError("ytdlp should not be called")

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", ytdlp)

    cfg = core.FetchConfig(
        backend="api",
        proxies=["http://a:1080", "http://b:1080"],
        max_retries=1,
    )
    assert core.fetch_transcript("v", cfg=cfg) == "ok"
    assert attempts == ["http://a:1080", "http://b:1080"]


def test_pinned_backend_does_not_fall_back(monkeypatch):
    def api(video_id, cfg, proxy=None):
        raise AssertionError("api should not be called when backend=ytdlp")

    def ytdlp(video_id, cfg, proxy=None):
        raise RuntimeError("real ytdlp failure")

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", ytdlp)

    cfg = core.FetchConfig(backend="ytdlp", max_retries=1)
    with pytest.raises(core.TranscriptError) as exc:
        core.fetch_transcript("v", cfg=cfg)
    assert "real ytdlp failure" in str(exc.value)


def test_invalid_backend_raises_value_error():
    with pytest.raises(ValueError):
        core.fetch_transcript("v", backend="bogus")


def test_all_backends_fail_raises_transcript_error(monkeypatch):
    def boom(video_id, cfg, proxy=None):
        raise RuntimeError("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr(core, "_fetch_via_api", boom)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", boom)

    cfg = core.FetchConfig(max_retries=1)
    with pytest.raises(core.TranscriptError):
        core.fetch_transcript("v", cfg=cfg)


def test_non_rate_limit_error_does_not_consume_retries(monkeypatch):
    """A non-429 error in api backend should fall through to ytdlp on first try, not retry."""
    api_calls = {"n": 0}
    ytdlp_calls = {"n": 0}

    def api(video_id, cfg, proxy=None):
        api_calls["n"] += 1
        raise RuntimeError("video unavailable")

    def ytdlp(video_id, cfg, proxy=None):
        ytdlp_calls["n"] += 1
        return "ok"

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(core, "_fetch_via_ytdlp", ytdlp)

    cfg = core.FetchConfig(max_retries=5)
    assert core.fetch_transcript("v", cfg=cfg) == "ok"
    assert api_calls["n"] == 1
    assert ytdlp_calls["n"] == 1


def test_kwargs_back_compat(monkeypatch):
    """`fetch_transcript(v, backend='api', max_retries=2)` still works without cfg."""

    def api(video_id, cfg, proxy=None):
        assert cfg.backend == "api"
        assert cfg.max_retries == 2
        return "ok"

    monkeypatch.setattr(core, "_fetch_via_api", api)
    monkeypatch.setattr(
        core,
        "_fetch_via_ytdlp",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("unused")),
    )

    assert core.fetch_transcript("v", backend="api", max_retries=2) == "ok"

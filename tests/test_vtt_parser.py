"""Tests for the VTT/SRT subtitle parser used by the yt-dlp backend."""

from yt_tool.core import _vtt_to_text


def test_strips_webvtt_header_and_metadata():
    src = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:01.000
hello world
"""
    assert _vtt_to_text(src) == "hello world"


def test_strips_cue_indices_and_timestamps():
    src = """1
00:00:00.000 --> 00:00:02.000
first line

2
00:00:02.000 --> 00:00:04.000
second line
"""
    assert _vtt_to_text(src) == "first line second line"


def test_strips_inline_tags():
    src = """WEBVTT

00:00:00.000 --> 00:00:01.000
<c.colorE5E5E5>tagged</c> text
"""
    assert _vtt_to_text(src) == "tagged text"


def test_decodes_html_entities():
    src = """WEBVTT

00:00:00.000 --> 00:00:01.000
foo &gt;&gt; bar &amp; baz
"""
    assert _vtt_to_text(src) == "foo >> bar & baz"


def test_collapses_consecutive_duplicate_lines():
    src = """WEBVTT

00:00:00.000 --> 00:00:01.000
hello

00:00:01.000 --> 00:00:02.000
hello

00:00:02.000 --> 00:00:03.000
hello world
"""
    assert _vtt_to_text(src) == "hello hello world"


def test_empty_input_returns_empty():
    assert _vtt_to_text("") == ""


def test_only_metadata_returns_empty():
    assert _vtt_to_text("WEBVTT\nKind: captions\nLanguage: en\n") == ""


def test_real_youtube_auto_caption_shape():
    """Auto-captions sometimes use timestamp-only cues with no index numbers."""
    src = """WEBVTT
Kind: captions
Language: en

00:00:00.480 --> 00:00:02.640 align:start position:0%
Box jumps aren&#39;t going to make you

00:00:02.650 --> 00:00:04.880 align:start position:0%
jump higher.
"""
    assert _vtt_to_text(src) == "Box jumps aren't going to make you jump higher."

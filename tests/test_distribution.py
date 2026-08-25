"""Distribution-level checks for the public command-line interface."""

from importlib.metadata import entry_points

from typer.testing import CliRunner

from yt_tool.cli import app


def test_distribution_exposes_only_the_cli_entry_point():
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in entry_points(group="console_scripts")
        if entry_point.name.startswith("yt-tool")
    }

    assert scripts == {"yt-tool": "yt_tool.cli:main"}


def test_root_help_describes_the_complete_cli_surface():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    introduction = result.stdout.split("Options", maxsplit=1)[0].lower()
    for capability in (
        "transcripts",
        "audio",
        "video",
        "summaries",
        "channels",
        "playlists",
        "search",
    ):
        assert capability in introduction

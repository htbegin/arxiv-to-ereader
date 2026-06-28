"""Tests for the arxiv2epub CLI."""

from typer.testing import CliRunner

from arxiv_to_ereader import __version__
from arxiv_to_ereader.cli import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI commands."""

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "arxiv2epub" in result.stdout

    def test_version_short_flag(self) -> None:
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "arXiv" in result.stdout
        assert "EPUB" in result.stdout
        assert "--no-images" in result.stdout
        assert "--use-id" in result.stdout
        assert "--screen" not in result.stdout
        assert "--width" not in result.stdout

    def test_invalid_paper_id(self) -> None:
        result = runner.invoke(app, ["invalid-not-real-id"])
        assert result.exit_code == 1
        assert "Could not extract arXiv ID" in result.stdout

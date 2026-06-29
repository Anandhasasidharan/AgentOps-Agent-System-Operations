"""Tests for sloctl CLI."""

from typer.testing import CliRunner

from agent_slo.cli import app


runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "apply" in result.output
    assert "status" in result.output
    assert "report" in result.output

"""Unit tests for CLI commands."""
from click.testing import CliRunner
from garminsynapse.cli import cli

def test_sync():
    runner = CliRunner()
    result = runner.invoke(cli, ["sync"])
    assert result.exit_code == 0
    assert "Syncing last" in result.output

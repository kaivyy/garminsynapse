"""Unit tests for CLI commands."""
from unittest.mock import patch
from click.testing import CliRunner
from garminsynapse.cli import cli

def test_sync():
    runner = CliRunner()
    with patch("garminsynapse.etl.extractor.GarminExtractor.extract_all"), \
         patch("garminsynapse.etl.processor.GarminProcessor.process_ingest_directory"):
        result = runner.invoke(cli, ["sync", "--days", "1"])
        assert result.exit_code == 0
        assert "Syncing last" in result.output
        assert "Sync complete!" in result.output

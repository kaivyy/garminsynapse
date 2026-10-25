import pytest
from pathlib import Path
from click.testing import CliRunner
from garminsynapse.cli import cli

SAMPLE_GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="Garmin Connect" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Morning Run</name><trkseg><trkpt lat="-7.7" lon="109.0"/></trkseg></trk>
</gpx>"""


def test_cli_export_success(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "garminsynapse.core.api.GarminAPI.download_activity_gpx",
        lambda self, act_id: SAMPLE_GPX
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "12345", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "Exported activity 12345" in result.output
    out_files = list(tmp_path.glob("*.gpx"))
    assert len(out_files) == 1
    assert out_files[0].read_bytes() == SAMPLE_GPX


def test_cli_export_no_gps(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "garminsynapse.core.api.GarminAPI.download_activity_gpx",
        lambda self, act_id: b""
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "99999", "--output", str(tmp_path)])
    assert result.exit_code != 0
    assert "does not contain GPS" in result.output

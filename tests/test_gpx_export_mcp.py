import pytest
from pathlib import Path
from garminsynapse.mcp.tools import export_activity_gpx

SAMPLE_GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="Garmin Connect" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Trail Run</name><trkseg><trkpt lat="-7.7" lon="109.0"/></trkseg></trk>
</gpx>"""


def test_mcp_export_activity_gpx_success(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "garminsynapse.core.api.GarminAPI.download_activity_gpx",
        lambda self, act_id: SAMPLE_GPX
    )
    result = export_activity_gpx(12345, output_dir=str(tmp_path))
    assert result["status"] == "success"
    assert result["activity_id"] == 12345
    assert result["has_gps_data"] is True
    assert result["file_size_bytes"] == len(SAMPLE_GPX)
    assert Path(result["file_path"]).exists()
    assert Path(result["file_path"]).read_bytes() == SAMPLE_GPX


def test_mcp_export_activity_gpx_no_gps(monkeypatch):
    monkeypatch.setattr(
        "garminsynapse.core.api.GarminAPI.download_activity_gpx",
        lambda self, act_id: b""
    )
    result = export_activity_gpx(99999)
    assert result["status"] == "no_gps_data"
    assert result["has_gps_data"] is False
    assert "does not contain GPS" in result["message"]

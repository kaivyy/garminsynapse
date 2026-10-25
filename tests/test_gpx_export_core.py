import pytest
from unittest.mock import MagicMock
from pathlib import Path
from garminsynapse.core.api import GarminAPI

SAMPLE_GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="Garmin Connect" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Morning Run</name>
    <type>running</type>
    <trkseg>
      <trkpt lat="-7.702" lon="109.023">
        <ele>15.0</ele>
        <time>2026-10-15T10:00:00Z</time>
      </trkpt>
      <trkpt lat="-7.703" lon="109.024">
        <ele>15.2</ele>
        <time>2026-10-15T10:00:05Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""


def test_download_activity_gpx_from_remote_and_caches(tmp_path, monkeypatch):
    export_dir = tmp_path / "exports"
    monkeypatch.setattr("garminsynapse.core.api.DEFAULT_EXPORTS_DIR", export_dir)

    api = GarminAPI()
    mock_instance = MagicMock()
    mock_instance.download_activity.return_value = SAMPLE_GPX
    api._garmin_instance = mock_instance

    result = api.download_activity_gpx(12345)
    assert result == SAMPLE_GPX
    cache_file = export_dir / "12345.gpx"
    assert cache_file.exists()
    assert cache_file.read_bytes() == SAMPLE_GPX


def test_download_activity_gpx_from_cache_hits_disk_first(tmp_path, monkeypatch):
    export_dir = tmp_path / "exports"
    export_dir.mkdir(parents=True)
    cache_file = export_dir / "99999.gpx"
    cache_file.write_bytes(SAMPLE_GPX)
    monkeypatch.setattr("garminsynapse.core.api.DEFAULT_EXPORTS_DIR", export_dir)

    api = GarminAPI()
    mock_instance = MagicMock()
    api._garmin_instance = mock_instance

    result = api.download_activity_gpx(99999)
    assert result == SAMPLE_GPX
    mock_instance.download_activity.assert_not_called()


def test_download_activity_gpx_empty_on_invalid_data(tmp_path, monkeypatch):
    export_dir = tmp_path / "exports"
    monkeypatch.setattr("garminsynapse.core.api.DEFAULT_EXPORTS_DIR", export_dir)

    api = GarminAPI()
    mock_instance = MagicMock()
    mock_instance.download_activity.return_value = b"<html>Error: No GPS track found</html>"
    api._garmin_instance = mock_instance

    result = api.download_activity_gpx(88888)
    assert result == b""
    assert not (export_dir / "88888.gpx").exists()

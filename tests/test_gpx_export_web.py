import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from garminsynapse.web.app import app

SAMPLE_GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="Garmin Connect" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Test Run</name><trkseg><trkpt lat="-7.7" lon="109.0"/></trkseg></trk>
</gpx>"""


@pytest.fixture
def client():
    return TestClient(app)


def test_export_gpx_unauthenticated(client, monkeypatch):
    monkeypatch.setattr("garminsynapse.auth.manager.DualAuthManager.get_active_tokens", lambda self, auto_refresh=True: None)
    response = client.get("/api/v1/activities/12345/export/gpx")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def test_export_gpx_success(client, monkeypatch):
    monkeypatch.setattr("garminsynapse.auth.manager.DualAuthManager.get_active_tokens", lambda self, auto_refresh=True: {"access_token": "valid"})
    monkeypatch.setattr("garminsynapse.core.api.GarminAPI.download_activity_gpx", lambda self, act_id: SAMPLE_GPX)

    response = client.get("/api/v1/activities/12345/export/gpx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert "attachment" in response.headers["content-disposition"]
    assert "12345.gpx" in response.headers["content-disposition"]
    assert response.content == SAMPLE_GPX


def test_export_gpx_no_gps_data(client, monkeypatch):
    monkeypatch.setattr("garminsynapse.auth.manager.DualAuthManager.get_active_tokens", lambda self, auto_refresh=True: {"access_token": "valid"})
    monkeypatch.setattr("garminsynapse.core.api.GarminAPI.download_activity_gpx", lambda self, act_id: b"")

    response = client.get("/api/v1/activities/99999/export/gpx")
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "no_gps_data"

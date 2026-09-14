"""Unit tests for web API routes."""
from fastapi.testclient import TestClient
from garminsynapse.web.app import app

client = TestClient(app)

def test_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert "authenticated" in data
    assert "mcp_server" in data


def test_split_normalization():
    from garminsynapse.core.api import GarminAPI
    api = GarminAPI()
    # Simulating 5km run fractured into interval/manual laps: 1km, 1km, 1km, 750m, 1km, 250m
    raw_laps = [
        {"distance": 1000.0, "duration": 480.0, "averageSpeed": 2.08, "averageHR": 140},
        {"distance": 1000.0, "duration": 480.0, "averageSpeed": 2.08, "averageHR": 145},
        {"distance": 1000.0, "duration": 480.0, "averageSpeed": 2.08, "averageHR": 148},
        {"distance": 750.0, "duration": 360.0, "averageSpeed": 2.08, "averageHR": 150},
        {"distance": 1000.0, "duration": 480.0, "averageSpeed": 2.08, "averageHR": 152},
        {"distance": 250.0, "duration": 120.0, "averageSpeed": 2.08, "averageHR": 155},
    ]
    norm = api._normalize_to_1km_splits(raw_laps, target_dist=1000.0)
    assert len(norm) == 5
    for i in range(5):
        assert norm[i]["distance"] == 1000.0
        assert norm[i]["splitIndex"] == i + 1


import pytest
from starlette.testclient import TestClient
from garminsynapse.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz_endpoint(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "auth" in data
    assert data["database"]["status"] == "connected"
    assert "wal_mode" in data["database"]
    assert "rate_limited" in data["auth"]

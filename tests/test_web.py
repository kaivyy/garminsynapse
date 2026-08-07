from fastapi.testclient import TestClient
from garminsynapse.web.app import app

client = TestClient(app)

def test_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "active"

def test_auth_registration():
    payload = {
        "email": "testuser@meetsense.ai",
        "password": "SecurePassword123",
        "full_name": "Test User"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

from fastapi.testclient import TestClient
from main import app
from app.core.date_parser import parse_natural_deadline

client = TestClient(app)

def test_health_check():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "active"

def test_date_parser():
    parsed = parse_natural_deadline("tomorrow")
    assert parsed != "tomorrow"

def test_qa_endpoint():
    res = client.post("/api/v1/analysis/qa", json={
        "meeting_id": "test_m1",
        "question": "What was the decision on budget?"
    })
    assert res.status_code == 200
    assert "answer" in res.json()
    assert "timestamp_reference" in res.json()
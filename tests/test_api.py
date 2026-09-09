import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Surfaces Tiles UK" in data["message"]
    assert "endpoints" in data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "document_count" in data
    assert "gemini_configured" in data


def test_chat_validation_empty_message():
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 400


def test_chat_endpoint_valid():
    response = client.post("/chat", json={
        "message": "I need grey floor tiles for my bathroom. What do you recommend?"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["statusCode"] == 200
    assert "meta" in data
    assert data["meta"]["status"] == 1
    assert data["meta"]["message"] == "Successfully processed user measurements and preferences"
    assert "data" in data
    assert "Response" in data["data"]
    assert isinstance(data["data"]["Response"], str)
    assert len(data["data"]["Response"]) > 0

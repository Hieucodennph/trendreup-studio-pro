from fastapi.testclient import TestClient

from app import app
from core.url_tools import detect_platform, extract_first_url


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "tiktok" in data["platforms"]


def test_platforms_endpoint():
    client = TestClient(app)
    response = client.get("/api/platforms")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["platforms"]]
    assert {"auto", "youtube", "tiktok", "douyin", "rednote", "instagram", "facebook", "kwai", "likee", "twitter"} <= set(ids)


def test_stats_and_ideas_endpoints():
    client = TestClient(app)
    stats = client.get("/api/stats")
    ideas = client.get("/api/ideas")
    assert stats.status_code == 200
    assert ideas.status_code == 200
    assert "videos" in stats.json()["stats"]
    assert len(ideas.json()["ideas"]) > 0


def test_content_edit_endpoint():
    client = TestClient(app)
    response = client.post("/api/content/edit", json={"text": "test caption http://example.com", "category": "technology"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "http://example.com" not in data["edited"]
    assert "#technology" in data["edited"]


def test_url_tools_clean_and_detect_platform():
    pasted = "Check video này: https://youtu.be/dQw4w9WgXcQ?si=test nhé"
    clean = extract_first_url(pasted)
    assert clean.startswith("https://youtu.be/")
    assert detect_platform(clean) == "youtube"

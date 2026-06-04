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


def test_auto_plan_and_worker_claim_flow():
    client = TestClient(app)
    plan = client.post(
        "/api/automation/plan",
        json={
            "keyword": "car sensor",
            "platforms": ["youtube"],
            "max_results_per_platform": 1,
            "channel_id": "default",
            "auto_queue": True,
        },
    )
    assert plan.status_code == 200
    payload = plan.json()
    assert payload["success"] is True
    assert payload["queued_count"] == 1

    claimed = client.post("/api/worker/claim", json={"worker_id": "test-worker"})
    assert claimed.status_code == 200
    item = claimed.json()["item"]
    assert item is not None
    assert item["status"] == "pending"

    failed = client.post("/api/worker/fail", json={"worker_id": "test-worker", "queue_id": item["id"], "error": "test failure"})
    assert failed.status_code == 200
    runs = client.get("/api/worker/runs")
    assert runs.status_code == 200
    assert len(runs.json()["runs"]) >= 1


def test_url_tools_clean_and_detect_platform():
    pasted = "Check video này: https://youtu.be/dQw4w9WgXcQ?si=test nhé"
    clean = extract_first_url(pasted)
    assert clean.startswith("https://youtu.be/")
    assert detect_platform(clean) == "youtube"

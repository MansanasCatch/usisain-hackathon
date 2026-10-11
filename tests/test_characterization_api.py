from unittest.mock import patch

from fastapi.testclient import TestClient
from usisain_backend.main import app
from usisain_backend.orchestration.events import StepEvent

client = TestClient(app)


def test_docs_and_static_routes():
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower() or "html" in r.headers.get("content-type", "")
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "openapi" in r.json()
    r = client.get("/app/")
    assert r.status_code == 200
    r = client.get("/app/dashboard/")
    assert r.status_code == 200


def test_scans_routes():
    r = client.get("/api/scans")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/api/scans/stats/summary")
    assert r.status_code == 200
    data = r.json()
    assert "total_scans" in data
    assert "by_channel" in data
    assert "by_verdict" in data
    r = client.get("/api/scans/stats/trends")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_settings_routes():
    r = client.get("/api/settings/ai")
    assert r.status_code == 200
    data = r.json()
    assert "default_provider" in data
    assert "gemini" in data
    assert "grok" in data
    r = client.post("/api/settings/test-key", json={"provider": "invalid", "api_key": "test"})
    assert r.status_code == 200
    assert r.json().get("status") == "error"


def test_reference_docs_and_errors():
    r = client.get("/api/reference-documents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/api/errors")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/api/errors/stats")
    assert r.status_code == 200
    assert "total_errors" in r.json()


def test_analyze_endpoint():
    mock_pipeline_res = {
        "step1": {"insight": "Test insight", "explanation": "Test insight"},
        "step2": {"applicable": False},
        "step3": {"score": 80, "verdict": "likely_true", "explanation": "Legit"},
        "step4": {"actions": ["Keep calm"]},
        "step5": {
            "tips": ["Tip 1"],
            "explanation": "Study hard",
            "learning_material": "Study hard",
            "source_links": [],
        },
    }
    with patch("usisain_backend.api.analyze.run_pipeline_blocking", return_value=mock_pipeline_res):
        resp = client.post(
            "/api/analyze", data={"text": "Test claim message", "provider": "ollama"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "scan_id" in data
        assert "step1" in data
        assert "step3" in data
        assert data["step1"]["insight"] == "Test insight"
        assert data["step3"]["verdict"] == "likely_true"


def test_analyze_stream_endpoint():

    async def mock_events(*args, **kwargs):
        yield StepEvent(1, "ai_insights", "completed", {"insight": "Stream insight"})

    with patch("usisain_backend.api.stream.run_pipeline", side_effect=mock_events):
        resp = client.post("/api/analyze/stream", data={"text": "Streaming test claim"})
        assert resp.status_code == 202
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: step" in body or "data:" in body

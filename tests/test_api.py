import pytest
from fastapi.testclient import TestClient

from scrip_core.api import create_app

TOKEN = "a" * 43


@pytest.fixture
def client(companion):
    with TestClient(create_app(companion, TOKEN), base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield client


def test_unauthenticated_requests_cannot_read_or_write(companion):
    with TestClient(create_app(companion, TOKEN), base_url="http://127.0.0.1") as client:
        for path in ("/v1/health", "/v1/inbox", "/v1/history"):
            assert client.get(path).status_code == 401
        assert client.post("/v1/events", json={}).status_code == 401


def test_input_ingestion_and_local_acknowledgement(client, input_event):
    response = client.post("/v1/events", json=input_event.model_dump(mode="json"))
    assert response.status_code == 200
    request_id = response.json()["request_id"]
    inbox = client.get("/v1/inbox").json()
    assert inbox["answer_forwarding_supported"] is False
    assert len(inbox["items"]) == 1
    answer = client.post(f"/v1/inbox/{request_id}/acknowledge", json={})
    assert answer.json()["answered_in_agent"] is False
    assert client.get("/v1/inbox").json()["items"] == []


def test_conflicting_event_id_is_http_409(client, tool_event):
    payload = tool_event.model_dump(mode="json")
    assert client.post("/v1/events", json=payload).status_code == 200
    payload["payload"]["arguments"]["CommandLine"] = "different command"
    assert client.post("/v1/events", json=payload).status_code == 409


def test_origin_host_size_and_schema_boundaries(client, tool_event):
    assert client.get("/v1/health", headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.get("/v1/health", headers={"Host": "evil.invalid"}).status_code == 400
    assert client.post("/v1/events", content=b"x" * (1024 * 1024 + 1)).status_code == 413
    payload = tool_event.model_dump(mode="json")
    payload["unexpected_policy_override"] = "allow"
    assert client.post("/v1/events", json=payload).status_code == 422
    assert client.get("/v1/history?limit=10000").status_code == 422
    assert client.get("/docs").status_code == 404

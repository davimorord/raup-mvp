"""Contract tests for MedGemmaClient, with HTTP mocked.

The contract itself (async /run + /status polling, sampling_params nesting,
output-as-a-list) was verified live against the real RunPod endpoint on
2026-09-23 (see D-017) — these tests pin that verified shape so a future
change to the client can't silently drift from it.
"""

import pytest

from raup.llm.medgemma_client import MedGemmaClient


class _FakeResponse:
    def __init__(self, json_body, status_code=200):
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_body


def _completed_body(content: str) -> dict:
    return {
        "status": "COMPLETED",
        "output": [{"choices": [{"message": {"content": content}}]}],
    }


def test_submits_to_run_with_sampling_params_nested(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse({"id": "job-123"})

    def fake_get(url, headers, timeout):
        return _FakeResponse(_completed_body("Hola"))

    monkeypatch.setattr("raup.llm.medgemma_client.requests.post", fake_post)
    monkeypatch.setattr("raup.llm.medgemma_client.requests.get", fake_get)

    client = MedGemmaClient(endpoint_id="ep-123", api_key="secret-key")
    result = client.complete("system rules", "user question")

    assert result == "Hola"
    assert captured["url"] == "https://api.runpod.ai/v2/ep-123/run"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    body_input = captured["json"]["input"]
    assert body_input["messages"][0] == {"role": "system", "content": "system rules"}
    assert body_input["messages"][1] == {"role": "user", "content": "user question"}
    assert "sampling_params" in body_input
    assert "max_tokens" not in body_input  # must be nested, not flat


def test_polls_status_until_completed(monkeypatch):
    statuses = iter(["IN_QUEUE", "IN_PROGRESS", "COMPLETED"])
    poll_count = {"n": 0}

    def fake_post(url, json, headers, timeout):
        return _FakeResponse({"id": "job-123"})

    def fake_get(url, headers, timeout):
        poll_count["n"] += 1
        status = next(statuses, "COMPLETED")
        if status == "COMPLETED":
            return _FakeResponse(_completed_body("Hola de nuevo"))
        return _FakeResponse({"status": status})

    monkeypatch.setattr("raup.llm.medgemma_client.requests.post", fake_post)
    monkeypatch.setattr("raup.llm.medgemma_client.requests.get", fake_get)
    monkeypatch.setattr("raup.llm.medgemma_client.time.sleep", lambda _: None)

    client = MedGemmaClient(endpoint_id="ep-123", api_key="secret-key")
    result = client.complete("s", "u")

    assert result == "Hola de nuevo"
    assert poll_count["n"] == 3


def test_raises_on_failed_status(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _FakeResponse({"id": "job-123"})

    def fake_get(url, headers, timeout):
        return _FakeResponse({"status": "FAILED", "error": "worker crashed"})

    monkeypatch.setattr("raup.llm.medgemma_client.requests.post", fake_post)
    monkeypatch.setattr("raup.llm.medgemma_client.requests.get", fake_get)

    client = MedGemmaClient(endpoint_id="ep-123", api_key="secret-key")
    with pytest.raises(RuntimeError, match="worker crashed"):
        client.complete("system rules", "user question")


def test_strips_whitespace_from_response(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _FakeResponse({"id": "job-123"})

    def fake_get(url, headers, timeout):
        return _FakeResponse(_completed_body("  Hola  \n"))

    monkeypatch.setattr("raup.llm.medgemma_client.requests.post", fake_post)
    monkeypatch.setattr("raup.llm.medgemma_client.requests.get", fake_get)

    client = MedGemmaClient(endpoint_id="ep-123", api_key="secret-key")
    assert client.complete("s", "u") == "Hola"


def test_raises_timeout_error_if_never_completes(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _FakeResponse({"id": "job-123"})

    def fake_get(url, headers, timeout):
        return _FakeResponse({"status": "IN_PROGRESS"})

    monkeypatch.setattr("raup.llm.medgemma_client.requests.post", fake_post)
    monkeypatch.setattr("raup.llm.medgemma_client.requests.get", fake_get)
    monkeypatch.setattr("raup.llm.medgemma_client.time.sleep", lambda _: None)
    # collapse the wait budget so the test doesn't actually take minutes
    monkeypatch.setattr("raup.llm.medgemma_client._MAX_WAIT_SECONDS", 0)

    client = MedGemmaClient(endpoint_id="ep-123", api_key="secret-key")
    with pytest.raises(TimeoutError):
        client.complete("s", "u")

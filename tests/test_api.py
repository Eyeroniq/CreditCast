"""Public API hardening (Phase 3.1 + 3.2): rate limits, strict validation,
and no stack traces leaking out of the scoring endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.api.main import app, limiter
from creditcast.config import load_config

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "governance_report.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)")

GOOD = dict(fico=690, dti=38.0, ltv=82, orig_interest_rate=4.3, orig_upb=300000,
            orig_loan_term=360, occupancy_status="P", loan_purpose="N",
            property_type="CO", first_time_homebuyer="Y", vintage="2021-06")


@pytest.fixture()
def client():
    limiter.reset()                      # each test starts with fresh buckets
    yield TestClient(app)
    limiter.reset()


# ---- 3.2 validation ------------------------------------------------------------
BAD_PAYLOADS = {
    "fico too low": {"fico": 100},
    "fico not a number": {"fico": "high"},
    "dti negative": {"dti": -1},
    "dti NaN": {"dti": "NaN"},
    "dti infinite": {"dti": "Infinity"},
    "ltv too high": {"ltv": 500},
    "rate too high": {"orig_interest_rate": 99},
    "loan amount huge": {"orig_upb": 50_000_000},
    "term too short": {"orig_loan_term": 12},
    "unknown occupancy code": {"occupancy_status": "X"},
    "unknown purpose code": {"loan_purpose": "refi"},
    "unknown property code": {"property_type": "castle"},
    "first-time buyer not Y/N": {"first_time_homebuyer": "maybe"},
    "bad vintage format": {"vintage": "June 2021"},
    "vintage month 13": {"vintage": "2021-13"},
    "unknown extra field": {"borrower_race": "White"},
}


@pytest.mark.parametrize("case", sorted(BAD_PAYLOADS))
def test_bad_applicant_is_422_not_500(client, case):
    r = client.post("/api/score", json={**GOOD, **BAD_PAYLOADS[case]})
    assert r.status_code == 422, r.text


def test_missing_field_is_422(client):
    payload = {k: v for k, v in GOOD.items() if k != "fico"}
    assert client.post("/api/score", json=payload).status_code == 422


def test_portfolio_n_is_bounded(client):
    assert client.get("/api/portfolio?n=0").status_code == 422
    assert client.get("/api/portfolio?n=1000001").status_code == 422


def test_question_length_is_bounded(client):
    cap = int(load_config().api.max_question_chars)
    assert client.post("/api/agent/chat", json={"question": ""}).status_code == 422
    r = client.post("/api/agent/chat", json={"question": "x" * (cap + 1)})
    assert r.status_code == 422


@needs_artifacts
def test_good_applicant_scores(client):
    r = client.post("/api/score", json=GOOD)
    assert r.status_code == 200
    assert r.json()["decision"] in {"approve", "decline"}
    assert r.headers.get("X-Request-ID")


@needs_artifacts
def test_unexpected_error_returns_request_id_not_traceback(client, monkeypatch):
    import app.api.main as api

    class Boom:
        def score(self, raw):
            raise RuntimeError("secret internals")

    monkeypatch.setattr(api, "bundle", lambda: Boom())
    r = client.post("/api/score", json=GOOD)
    assert r.status_code == 500
    body = r.json()["detail"]
    assert "request id" in body and "secret internals" not in body
    assert r.headers["X-Request-ID"] in body


# ---- 3.1 rate limits -----------------------------------------------------------
def _per_minute(limit: str) -> int:
    first = limit.split(";")[0]                     # e.g. "10/minute"
    return int(first.split("/")[0])


def test_copilot_rate_limit_returns_friendly_429(client, monkeypatch):
    # No LLM key -> each allowed call is a fast 503; the limiter still counts it.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    n = _per_minute(load_config().api.rate_limits.agent_chat)
    codes = [client.post("/api/agent/chat", json={"question": "Is the model fair?"}).status_code
             for _ in range(n)]
    assert 429 not in codes
    r = client.post("/api/agent/chat", json={"question": "Is the model fair?"})
    assert r.status_code == 429
    assert "try again" in r.json()["detail"]
    assert "Retry-After" in r.headers


def test_score_rate_limit(client, monkeypatch):
    # Invalid bodies are rejected before the limiter runs (cheap 422s), so use
    # valid requests against a stub model — no trained artifacts needed.
    import app.api.main as api

    class Stub:
        def score(self, raw):
            return {"decision": "approve"}

    monkeypatch.setattr(api, "bundle", lambda: Stub())
    n = _per_minute(load_config().api.rate_limits.score)
    for _ in range(n):
        assert client.post("/api/score", json=GOOD).status_code == 200
    r = client.post("/api/score", json=GOOD)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_health_is_not_rate_limited(client):
    assert all(client.get("/api/health").status_code == 200 for _ in range(150))

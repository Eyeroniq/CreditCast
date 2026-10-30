"""Public API hardening (Phase 3.1 + 3.2): rate limits, strict validation,
and no stack traces leaking out of the scoring endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, limiter
from creditcast.config import load_config

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "governance_report.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)

GOOD = dict(
    fico=690,
    dti=38.0,
    ltv=82,
    orig_interest_rate=4.3,
    orig_upb=300000,
    orig_loan_term=360,
    occupancy_status="P",
    loan_purpose="N",
    property_type="CO",
    first_time_homebuyer="Y",
    vintage="2021-06",
)


@pytest.fixture()
def client():
    limiter.reset()  # each test starts with fresh buckets
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
    first = limit.split(";")[0]  # e.g. "10/minute"
    return int(first.split("/")[0])


def test_copilot_rate_limit_returns_friendly_429(client, monkeypatch):
    # No LLM key -> each allowed call is a fast 503; the limiter still counts it.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    n = _per_minute(load_config().api.rate_limits.agent_chat)
    codes = [
        client.post("/api/agent/chat", json={"question": "Is the model fair?"}).status_code
        for _ in range(n)
    ]
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


# ---- 3.3 CORS + optional API key ------------------------------------------------
def test_cors_is_same_origin_only_by_default(client):
    from app.api.main import ALLOWED_ORIGINS

    if ALLOWED_ORIGINS:
        pytest.skip("CC_ALLOWED_ORIGINS is set in this environment")
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_parsing():
    from app.api.main import cors_origins

    assert cors_origins(None) == []
    assert cors_origins(" https://dhyyraj.in/ , http://localhost:3000 ,") == [
        "https://dhyyraj.in",
        "http://localhost:3000",
    ]


class _StubBundle:
    model_version = {"code_version": "test", "fingerprint": "abc123def456"}

    def score(self, raw):
        return {
            "decision": "decline",
            "pd": 0.2,
            "risk_band": "B",
            "threshold": 0.0625,
            "reason_codes": [{"feature": "fico"}, {"feature": "dti"}],
        }


def test_api_key_enforced_only_when_configured(client, monkeypatch):
    import app.api.main as api

    monkeypatch.setattr(api, "bundle", lambda: _StubBundle())
    monkeypatch.delenv("CC_API_KEY", raising=False)
    assert client.post("/api/score", json=GOOD).status_code == 200  # open demo
    monkeypatch.setenv("CC_API_KEY", "s3cret")
    assert client.post("/api/score", json=GOOD).status_code == 401
    assert client.post("/api/score", json=GOOD, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/api/score", json=GOOD, headers={"X-API-Key": "s3cret"}).status_code == 200


# ---- 3.4 decision audit trail ---------------------------------------------------
def test_score_writes_traceable_audit_record(client, monkeypatch):
    import logging

    import app.api.main as api
    from app.api.audit import input_hash

    monkeypatch.setattr(api, "bundle", lambda: _StubBundle())
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.msg)

    h = Capture()
    logging.getLogger("creditcast.decisions").addHandler(h)
    try:
        r = client.post("/api/score", json=GOOD)
    finally:
        logging.getLogger("creditcast.decisions").removeHandler(h)
    assert r.status_code == 200
    (rec,) = records
    assert rec["request_id"] == r.headers["X-Request-ID"] == r.json()["request_id"]
    assert rec["model_version"]["fingerprint"] == "abc123def456"
    assert rec["input_hash"] == input_hash(api.Applicant(**GOOD).model_dump())
    assert rec["decision"] == "decline" and rec["reason_features"] == ["fico", "dti"]
    assert rec["latency_ms"] >= 0
    assert "fico" not in rec and 690 not in rec.values()  # no raw inputs logged


def test_input_hash_is_order_independent():
    from app.api.audit import input_hash

    a = {"fico": 690, "dti": 38.0}
    assert input_hash(a) == input_hash(dict(reversed(list(a.items()))))
    assert input_hash(a) != input_hash({**a, "fico": 691})


# ---- 3.5 readiness ----------------------------------------------------------------
@needs_artifacts
def test_ready_reports_model_version(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True
    assert len(r.json()["model_version"]["fingerprint"]) == 12


def test_ready_is_503_when_an_artifact_is_missing(client, monkeypatch, tmp_path):
    import copy

    import app.api.main as api
    from creditcast.config import Config
    from creditcast.serving import ModelBundle

    cfg = Config(copy.deepcopy(dict(load_config())))
    cfg["paths"] = {**cfg["paths"], "artifacts": str(tmp_path)}  # empty dir
    monkeypatch.setattr(api, "bundle", lambda: ModelBundle(cfg))
    r = client.get("/api/ready")
    assert r.status_code == 503
    assert "artifacts/challenger.joblib" in r.json()["missing"]
    assert client.get("/api/health").status_code == 200  # still alive


# ---- 6.2.2 what-if endpoint --------------------------------------------------------
@needs_artifacts
def test_whatif_endpoint(client):
    high = {
        **GOOD,
        "fico": 645,
        "dti": 47.0,
        "ltv": 94,
        "orig_interest_rate": 5.6,
        "orig_upb": 360000,
        "occupancy_status": "I",
        "loan_purpose": "C",
        "property_type": "MH",
    }
    for payload in (GOOD, high):
        r = client.post("/api/whatif", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert {"already_approved", "options", "threshold"} <= body.keys()
        assert body["already_approved"] or body["options"] or body["message"]


def test_whatif_validates_input(client):
    assert client.post("/api/whatif", json={**GOOD, "dti": -5}).status_code == 422


# ---- 6.2.8 streamed Copilot answers ---------------------------------------------
def _sse(r):
    import json as _json

    return [_json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]


def test_stream_without_llm_key_is_a_plain_503(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = client.post("/api/agent/chat/stream", json={"question": "Is the model fair?"})
    assert r.status_code == 503
    assert "GROQ_API_KEY" in r.json()["detail"]


def test_stream_sends_progress_events_then_done(client, monkeypatch):
    from creditcast.agents import orchestrator

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    events = [
        {"type": "plan", "agents": [{"specialist": "fairness", "title": "Fairness Auditor"}]},
        {"type": "agent_start", "specialist": "fairness", "title": "Fairness Auditor"},
        {
            "type": "agent_done",
            "specialist": "fairness",
            "title": "Fairness Auditor",
            "text": "Approval ratio 0.80.",
            "charts": [],
            "trace": [],
        },
        {"type": "done", "answer": "Approval ratio 0.80.", "charts": [], "trace": [], "agents": []},
    ]
    monkeypatch.setattr(orchestrator, "run_events", lambda q: iter(events))
    r = client.post("/api/agent/chat/stream", json={"question": "Is the model fair?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert _sse(r) == events


def test_stream_failure_mid_answer_is_an_error_event_with_request_id(client, monkeypatch):
    from creditcast.agents import orchestrator

    def broken(q):
        yield {"type": "plan", "agents": []}
        raise RuntimeError("tool exploded")

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(orchestrator, "run_events", broken)
    got = _sse(client.post("/api/agent/chat/stream", json={"question": "Is the model fair?"}))
    assert [e["type"] for e in got] == ["plan", "error"]
    assert "request id" in got[1]["detail"] and "exploded" not in got[1]["detail"]


def test_stream_question_length_is_bounded(client):
    assert client.post("/api/agent/chat/stream", json={"question": ""}).status_code == 422


# ---- 5.2 stress testing -----------------------------------------------------------
@pytest.mark.parametrize(
    "body",
    [
        {"unemployment_pts": 99, "hpi_change_pct": 0},
        {"unemployment_pts": 3, "hpi_change_pct": -80},
        {"unemployment_pts": 3},
        {"unemployment_pts": 3, "hpi_change_pct": -10, "rates": 2},
    ],
)
def test_stress_shock_is_validated(client, body):
    assert client.post("/api/stress", json=body).status_code == 422


@needs_artifacts
def test_stress_custom_scenario_runs(client):
    r = client.post("/api/stress", json={"unemployment_pts": 4, "hpi_change_pct": -15})
    assert r.status_code == 200
    body = r.json()
    assert body["unemployment_pts"] == 4 and body["el_bps"] > 0
    base = client.get("/api/stress").json()["scenarios"]["baseline"]
    assert body["expected_loss"] > base["expected_loss"]


# ---- 5.5 regulatory capital ----------------------------------------------------------
@needs_artifacts
def test_capital_is_reported_next_to_expected_loss(client):
    s = client.post("/api/score", json=GOOD).json()
    assert s["capital"] > 0 and 0 < s["risk_weight"] < 12.5
    p = client.get("/api/portfolio?n=5").json()
    assert p["capital"] > p["portfolio_el"] > 0  # unexpected loss dwarfs the average
    assert p["rwa"] == pytest.approx(12.5 * p["capital"])
    assert sum(p["capital_by_band"].values()) == pytest.approx(p["capital"], rel=1e-6)
    assert all("capital" in row for row in p["sample"])


# ---- 5.3 lifetime PD and IFRS 9 -------------------------------------------------------
@needs_artifacts
def test_lifetime_and_stages_reach_the_portfolio(client):
    r = client.get("/api/lifetime").json()
    assert {s["stage"] for s in r["staging"]["stages"]} == {1, 2, 3}
    rows = client.get("/api/portfolio?n=200").json()["sample"]
    assert all(row["pd_lifetime"] >= row["pd_champion"] - 1e-9 for row in rows)
    assert {row["ifrs9_stage"] for row in rows} <= {1, 2, 3, None}

"""CreditCast scoring API (FastAPI).

Serves single-applicant scoring (PD/LGD/EL + decision + reason codes) and the
precomputed report artifacts under `/api/*`, and (when present) the pre-built
static Next.js Risk Cockpit at `/` — so the whole app runs as one container at
one origin (no CORS).

Public-facing hardening: per-IP rate limits (slowapi) on the costly endpoints,
strict input validation (unknown fields, out-of-range values and unknown
category codes are 422s), and unexpected errors return a request ID instead of
a stack trace. Limits live in `config.yaml` under `api`.

Production settings (environment variables, all optional):
  CC_ALLOWED_ORIGINS  comma-separated origins allowed to call the API from a
                      browser (CORS). Unset = same-origin only (the cockpit).
  CC_API_KEY          if set, POST /api/score and /api/agent/chat require the
                      header `X-API-Key: <key>` (API-only deployments; leave
                      unset when the public cockpit must work).
  CC_LOG_DIR          where `decisions.jsonl` (the audit trail) is written.

Run locally:

    uvicorn app.api.main:app --reload --port 8001
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import audit
from creditcast.config import load_config
from creditcast.governance import decision
from creditcast.models import capital
from creditcast.serving import ModelBundle

decision_log = audit.setup_logging()
log = logging.getLogger("creditcast.api")
API_CFG = load_config().api
LIMITS = API_CFG.rate_limits


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Apply a pinned model version (rollback), then warm the model bundle so the
    first visitor isn't slow. Failures are logged, not fatal: /api/ready then
    reports 503 (unhealthy)."""
    pinned = (load_config().get("serving") or {}).get("pinned_version")
    if pinned:
        from creditcast.registry import activate, active_version

        try:
            if active_version() != pinned:
                activate(pinned)
                log.info({"event": "model_version_pinned", "version": pinned})
        except Exception:
            log.exception("could not activate pinned model version %s", pinned)
    try:
        bundle().warm()
        log.info({"event": "startup", "model_version": bundle().model_version})
    except Exception:
        log.exception("model warm-up failed; /api/ready will report unhealthy")
    yield


app = FastAPI(title="CreditCast Scoring API", version="0.1.0", lifespan=_lifespan)


# CORS: same-origin only by default (the cockpit is served by this app). Allow
# extra browser origins explicitly, e.g. a split local dev server.
def cors_origins(raw: str | None) -> list[str]:
    """Parse CC_ALLOWED_ORIGINS ("https://a.com, http://localhost:3000")."""
    return [o.strip().rstrip("/") for o in (raw or "").split(",") if o.strip()]


ALLOWED_ORIGINS = cors_origins(os.environ.get("CC_ALLOWED_ORIGINS"))
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "x-api-key"],
    )


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional shared-secret check, active only when CC_API_KEY is set."""
    expected = os.environ.get("CC_API_KEY")
    if expected and not (x_api_key and hmac.compare_digest(x_api_key, expected)):
        raise HTTPException(401, "Missing or invalid API key (send header X-API-Key).")


# Per-client-IP rate limits (in-memory: one container, one process).
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def _rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Friendly 429 the cockpit can show as-is (`detail`), plus Retry-After."""
    try:
        retry_after = int(exc.limit.limit.get_expiry())  # window length, seconds
    except AttributeError:
        retry_after = 60
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={
            "detail": "You're sending requests quickly — please try again "
            f"in a minute (limit: {exc.detail}).",
            "limit": str(exc.detail),
        },
    )


@app.middleware("http")
async def _request_id(request: Request, call_next):
    """Tag every request with an ID (echoed in X-Request-ID and in 500s)."""
    request.state.request_id = uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def _internal_error(request: Request, what: str) -> HTTPException:
    rid = getattr(request.state, "request_id", "-")
    log.exception("%s failed (request_id=%s)", what, rid)
    return HTTPException(500, f"Internal error while {what} (request id {rid}).")


# All API endpoints live under /api so they never collide with the static
# cockpit routes (e.g. the page /validation vs the endpoint /api/validation).
router = APIRouter(prefix="/api")


@lru_cache(maxsize=1)
def bundle() -> ModelBundle:
    return ModelBundle()


def _artifact(name: str) -> dict:
    cfg = load_config()
    path = cfg.path("artifacts") / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found — run the pipeline first")
    return json.loads(path.read_text())


class Applicant(BaseModel):
    """One mortgage application. Ranges mirror the Silver data-quality gate;
    category codes are the ones the models were trained on."""

    model_config = ConfigDict(extra="forbid")

    fico: int = Field(ge=300, le=850, examples=[680])
    dti: float = Field(ge=0, le=70, allow_inf_nan=False, examples=[42.0])
    ltv: int = Field(ge=1, le=125, examples=[88])
    orig_interest_rate: float = Field(ge=0, le=25, allow_inf_nan=False, examples=[4.5])
    orig_upb: int = Field(ge=1_000, le=5_000_000, examples=[280000])
    orig_loan_term: int = Field(ge=60, le=480, examples=[360])
    occupancy_status: Literal["P", "I", "S"] = Field(examples=["I"])
    loan_purpose: Literal["P", "C", "N"] = Field(examples=["C"])
    property_type: Literal["SF", "CO", "PU", "MH"] = Field(examples=["SF"])
    first_time_homebuyer: Literal["Y", "N"] = Field(examples=["N"])
    vintage: str | None = Field(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2021-06"]
    )
    # Only used to look up local economic conditions (5.1), never as a model
    # input. Unknown or missing -> national figures.
    property_state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$", examples=["TX"])


@router.get("/health")
def health():
    """Liveness: the process is up (does not load the models), plus which
    registered model version is being served."""
    from creditcast.config import git_sha
    from creditcast.registry import active_version

    return {
        "status": "ok",
        "stamp": load_config()["run"],
        "git_sha": git_sha(),
        "model_version": active_version(),
    }


@router.get("/ready")
def ready():
    """Readiness: every required artifact exists and loads. Used by the Docker
    HEALTHCHECK, so a missing/broken model marks the container unhealthy."""
    b = bundle()
    missing = b.missing_artifacts()
    if missing:
        return JSONResponse(status_code=503, content={"ready": False, "missing": missing})
    try:
        b.warm()
    except Exception as exc:
        log.exception("readiness check failed")
        return JSONResponse(status_code=503, content={"ready": False, "error": type(exc).__name__})
    return {"ready": True, "model_version": b.model_version}


@router.post("/score", dependencies=[Depends(require_api_key)])
@limiter.limit(LIMITS.score)
def score(request: Request, applicant: Applicant):
    started = time.perf_counter()
    raw = applicant.model_dump()
    b = bundle()
    try:
        result = b.score(raw)
    except KeyError as e:
        raise HTTPException(422, f"missing feature: {e}") from e
    except Exception as e:
        raise _internal_error(request, "scoring") from e
    # Audit trail: model version + input hash, never the raw inputs.
    version = getattr(b, "model_version", {}) or {}
    decision_log.info(
        audit.decision_record(
            request_id=request.state.request_id,
            model_version=version,
            applicant=raw,
            result=result,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
    )
    return {
        **result,
        "request_id": request.state.request_id,
        "model_fingerprint": version.get("fingerprint"),
    }


@router.post("/whatif", dependencies=[Depends(require_api_key)])
@limiter.limit(LIMITS.whatif)
def whatif(request: Request, applicant: Applicant):
    """Smallest single changes that would turn a decline into an approval."""
    from creditcast.governance.counterfactual import what_if

    b = bundle()
    try:
        return what_if(applicant.model_dump(), b.pd_batch, b.threshold)
    except Exception as e:
        raise _internal_error(request, "searching for changes") from e


@router.get("/validation")
def validation():
    return _artifact("validation_report.json")


@router.get("/governance")
def governance():
    return _artifact("governance_report.json")


# ---- Stress testing (5.2) ---------------------------------------------------
_STRESS_LIMITS = load_config().stress.limits


class StressShock(BaseModel):
    """A custom macro scenario on top of each loan's actual conditions."""

    model_config = ConfigDict(extra="forbid")

    unemployment_pts: float = Field(
        ge=_STRESS_LIMITS.unemployment_pts[0],
        le=_STRESS_LIMITS.unemployment_pts[1],
        allow_inf_nan=False,
        examples=[4.0],
    )
    hpi_change_pct: float = Field(
        ge=_STRESS_LIMITS.hpi_change_pct[0],
        le=_STRESS_LIMITS.hpi_change_pct[1],
        allow_inf_nan=False,
        examples=[-15.0],
    )


@router.get("/lifetime")
def lifetime_report():
    """Lifetime PD hazard, back-tests and IFRS 9 staging of the out-of-time book."""
    return _artifact("lifetime_report.json")


@router.get("/stress")
def stress_scenarios():
    """Baseline / adverse / severely adverse results, precomputed by the pipeline."""
    return _artifact("stress_report.json")


@router.post("/stress", dependencies=[Depends(require_api_key)])
@limiter.limit(LIMITS.stress)
def stress_custom(request: Request, shock: StressShock):
    """Re-run the stress test for a custom shock."""
    from creditcast.stress import engine

    try:
        return engine().run(shock.unemployment_pts, shock.hpi_change_pct)
    except Exception as e:
        raise _internal_error(request, "running the stress test") from e


@router.get("/threshold-curve")
def threshold_curve():
    """Approval rate / expected loss / fairness at every candidate cut-off."""
    return _artifact("threshold_curve.json")


@router.get("/monitoring")
def monitoring():
    return _artifact("monitoring_report.json")


@router.get("/shap/global")
def shap_global():
    return _artifact("shap_global.json")


@router.get("/portfolio")
@limiter.limit(LIMITS.portfolio)
def portfolio(request: Request, n: int = Query(500, ge=1, le=int(API_CFG.portfolio_max_rows))):
    """Portfolio risk view: aggregates + a sample of scored loans for the UI."""
    cfg = load_config()
    scored = pd.read_parquet(cfg.path("artifacts") / "test_scored.parquet")
    thr = bundle().threshold
    bands = decision.assign_band(scored["credit_score"].to_numpy(), cfg)
    scored = scored.assign(
        risk_band=bands, decision=decision.decide(scored["pd_champion"].to_numpy(), thr)
    )
    cap = capital.irb(scored["pd_champion"], scored["lgd_hat"], scored["ead"], cfg)
    scored = scored.assign(capital=cap["capital"])
    # Lifetime PD and IFRS 9 stage per loan (5.3), when the step has run
    life_path = cfg.path("artifacts") / "lifetime_scored.parquet"
    if life_path.exists():
        life = pd.read_parquet(life_path)[["loan_id", "pd_lifetime", "ifrs9_stage"]]
        scored = scored.merge(life, on="loan_id", how="left")
        # loans already repaid or written off have no stage: null, not NaN
        stage = scored["ifrs9_stage"]
        scored["ifrs9_stage"] = stage.astype(object).where(stage.notna(), None)
        scored.loc[stage.notna(), "ifrs9_stage"] = stage[stage.notna()].astype(int)
    band_order = [b["name"] for b in cfg.decision.bands]
    band_dist = (
        scored["risk_band"].value_counts().reindex(band_order).fillna(0).astype(int).to_dict()
    )
    el_by_band = (
        scored.groupby("risk_band")["expected_loss"]
        .sum()
        .reindex(band_order)
        .fillna(0)
        .round(2)
        .to_dict()
    )
    sample_cols = [
        "loan_id",
        "vintage",
        "pd_champion",
        "credit_score",
        "risk_band",
        "lgd_hat",
        "ead",
        "expected_loss",
        "capital",
        "decision",
        "default_12m",
    ]
    sample_cols += [c for c in ("pd_lifetime", "ifrs9_stage") if c in scored]
    return {
        "n_loans": int(len(scored)),
        "portfolio_el": float(scored["expected_loss"].sum()),
        "total_ead": float(scored["ead"].sum()),
        "el_rate_bps": float(scored["expected_loss"].sum() / scored["ead"].sum() * 1e4),
        "mean_pd": float(scored["pd_champion"].mean()),
        "approval_rate": float((scored["decision"] == "approve").mean()),
        "band_distribution": band_dist,
        "el_by_band": el_by_band,
        # Basel IRB (5.5): capital for unexpected loss, next to EL
        "capital": cap["total"]["capital"],
        "rwa": cap["total"]["rwa"],
        "risk_weight": cap["total"]["risk_weight"],
        "capital_by_band": scored.groupby("risk_band")["capital"]
        .sum()
        .reindex(band_order)
        .fillna(0)
        .round(2)
        .to_dict(),
        "pd_histogram": _histogram(scored["pd_champion"], 25),
        "sample": scored.sort_values("expected_loss", ascending=False)
        .head(n)[sample_cols]
        .to_dict(orient="records"),
    }


def _histogram(series: pd.Series, bins: int) -> list[dict]:
    counts, edges = pd.cut(series, bins=bins, retbins=True)
    vc = counts.value_counts(sort=False)
    return [{"x": round(float(edges[i]), 4), "count": int(vc.iloc[i])} for i in range(len(vc))]


# ---- Risk Copilot (agent layer) -------------------------------------------
class AgentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=int(API_CFG.max_question_chars),
        examples=["Why is the 2021 vintage riskier, and is the model fair?"],
    )


@router.get("/agent/team")
def agent_team():
    """The specialist roster shown in the Copilot UI."""
    from creditcast.agents.specialists import SPECIALISTS

    return {
        "llm_ready": bool(os.environ.get("GROQ_API_KEY")),
        "model": load_config().agents.model,
        "agents": [
            {"id": k, "title": v["title"], "tools": v["tools"]} for k, v in SPECIALISTS.items()
        ],
    }


@router.post("/agent/chat", dependencies=[Depends(require_api_key)])
@limiter.limit(LIMITS.agent_chat)
def agent_chat(request: Request, q: AgentQuery):
    """Route the question to the specialist team and return answer + charts + trace."""
    from creditcast.agents import orchestrator
    from creditcast.agents.llm import LLMNotConfigured

    try:
        return orchestrator.run(q.question)
    except LLMNotConfigured as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise _internal_error(request, "answering") from e


@router.post("/agent/chat/stream", dependencies=[Depends(require_api_key)])
@limiter.limit(LIMITS.agent_chat)
def agent_chat_stream(request: Request, q: AgentQuery):
    """Same as /agent/chat, streamed as server-sent events (6.2.8): `plan`,
    then `agent_start` / `agent_done` per specialist, then `done` (the full
    result) — or a single `error` event if something fails mid-answer."""
    from creditcast.agents import llm, orchestrator
    from creditcast.agents.llm import LLMNotConfigured

    try:
        llm.ensure_configured()  # a missing key is a plain 503, before streaming starts
    except LLMNotConfigured as e:
        raise HTTPException(503, str(e)) from e

    def events():
        try:
            for ev in orchestrator.run_events(q.question):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception:
            err = _internal_error(request, "answering")
            yield f"data: {json.dumps({'type': 'error', 'detail': err.detail})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # no proxy buffering (Caddy/nginx), so each event reaches the browser at once
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Register the API, then (in the container) serve the static Next.js export at /.
app.include_router(router)

_STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
if Path(_STATIC_DIR).is_dir():
    # html=True serves index.html for directory routes (/, /portfolio/, …),
    # matching Next's static export with trailingSlash. Mounted last so it
    # never shadows the /api routes above.
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="cockpit")

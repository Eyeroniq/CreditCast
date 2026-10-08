"""CreditCast scoring API (FastAPI).

Serves single-applicant scoring (PD/LGD/EL + decision + reason codes) and the
precomputed report artifacts under `/api/*`, and (when present) the pre-built
static Next.js Risk Cockpit at `/` — so the whole app runs as one container at
one origin (no CORS).

Public-facing hardening: per-IP rate limits (slowapi) on the costly endpoints,
strict input validation (unknown fields, out-of-range values and unknown
category codes are 422s), and unexpected errors return a request ID instead of
a stack trace. Limits live in `config.yaml` under `api`. Run locally:

    uvicorn app.api.main:app --reload --port 8001
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from creditcast.config import load_config
from creditcast.governance import decision
from creditcast.serving import ModelBundle

log = logging.getLogger("creditcast.api")
API_CFG = load_config().api
LIMITS = API_CFG.rate_limits

app = FastAPI(title="CreditCast Scoring API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Per-client-IP rate limits (in-memory: one container, one process).
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def _rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Friendly 429 the cockpit can show as-is (`detail`), plus Retry-After."""
    try:
        retry_after = int(exc.limit.limit.get_expiry())   # window length, seconds
    except AttributeError:
        retry_after = 60
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={"detail": "You're sending requests quickly — please try again "
                           f"in a minute (limit: {exc.detail}).",
                 "limit": str(exc.detail)})


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
    vintage: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                                examples=["2021-06"])


@router.get("/health")
def health():
    return {"status": "ok", "stamp": load_config()["run"]}


@router.post("/score")
@limiter.limit(LIMITS.score)
def score(request: Request, applicant: Applicant):
    try:
        return bundle().score(applicant.model_dump())
    except KeyError as e:
        raise HTTPException(422, f"missing feature: {e}")
    except Exception:
        raise _internal_error(request, "scoring")


@router.get("/validation")
def validation():
    return _artifact("validation_report.json")


@router.get("/governance")
def governance():
    return _artifact("governance_report.json")


@router.get("/monitoring")
def monitoring():
    return _artifact("monitoring_report.json")


@router.get("/shap/global")
def shap_global():
    return _artifact("shap_global.json")


@router.get("/portfolio")
@limiter.limit(LIMITS.portfolio)
def portfolio(request: Request,
              n: int = Query(500, ge=1, le=int(API_CFG.portfolio_max_rows))):
    """Portfolio risk view: aggregates + a sample of scored loans for the UI."""
    cfg = load_config()
    scored = pd.read_parquet(cfg.path("artifacts") / "test_scored.parquet")
    thr = bundle().threshold
    bands = decision.assign_band(scored["credit_score"].to_numpy(), cfg)
    scored = scored.assign(risk_band=bands,
                           decision=decision.decide(scored["pd_champion"].to_numpy(), thr))
    band_order = [b["name"] for b in cfg.decision.bands]
    band_dist = (scored["risk_band"].value_counts().reindex(band_order).fillna(0)
                 .astype(int).to_dict())
    el_by_band = (scored.groupby("risk_band")["expected_loss"].sum()
                  .reindex(band_order).fillna(0).round(2).to_dict())
    sample_cols = ["loan_id", "vintage", "pd_champion", "credit_score",
                   "risk_band", "lgd_hat", "ead", "expected_loss", "decision",
                   "default_12m"]
    return {
        "n_loans": int(len(scored)),
        "portfolio_el": float(scored["expected_loss"].sum()),
        "total_ead": float(scored["ead"].sum()),
        "el_rate_bps": float(scored["expected_loss"].sum() / scored["ead"].sum() * 1e4),
        "mean_pd": float(scored["pd_champion"].mean()),
        "approval_rate": float((scored["decision"] == "approve").mean()),
        "band_distribution": band_dist,
        "el_by_band": el_by_band,
        "pd_histogram": _histogram(scored["pd_champion"], 25),
        "sample": scored.sort_values("expected_loss", ascending=False)
                        .head(n)[sample_cols].to_dict(orient="records"),
    }


def _histogram(series: pd.Series, bins: int) -> list[dict]:
    counts, edges = pd.cut(series, bins=bins, retbins=True)
    vc = counts.value_counts(sort=False)
    return [{"x": round(float(edges[i]), 4), "count": int(vc.iloc[i])}
            for i in range(len(vc))]


# ---- Risk Copilot (agent layer) -------------------------------------------
class AgentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=int(API_CFG.max_question_chars),
                          examples=["Why is the 2021 vintage riskier, and is the model fair?"])


@router.get("/agent/team")
def agent_team():
    """The specialist roster shown in the Copilot UI."""
    from creditcast.agents.specialists import SPECIALISTS
    return {"llm_ready": bool(os.environ.get("GROQ_API_KEY")),
            "model": load_config().agents.model,
            "agents": [{"id": k, "title": v["title"],
                        "tools": v["tools"]} for k, v in SPECIALISTS.items()]}


@router.post("/agent/chat")
@limiter.limit(LIMITS.agent_chat)
def agent_chat(request: Request, q: AgentQuery):
    """Route the question to the specialist team and return answer + charts + trace."""
    from creditcast.agents import orchestrator
    from creditcast.agents.llm import LLMNotConfigured
    try:
        return orchestrator.run(q.question)
    except LLMNotConfigured as e:
        raise HTTPException(503, str(e))
    except Exception:
        raise _internal_error(request, "answering")


# Register the API, then (in the container) serve the static Next.js export at /.
app.include_router(router)

_STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
if Path(_STATIC_DIR).is_dir():
    # html=True serves index.html for directory routes (/, /portfolio/, …),
    # matching Next's static export with trailingSlash. Mounted last so it
    # never shadows the /api routes above.
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="cockpit")

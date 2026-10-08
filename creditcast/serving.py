"""Serving bundle — load every artifact once and score one applicant end-to-end.

Encapsulates the production scoring path: build the leakage-safe features from
raw inputs (the same `creditcast.features.engineer` the pipeline uses), run
scorecard + challenger, calibrate, pick the configured champion, scale to a
credit score and risk band, predict LGD/EAD, compute Expected Loss, apply the
cost-based decision, and attach champion-consistent adverse-action reason
codes. Used by the FastAPI service.
"""
from __future__ import annotations

import hashlib
import json
from functools import cached_property

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import (categorical_columns, feature_columns,
                                 numeric_columns)
from creditcast.features import engineer
from creditcast.governance import decision, explain, reason_codes, shap_explain
from creditcast.models import calibration, challenger, ead as ead_mod
from creditcast.models import el as el_mod, lgd as lgd_mod, scorecard


# Files the scoring service needs: (config path key, file name).
REQUIRED_ARTIFACTS = [
    ("artifacts", "scorecard.joblib"),
    ("artifacts", "challenger.joblib"),
    ("artifacts", "calibrator_scorecard.joblib"),
    ("artifacts", "calibrator_challenger.joblib"),
    ("artifacts", "lgd.joblib"),
    ("artifacts", "governance_report.json"),
    ("artifacts", "test_scored.parquet"),
    ("gold", "feature_manifest.json"),
    ("gold", "rate_benchmark.parquet"),
]
# The model files whose bytes define "which model made this decision".
_FINGERPRINTED = ["scorecard.joblib", "challenger.joblib", "calibrator_scorecard.joblib",
                  "calibrator_challenger.joblib", "lgd.joblib"]


class ModelBundle:
    """Lazily loads all trained artifacts and serves single-applicant scoring."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()

    # ---- readiness ----------------------------------------------------------
    def missing_artifacts(self) -> list[str]:
        """Required files that are not on disk (checked on every call)."""
        return [f"{key}/{name}" for key, name in REQUIRED_ARTIFACTS
                if not (self.cfg.path(key) / name).exists()]

    def warm(self) -> None:
        """Load every artifact now, so the first real request isn't slow and a
        broken artifact fails readiness instead of a user's request."""
        for prop in ("scorecard", "challenger", "cal_sc", "cal_ch", "lgd",
                     "explainer", "threshold", "rate_benchmark", "model_version"):
            getattr(self, prop)

    @cached_property
    def model_version(self) -> dict:
        """Run stamp + champion + a fingerprint of the model files' bytes."""
        h = hashlib.sha256()
        for name in _FINGERPRINTED:
            h.update((self.cfg.path("artifacts") / name).read_bytes())
        return {**run_stamp(), "champion": str(self.cfg.decision.champion),
                "fingerprint": h.hexdigest()[:12]}

    @cached_property
    def scorecard(self):
        return scorecard.load(self.cfg)

    @cached_property
    def challenger(self):
        return challenger.load(self.cfg)

    @cached_property
    def cal_sc(self):
        return calibration.load("scorecard", self.cfg)

    @cached_property
    def cal_ch(self):
        return calibration.load("challenger", self.cfg)

    @cached_property
    def lgd(self):
        return lgd_mod.load(self.cfg)

    @cached_property
    def explainer(self):
        return shap_explain.build_explainer(self.challenger, self.cfg)

    @cached_property
    def threshold(self) -> float:
        gov = json.loads((self.cfg.path("artifacts") / "governance_report.json").read_text())
        return float(gov["decision"]["threshold"])

    @cached_property
    def rate_benchmark(self) -> pd.DataFrame:
        """Point-in-time rate benchmark table persisted by the Gold build."""
        return pd.read_parquet(self.cfg.path("gold") / "rate_benchmark.parquet")

    # ---- feature engineering: the SAME function the Gold pipeline uses --------
    def _build_features(self, raw: dict | list[dict]) -> pd.DataFrame:
        rows = [dict(r) for r in (raw if isinstance(raw, list) else [raw])]
        for r in rows:
            r.setdefault("vintage", None)
        df = engineer(pd.DataFrame(rows), self.rate_benchmark)
        df = df[feature_columns()].copy()
        for c in categorical_columns():
            df[c] = df[c].astype("category")
        for c in numeric_columns():
            df[c] = pd.to_numeric(df[c])
        return df

    def pd_batch(self, rows: list[dict]) -> np.ndarray:
        """Champion calibrated PDs for many applicants at once (no SHAP) —
        the fast path used by the what-if search."""
        X = self._build_features(rows)
        if str(self.cfg.decision.champion) == "scorecard":
            raw = self.scorecard.predict_proba(X)[:, 1]
            return self.cal_sc.transform(raw)
        return self.cal_ch.transform(challenger.predict_pd(self.challenger, X))

    def score(self, raw: dict) -> dict:
        X = self._build_features(raw)

        pd_sc = float(self.cal_sc.transform(self.scorecard.predict_proba(X)[:, 1])[0])
        pd_ch = float(self.cal_ch.transform(challenger.predict_pd(self.challenger, X))[0])
        credit_score = float(self.scorecard.score(X)[0])
        band = str(decision.assign_band(credit_score, self.cfg))

        # The champion drives EL, the decision AND the reasons (consistency).
        champion = str(self.cfg.decision.champion)
        pd_champ = pd_sc if champion == "scorecard" else pd_ch

        lgd_hat = float(self.lgd.predict(X)[0])
        ead = float(ead_mod.estimate_ead(X, self.cfg)[0])
        el = float(el_mod.expected_loss(pd_champ, lgd_hat, ead))

        dec = str(decision.decide(pd_champ, self.threshold))
        local = explain.local_drivers(
            X, self.cfg, scorecard=self.scorecard,
            explainer=self.explainer if champion == "challenger" else None)
        codes = reason_codes.reason_codes(local, top_n=4)

        return {
            "pd_scorecard": pd_sc,
            "pd_challenger": pd_ch,
            "pd": pd_champ,
            "champion": champion,
            "credit_score": round(credit_score, 1),
            "risk_band": band,
            "lgd": round(lgd_hat, 4),
            "ead": round(ead, 2),
            "expected_loss": round(el, 2),
            "decision": dec,
            "threshold": self.threshold,
            "reason_codes": codes if dec == "decline" else [],
            "explanation": [
                {"feature": t.feature, "value": str(t.value), "shap": round(float(t.shap), 4)}
                for t in local.itertuples(index=False)
            ],
            "adverse_action_letter": reason_codes.narrate(codes, dec),
        }

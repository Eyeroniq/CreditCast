"""Macro stress testing (ROADMAP 5.2).

A scenario shifts the economy: local unemployment up by `unemployment_pts`
points and house prices by `hpi_change_pct` percent. The out-of-time
portfolio is re-scored under it and the report shows expected loss, PD by risk
band and the approval rate per scenario.

Two channels move PD, because the champion alone can't carry a severe shock:

1. **Re-scoring.** The champion sees the shocked macro features. A tree model is
   flat beyond the conditions in its training years (2015–2019 were calm), so
   this channel stops responding exactly where a recession starts.
2. **Satellite sensitivity.** A small logistic model, fitted on every labelled
   vintage (2015–2021, including the 2020 shock), measures how default rates
   moved with the macro features *on top of* the champion's PD (its logit is an
   offset). Its coefficients turn a scenario's shift into an extra logit shift.
   This is the usual top-down design of bank stress tests (a "satellite" model
   linking risk parameters to macro variables). A coefficient with the
   economically wrong sign is set to 0, so stress can never lower risk.

LGD responds through loan-to-value: a house-price fall of x% raises current LTV
to LTV / (1 + x), and the LGD model is re-run on that. PD does *not* get the
re-marked LTV: its house-price channel is the HPI feature plus the satellite,
and also feeding a higher LTV to the PD model would count the fall twice.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import feature_columns

MACRO = ["unemp_rate", "unemp_chg_12m", "hpi_chg_12m"]
# Expected sign of each satellite coefficient: more unemployment (level or
# rise) raises default risk; faster house-price growth lowers it.
EXPECTED_SIGN = {"unemp_rate": 1, "unemp_chg_12m": 1, "hpi_chg_12m": -1}


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def fit_satellite(y: np.ndarray, offset: np.ndarray, macro: pd.DataFrame, iters: int = 50) -> dict:
    """Logistic regression y ~ offset + a + b . macro by Newton-Raphson.

    Returns coefficients, standard errors, and the sign-constrained
    coefficients actually used for stress (wrong-sign -> 0).
    """
    X = np.column_stack([np.ones(len(macro)), macro[MACRO].to_numpy(float)])
    y = np.asarray(y, float)
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = _sigmoid(offset + X @ beta)
        w = p * (1 - p)
        hess = X.T @ (X * w[:, None]) + 1e-8 * np.eye(X.shape[1])
        step = np.linalg.solve(hess, X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-9:
            break
    p = _sigmoid(offset + X @ beta)
    cov = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    se = np.sqrt(np.diag(cov))
    coef = dict(zip(MACRO, beta[1:].tolist(), strict=True))
    used = {k: (v if np.sign(v) == EXPECTED_SIGN[k] else 0.0) for k, v in coef.items()}
    return {
        "intercept": float(beta[0]),
        "coef": coef,
        "se": dict(zip(MACRO, se[1:].tolist(), strict=True)),
        "used": used,
        "n": int(len(y)),
        "default_rate": float(y.mean()),
    }


def shock(
    X: pd.DataFrame, unemployment_pts: float, hpi_change_pct: float, remark_ltv: bool = False
) -> pd.DataFrame:
    """The same loans under a scenario: macro features shifted; with
    `remark_ltv`, LTV re-marked to the new house value (for LGD only)."""
    X = X.copy()
    X["unemp_rate"] = X["unemp_rate"] + unemployment_pts
    X["unemp_chg_12m"] = X["unemp_chg_12m"] + unemployment_pts
    X["hpi_chg_12m"] = X["hpi_chg_12m"] + hpi_change_pct
    # Current LTV after the price move (loan balance unchanged, value moves).
    # Integer like the original column; 'high_ltv' and 'ltv_dti' follow it.
    if remark_ltv and hpi_change_pct:
        ltv = X["ltv"] / (1 + hpi_change_pct / 100)
        X["ltv"] = ltv.round().clip(upper=200).astype(X["ltv"].dtype)
        X["high_ltv"] = (X["ltv"] > 80).astype(int)
        X["ltv_dti"] = (X["ltv"] * X["dti"] / 100.0).round(2)
    return X


class StressEngine:
    """Holds the OOT portfolio, the models and the satellite; runs scenarios."""

    def __init__(self, cfg: Config | None = None, satellite: dict | None = None):
        from creditcast.pipeline.split import make_split
        from creditcast.serving import ModelBundle

        self.cfg = cfg or load_config()
        self.bundle = ModelBundle(self.cfg)
        split = make_split(cfg=self.cfg)
        scored = pd.read_parquet(self.cfg.path("artifacts") / "test_scored.parquet")
        # Estimated EAD from scoring (Gold's 'ead' is the realised one on defaults)
        est = scored[["loan_id", "credit_score", "ead"]].rename(columns={"ead": "ead_hat"})
        test = split.test.merge(est, on="loan_id")
        self.X = test[feature_columns()].reset_index(drop=True)
        self.ead = test["ead_hat"].to_numpy(float)
        from creditcast.governance import decision

        self.band = np.asarray(decision.assign_band(test["credit_score"].to_numpy(), self.cfg))
        self.threshold = self.bundle.threshold

        if satellite is None:
            labelled = pd.concat(
                [split.train, split.calib, split.valid, split.test], ignore_index=True
            )
            offset = _logit(self.bundle.pd_from_features(labelled[feature_columns()]))
            satellite = fit_satellite(labelled["default_12m"].to_numpy(), offset, labelled[MACRO])
        self.satellite = satellite

    def run(self, unemployment_pts: float = 0.0, hpi_change_pct: float = 0.0) -> dict:
        Xs = shock(self.X, unemployment_pts, hpi_change_pct)
        Xl = shock(self.X, unemployment_pts, hpi_change_pct, remark_ltv=True)
        delta = {
            "unemp_rate": unemployment_pts,
            "unemp_chg_12m": unemployment_pts,
            "hpi_chg_12m": hpi_change_pct,
        }
        extra = sum(self.satellite["used"][k] * delta[k] for k in MACRO)
        pd_model = self.bundle.pd_from_features(Xs)
        pd_s = _sigmoid(_logit(pd_model) + extra)
        lgd_s = np.clip(self.bundle.lgd.predict(Xl), 0, 1)
        el = pd_s * lgd_s * self.ead
        ead_total = float(self.ead.sum())
        by_band = (
            pd.DataFrame({"band": self.band, "pd": pd_s}).groupby("band", sort=False)["pd"].mean()
        )
        order = [str(b["name"]) for b in self.cfg.decision.bands]  # best grade first
        bands = [b for b in order if b in by_band.index]
        return {
            "unemployment_pts": float(unemployment_pts),
            "hpi_change_pct": float(hpi_change_pct),
            "n_loans": int(len(pd_s)),
            "mean_pd": float(pd_s.mean()),
            "mean_lgd": float(lgd_s.mean()),
            "expected_loss": float(el.sum()),
            "el_bps": float(el.sum() / ead_total * 1e4),
            "approval_rate": float((pd_s <= self.threshold).mean()),
            "pd_by_band": [{"band": b, "mean_pd": float(by_band[b])} for b in bands],
            "satellite_logit_shift": float(extra),
        }


@lru_cache(maxsize=1)
def engine() -> StressEngine:
    """The serving engine: reuses the satellite fitted by the pipeline run."""
    cfg = load_config()
    path = cfg.path("artifacts") / "stress_report.json"
    sat = json.loads(path.read_text())["satellite"] if path.exists() else None
    return StressEngine(cfg, satellite=sat)


def stress_report(cfg: Config | None = None) -> Path:
    """Run every configured scenario and persist artifacts/stress_report.json."""
    cfg = cfg or load_config()
    eng = StressEngine(cfg)
    scenarios = {
        name: {"label": str(s.get("label", name)), **eng.run(
            float(s["unemployment_pts"]), float(s["hpi_change_pct"])
        )}
        for name, s in dict(cfg.stress.scenarios).items()
    }  # fmt: skip
    base = scenarios["baseline"]["expected_loss"]
    for s in scenarios.values():
        s["el_vs_baseline_pct"] = (s["expected_loss"] / base - 1) * 100 if base else None
    report = {"stamp": run_stamp(), "satellite": eng.satellite, "scenarios": scenarios}
    out = cfg.path("artifacts") / "stress_report.json"
    out.write_text(json.dumps(report, indent=2))
    return out


if __name__ == "__main__":
    p = stress_report()
    print(json.dumps(json.loads(p.read_text())["scenarios"], indent=2))

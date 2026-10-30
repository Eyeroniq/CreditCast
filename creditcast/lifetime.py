"""Lifetime PD and IFRS 9 staging (ROADMAP 5.3).

**Lifetime PD.** A discrete-time survival model on the loan-month panel: the
chance of a first 90+ DPD in loan month t, given the loan is still performing,
is a logistic hazard

    logit h(t) = a[age bucket of t] + b * logit(PD_12m)

fitted on the training vintages. The age terms give the seasoning curve (risk
builds, peaks, then eases); b ties each loan's curve to its own 12-month PD.
Prepayment is a competing exit at the panel's observed monthly rate.

For a loan with remaining term T:

    lifetime PD = PD_12m + sum_{t=13..T} S(t-1) * h(t)
    S(12) = (1 - PD_12m) * (1 - prepay)^12,   S(t) = S(t-1) * (1 - h(t)) * (1 - prepay)

so year one is exactly the champion's PD and lifetime PD >= 12-month PD for
every loan. The panel covers 24 months; beyond that the last age bucket's hazard
is held flat (an explicit assumption; real mortgage hazards ease further).

**IFRS 9 staging** of the out-of-time book at the reporting date (data cutoff):
Stage 3 = 90+ DPD (credit-impaired); Stage 2 = significant increase in credit
risk: 30+ DPD (the backstop) or 12-month PD now >= 2x its origination value and
at least 0.5 points higher (re-scored with the economy at the reporting date);
Stage 1 = the rest. Expected credit loss: Stage 1 = 12-month ECL, Stage 2 =
lifetime ECL (amortising balance, discounted at the note rate), Stage 3 =
LGD x balance. Loans already prepaid or written off are off the books.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import feature_columns

AGE_EDGES = [0, 3, 6, 9, 12, 15, 18, 21, 24]  # buckets (0,3], (3,6], ... (21,24]
N_BUCKETS = len(AGE_EDGES) - 1
FIRST_YEAR = 12


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def age_bucket(age) -> np.ndarray:
    """0-based bucket index for loan month(s) >= 1; beyond the panel -> last bucket."""
    a = np.minimum(np.asarray(age, int), AGE_EDGES[-1])
    return np.searchsorted(AGE_EDGES, a, side="left") - 1


# ---- panel -------------------------------------------------------------------
def build_panel(cfg: Config) -> pd.DataFrame:
    """One row per loan-month at risk of a first default: age, default (0/1),
    prepaid (0/1). A loan leaves after its first 90+ DPD month or prepayment."""
    perf = pd.read_parquet(
        cfg.path("bronze") / "performance",
        columns=["loan_id", "loan_age", "current_loan_delinquency_status", "zero_balance_code"],
    )
    perf = perf.sort_values(["loan_id", "loan_age"])
    dpd = pd.to_numeric(perf["current_loan_delinquency_status"], errors="coerce").fillna(0)
    dpd_months = int(cfg.target.default_dpd_threshold) // 30
    is_def = (dpd >= dpd_months) | perf["zero_balance_code"].isin(list(cfg.target.default_zb_codes))
    perf = perf.assign(default=is_def.astype(int))
    # keep months up to and including the first default
    seen = perf.groupby("loan_id")["default"].cumsum()
    perf = perf[(seen == 0) | ((seen == 1) & (perf["default"] == 1))]
    prepaid = perf["zero_balance_code"].isin(list(cfg.target.prepay_zb_codes))
    return pd.DataFrame(
        {
            "loan_id": perf["loan_id"].to_numpy(),
            "age": perf["loan_age"].to_numpy(int),
            "default": perf["default"].to_numpy(int),
            "prepaid": prepaid.to_numpy(int),
        }
    )


def fit_hazard(panel: pd.DataFrame, pd12: pd.Series, iters: int = 50) -> dict:
    """Logistic hazard with age-bucket intercepts + slope on logit(PD_12m)."""
    df = panel.merge(pd12.rename("pd12"), left_on="loan_id", right_index=True)
    b = age_bucket(df["age"].to_numpy())
    X = np.zeros((len(df), N_BUCKETS + 1))
    X[np.arange(len(df)), b] = 1.0
    X[:, -1] = _logit(df["pd12"].to_numpy())
    y = df["default"].to_numpy(float)
    beta = np.zeros(X.shape[1])
    beta[:N_BUCKETS] = _logit(max(y.mean(), 1e-4))
    for _ in range(iters):
        p = _sigmoid(X @ beta)
        w = p * (1 - p)
        step = np.linalg.solve(X.T @ (X * w[:, None]) + 1e-8 * np.eye(X.shape[1]), X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-9:
            break
    healthy = df[df["default"] == 0]
    return {
        "age_edges": AGE_EDGES,
        "alpha": beta[:N_BUCKETS].tolist(),
        "beta_logit_pd12": float(beta[-1]),
        "prepay_monthly": float(healthy["prepaid"].mean()),
        "n_loan_months": int(len(df)),
        "n_defaults": int(y.sum()),
    }


# ---- lifetime PD -------------------------------------------------------------
def hazard_path(pd12: np.ndarray, ages: np.ndarray, fit: dict) -> np.ndarray:
    """Monthly default hazard for each loan (rows) at each loan age (cols)."""
    alpha = np.asarray(fit["alpha"])[age_bucket(ages)]
    return _sigmoid(alpha[None, :] + fit["beta_logit_pd12"] * _logit(pd12)[:, None])


def marginal_pd(
    pd12: np.ndarray, age_now: np.ndarray, remaining: np.ndarray, fit: dict
) -> np.ndarray:
    """Unconditional default probability in each future month t = 1..max term.

    Year one spreads the 12-month PD evenly (it is the champion's figure);
    later months follow the hazard curve from the loan's current age, with
    prepayment as a competing exit. Months past the remaining term are 0.
    """
    pd12 = np.asarray(pd12, float)
    age_now = np.asarray(age_now, int)
    remaining = np.asarray(remaining, int)
    horizon = int(remaining.max())
    t = np.arange(1, horizon + 1)
    out = np.zeros((len(pd12), horizon))
    out[:, : min(FIRST_YEAR, horizon)] = (pd12 / FIRST_YEAR)[:, None]
    if horizon > FIRST_YEAR:
        q = float(fit["prepay_monthly"])
        later = t[FIRST_YEAR:]
        # hazard at the loan's own age (current age + months ahead)
        ages = age_now[:, None] + later[None, :]
        alpha = np.asarray(fit["alpha"])[age_bucket(ages)]
        h = _sigmoid(alpha + fit["beta_logit_pd12"] * _logit(pd12)[:, None])
        surv_12 = (1 - pd12) * (1 - q) ** FIRST_YEAR
        # survival before each later month: S(12) * prod_{13..t-1} (1-h)(1-q)
        step = (1 - h) * (1 - q)
        before = np.concatenate([np.ones((len(pd12), 1)), np.cumprod(step, axis=1)[:, :-1]], axis=1)
        out[:, FIRST_YEAR:] = surv_12[:, None] * before * h
    out[t[None, :] > remaining[:, None]] = 0.0
    return out


def lifetime_pd(pd12, age_now, remaining, fit) -> np.ndarray:
    m = marginal_pd(pd12, age_now, remaining, fit)
    # year one is the champion's PD exactly (even if fewer months remain, the
    # 12-month PD is the floor IFRS 9 compares against)
    return np.maximum(m.sum(axis=1), np.asarray(pd12, float))


def scheduled_balance(balance, annual_rate, remaining, months: int) -> np.ndarray:
    """Amortising balance at the start of each of the next `months` months."""
    r = np.asarray(annual_rate, float)[:, None] / 100 / 12
    n = np.maximum(np.asarray(remaining, int), 1)[:, None]
    b0 = np.asarray(balance, float)[:, None]
    t = np.arange(months)[None, :]
    growth = (1 + r) ** t
    pmt_factor = np.where(r > 0, ((1 + r) ** t - 1) / np.where(r > 0, r, 1), t)
    pmt = np.where(r > 0, b0 * r / (1 - (1 + r) ** (-n)), b0 / n)
    bal = b0 * growth - pmt * pmt_factor
    return np.clip(np.where(t < n, bal, 0.0), 0.0, None)


def ecl(pd12, age_now, remaining, lgd, balance, rate, fit) -> tuple[np.ndarray, np.ndarray]:
    """(12-month ECL, lifetime ECL): sum of marginal PD x LGD x EAD_t, discounted
    at the note rate (IFRS 9's effective interest rate, simplified)."""
    m = marginal_pd(pd12, age_now, remaining, fit)
    months = m.shape[1]
    ead = scheduled_balance(balance, rate, remaining, months)
    df = (1 + np.asarray(rate, float)[:, None] / 100 / 12) ** -np.arange(1, months + 1)[None, :]
    loss = m * np.asarray(lgd, float)[:, None] * ead * df
    return loss[:, :FIRST_YEAR].sum(axis=1), loss.sum(axis=1)


# ---- report ------------------------------------------------------------------
def build_lifetime(cfg: Config | None = None) -> Path:
    """Fit the hazard on training vintages, back-test it on the out-of-time
    loans, score lifetime PD and IFRS 9 stages, and persist the results."""
    from creditcast.pipeline import macro
    from creditcast.pipeline.split import make_split
    from creditcast.serving import ModelBundle

    cfg = cfg or load_config()
    art = cfg.path("artifacts")
    bundle = ModelBundle(cfg)
    split = make_split(cfg=cfg)
    feats = feature_columns()
    panel = build_panel(cfg)

    def pd_for(df: pd.DataFrame) -> pd.Series:
        return pd.Series(bundle.pd_from_features(df[feats]), index=df["loan_id"].to_numpy())

    in_time = pd.concat([split.train, split.calib, split.valid], ignore_index=True)
    fit = fit_hazard(panel[panel["loan_id"].isin(in_time["loan_id"])], pd_for(in_time))

    # back-test on out-of-time loans seen for the full 24 months
    test = split.test
    pd12_test = pd_for(test)
    cutoff = str(cfg.generator.data_cutoff)
    backtest = {
        # in-time: does the curve describe the vintages it was fitted on?
        "in_time": _backtest(panel, in_time, pd_for(in_time), fit, cutoff),
        # out-of-time: 2020 vintages, which met the 2020 shock
        "out_of_time": _backtest(panel, test, pd12_test, fit, cutoff),
    }

    # ---- reporting-date view of the OOT book ----------------------------------
    scored = pd.read_parquet(art / "test_scored.parquet")[["loan_id", "lgd_hat", "ead"]]
    status = _status_at_cutoff(cfg, test["loan_id"])
    book = test.merge(scored, on="loan_id").merge(status, on="loan_id")
    on_book = book[book["off_book"] == 0].reset_index(drop=True)

    pd12_orig = bundle.pd_from_features(on_book[feats])
    now = on_book[feats].copy()
    table = pd.read_parquet(cfg.path("gold") / "macro_features.parquet")
    latest = macro.lookup_macro(on_book.assign(vintage=None), table)  # newest month per state
    for c in latest.columns:
        if c in now:
            now[c] = latest[c].to_numpy()
    pd12_now = bundle.pd_from_features(now)

    term = on_book["orig_loan_term"].to_numpy(int)
    age = on_book["age_now"].to_numpy(int)
    remaining = np.maximum(term - age, 1)
    lgd = np.clip(on_book["lgd_hat"].to_numpy(float), 0, 1)
    bal = on_book["balance"].to_numpy(float)
    rate = on_book["orig_interest_rate"].to_numpy(float)

    sicr_cfg = cfg.ifrs9
    stage = np.where(
        on_book["dpd"].to_numpy() >= 3,
        3,
        np.where(
            (on_book["dpd"].to_numpy() >= 1)
            | (
                (pd12_now >= float(sicr_cfg.sicr_relative) * pd12_orig)
                & (pd12_now - pd12_orig >= float(sicr_cfg.sicr_absolute))
            ),
            2,
            1,
        ),
    )
    ecl_12, ecl_life = ecl(pd12_now, age, remaining, lgd, bal, rate, fit)
    allowance = np.where(stage == 1, ecl_12, np.where(stage == 2, ecl_life, lgd * bal))

    # lifetime PD at origination for every OOT loan (Portfolio table)
    orig_life = lifetime_pd(
        pd12_test.to_numpy(), np.zeros(len(test), int), test["orig_loan_term"].to_numpy(int), fit
    )
    per_loan = pd.DataFrame(
        {
            "loan_id": test["loan_id"].to_numpy(),
            "pd_12m": pd12_test.to_numpy(),
            "pd_lifetime": orig_life,
        }
    ).merge(
        pd.DataFrame({"loan_id": on_book["loan_id"], "ifrs9_stage": stage, "ecl": allowance}),
        on="loan_id",
        how="left",
    )
    per_loan.to_parquet(art / "lifetime_scored.parquet", index=False)

    stages = []
    for s in (1, 2, 3):
        mask = stage == s
        exposure = float(bal[mask].sum())
        stages.append(
            {
                "stage": s,
                "loans": int(mask.sum()),
                "exposure": exposure,
                "ecl": float(allowance[mask].sum()),
                "coverage": float(allowance[mask].sum() / exposure) if exposure else 0.0,
            }
        )
    report = {
        "stamp": run_stamp(),
        "reporting_date": str(cfg.generator.data_cutoff),
        "hazard": fit,
        "backtest": backtest,
        "lifetime_pd": {
            "mean_12m": float(pd12_test.mean()),
            "mean_lifetime": float(orig_life.mean()),
            "min_gap": float((orig_life - pd12_test.to_numpy()).min()),
        },
        "staging": {
            "on_book": int(len(on_book)),
            "off_book": int((book["off_book"] == 1).sum()),
            "stages": stages,
            "total_ecl": float(allowance.sum()),
            "sicr_rule": {
                "dpd_backstop_months": 1,
                "relative": float(sicr_cfg.sicr_relative),
                "absolute": float(sicr_cfg.sicr_absolute),
            },
        },
    }
    out = art / "lifetime_report.json"
    out.write_text(json.dumps(report, indent=2, default=float))
    return out


def _status_at_cutoff(cfg: Config, loan_ids: pd.Series) -> pd.DataFrame:
    """Each loan's last reported month: age, balance, DPD, and whether it has
    already left the book (prepaid or disposed)."""
    perf = pd.read_parquet(
        cfg.path("bronze") / "performance",
        columns=[
            "loan_id",
            "loan_age",
            "current_upb",
            "current_loan_delinquency_status",
            "zero_balance_code",
        ],
    )
    perf = perf[perf["loan_id"].isin(set(loan_ids))]
    last = perf.sort_values(["loan_id", "loan_age"]).groupby("loan_id").tail(1)
    return pd.DataFrame(
        {
            "loan_id": last["loan_id"].to_numpy(),
            "age_now": last["loan_age"].to_numpy(int),
            "balance": last["current_upb"].to_numpy(float),
            "dpd": pd.to_numeric(last["current_loan_delinquency_status"], errors="coerce")
            .fillna(0)
            .to_numpy(int),
            "off_book": last["zero_balance_code"].notna().astype(int).to_numpy(),
        }
    )


def _backtest(
    panel: pd.DataFrame, test: pd.DataFrame, pd12: pd.Series, fit: dict, cutoff: str
) -> dict:
    """Predicted vs observed cumulative first-default rate by month 24, for
    out-of-time vintages old enough to be seen for 24 months by the cutoff.
    (Taking only loans that *happen* to be fully seen would over-count defaults:
    a recent loan that defaulted is visible, its healthy twin is not.)"""
    old_enough = pd.PeriodIndex(test["vintage"], freq="M") + 24 <= pd.Period(cutoff, freq="M")
    ids = test.loc[old_enough, "loan_id"]
    full = (
        panel[panel["loan_id"].isin(ids)]
        .groupby("loan_id")
        .agg(defaulted=("default", "max"), prepaid=("prepaid", "max"))
    )
    p = pd12.reindex(full.index).to_numpy()
    q = float(fit["prepay_monthly"])
    ages = np.arange(1, 25)
    h = hazard_path(p, ages, fit)
    step = (1 - h) * (1 - q)
    before = np.concatenate([np.ones((len(p), 1)), np.cumprod(step, axis=1)[:, :-1]], axis=1)
    predicted = float((before * h).sum(axis=1).mean())
    return {
        "vintages": f"{test.loc[old_enough, 'vintage'].min()} to {test.loc[old_enough, 'vintage'].max()}",
        "loans": int(len(full)),
        "observed_24m": float(full["defaulted"].mean()),
        "predicted_24m": predicted,
    }


if __name__ == "__main__":
    p = build_lifetime()
    r = json.loads(p.read_text())
    print(json.dumps({k: r[k] for k in ("hazard", "backtest", "lifetime_pd", "staging")}, indent=2))

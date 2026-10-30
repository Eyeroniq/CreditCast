"""Lifetime PD and IFRS 9 staging (ROADMAP 5.3)."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from creditcast.config import Config, load_config
from creditcast.lifetime import (
    N_BUCKETS,
    age_bucket,
    ecl,
    fit_hazard,
    lifetime_pd,
    scheduled_balance,
)

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "lifetime_report.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)
FIT = {"alpha": [-6.0, -5.5, -5.4, -5.6, -5.8, -5.9, -6.0, -6.1], "beta_logit_pd12": 1.0,
       "prepay_monthly": 0.01}  # fmt: skip


def test_age_buckets_and_flat_tail():
    assert age_bucket([1, 3, 4, 12, 13, 24]).tolist() == [0, 0, 1, 3, 4, 7]
    assert age_bucket([25, 360]).tolist() == [N_BUCKETS - 1] * 2  # beyond the panel: last bucket


def test_fit_hazard_is_the_likelihood_maximum_and_recovers_the_truth():
    """At the fitted coefficients the log-likelihood gradient is zero (a true
    maximum-likelihood fit), and they are close to the curve that generated
    the simulated panel."""
    rng = np.random.default_rng(0)
    n = 60_000
    pd12 = np.clip(rng.beta(2, 25, n), 0.002, 0.5)
    alpha_true = np.array([-4.0, -3.2, -3.0, -3.4, -3.6, -3.7, -3.8, -3.9])
    ages = np.tile(np.arange(1, 25), n)
    loan = np.repeat(np.arange(n), 24)
    logit_pd = np.log(pd12 / (1 - pd12))
    h = 1 / (1 + np.exp(-(alpha_true[age_bucket(ages)] + 0.9 * logit_pd[loan])))
    panel = pd.DataFrame(
        {"loan_id": loan, "age": ages, "default": (rng.random(len(h)) < h).astype(int)}
    )
    seen = panel.groupby("loan_id")["default"].cumsum()
    panel = panel[(seen == 0) | ((seen == 1) & (panel["default"] == 1))].assign(prepaid=0)

    fit = fit_hazard(panel, pd.Series(pd12))
    X = np.zeros((len(panel), N_BUCKETS + 1))
    X[np.arange(len(panel)), age_bucket(panel["age"].to_numpy())] = 1
    X[:, -1] = logit_pd[panel["loan_id"].to_numpy()]
    coef = np.array([*fit["alpha"], fit["beta_logit_pd12"]])
    p = 1 / (1 + np.exp(-(X @ coef)))
    gradient = X.T @ (panel["default"].to_numpy() - p)
    assert np.abs(gradient).max() < 1e-6
    assert fit["beta_logit_pd12"] == pytest.approx(0.9, abs=0.15)  # sampling error ~0.05-0.08
    assert np.allclose(fit["alpha"], alpha_true, atol=0.35)


def test_lifetime_pd_is_never_below_12m_and_grows_with_term():
    pd12 = np.array([0.005, 0.02, 0.08, 0.3])
    zero = np.zeros(4, int)
    for term in (6, 12, 180, 360):
        life = lifetime_pd(pd12, zero, np.full(4, term), FIT)
        assert np.all(life >= pd12)
    assert np.allclose(lifetime_pd(pd12, zero, np.full(4, 12), FIT), pd12)  # one year left
    short, long = (lifetime_pd(pd12, zero, np.full(4, t), FIT) for t in (180, 360))
    assert np.all(long > short)
    assert np.all(np.diff(lifetime_pd(pd12, zero, np.full(4, 360), FIT)) > 0)  # riskier -> higher


def test_amortising_balance_runs_down_to_zero():
    bal = scheduled_balance([200_000.0], [6.0], [360], 361)[0]
    assert bal[0] == pytest.approx(200_000)
    assert np.all(np.diff(bal[:360]) < 0)
    assert bal[359] < 2_000 and bal[360] == 0.0


def test_lifetime_ecl_exceeds_12_month_ecl():
    e12, life = ecl(np.array([0.03]), np.array([0]), np.array([360]), np.array([0.3]),
                    np.array([250_000.0]), np.array([4.0]), FIT)  # fmt: skip
    assert 0 < e12[0] < life[0]
    assert e12[0] == pytest.approx(0.03 * 0.3 * 250_000, rel=0.05)  # ~ PD x LGD x balance


def test_late_defaults_leave_the_first_year_untouched(tmp_path):
    """The generator's later defaults (months 13+) use their own random stream:
    every loan's first 12 months are identical with or without them."""
    from creditcast.pipeline import generate, macro

    raw = copy.deepcopy(dict(load_config()))
    raw["paths"] = {**raw["paths"], "macro": str(tmp_path / "macro")}
    raw["generator"] = {**raw["generator"], "n_loans": 400}

    def panel(ratio):
        cfg = Config(copy.deepcopy(raw))
        cfg["generator"]["late_default_ratio"] = ratio
        macro.generate_series(cfg)
        rng = np.random.default_rng(cfg.run.seed)
        orig = generate._origination(cfg, rng)
        return generate._performance(orig, cfg, rng)

    without, with_late = panel(0.0), panel(3.0)
    late_ids = set(with_late.loc[with_late["loan_age"] > 12, "loan_id"]) - set()
    first = lambda p: p[p["loan_age"] <= 12].reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(first(without), first(with_late))
    assert len(with_late) != len(without) or late_ids  # the later months did change
    # loans with no late default are identical all the way through
    changed = set(pd.concat([without, with_late]).drop_duplicates(keep=False)["loan_id"])
    same = without[~without["loan_id"].isin(changed)]
    assert len(same) > 0.5 * len(without)


@needs_artifacts
def test_report_staging_is_consistent():
    r = json.loads((ART / "lifetime_report.json").read_text())
    assert r["lifetime_pd"]["min_gap"] >= 0
    st = {s["stage"]: s for s in r["staging"]["stages"]}
    assert sum(s["loans"] for s in st.values()) == r["staging"]["on_book"]
    assert st[3]["coverage"] > st[2]["coverage"] > st[1]["coverage"]
    assert r["backtest"]["in_time"]["predicted_24m"] == pytest.approx(
        r["backtest"]["in_time"]["observed_24m"], abs=0.01
    )

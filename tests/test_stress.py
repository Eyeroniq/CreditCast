"""Stress testing (ROADMAP 5.2): the satellite estimates what it should, shocks
move the right columns, and losses rise with severity."""

import json

import numpy as np
import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.stress import MACRO, fit_satellite, shock

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "stress_report.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)


def _macro(n, rng):
    return pd.DataFrame(
        {
            "unemp_rate": rng.uniform(3, 10, n),
            "unemp_chg_12m": rng.uniform(-3, 5, n),
            "hpi_chg_12m": rng.uniform(-10, 20, n),
        }
    )


def test_satellite_recovers_known_macro_sensitivity():
    rng = np.random.default_rng(0)
    n = 200_000
    m = _macro(n, rng)
    offset = rng.normal(-3.0, 0.8, n)  # the champion's own logit
    true = {"unemp_rate": 0.08, "unemp_chg_12m": 0.05, "hpi_chg_12m": -0.03}
    z = offset + sum(true[k] * m[k] for k in MACRO) - 0.2
    y = rng.random(n) < 1 / (1 + np.exp(-z))
    sat = fit_satellite(y.astype(int), offset, m)
    for k in MACRO:
        assert sat["coef"][k] == pytest.approx(true[k], abs=3 * sat["se"][k] + 0.005)
    assert sat["used"] == sat["coef"]  # all signs as expected


def test_wrong_sign_coefficients_are_not_used():
    rng = np.random.default_rng(1)
    n = 100_000
    m = _macro(n, rng)
    offset = rng.normal(-3.0, 0.8, n)
    z = offset - 0.10 * m["unemp_rate"] + 0.3  # unemployment *lowering* risk
    y = rng.random(n) < 1 / (1 + np.exp(-z))
    sat = fit_satellite(y.astype(int), offset, m)
    assert sat["coef"]["unemp_rate"] < 0
    assert sat["used"]["unemp_rate"] == 0.0  # stress can never lower risk


def test_shock_moves_macro_and_remarks_ltv_only_when_asked():
    X = pd.DataFrame(
        {"unemp_rate": [4.0], "unemp_chg_12m": [-0.5], "hpi_chg_12m": [6.0],
         "ltv": [76], "dti": [40.0], "high_ltv": [0], "ltv_dti": [30.4]}
    )  # fmt: skip
    pd_side = shock(X, 3, -20)
    assert pd_side.iloc[0][["unemp_rate", "unemp_chg_12m", "hpi_chg_12m"]].tolist() == [
        7.0,
        2.5,
        -14.0,
    ]
    assert pd_side.iloc[0]["ltv"] == 76  # PD side: house-price channel is the HPI feature
    lgd_side = shock(X, 3, -20, remark_ltv=True).iloc[0]
    assert lgd_side["ltv"] == 95  # 76 / 0.8
    assert lgd_side["high_ltv"] == 1 and lgd_side["ltv_dti"] == pytest.approx(38.0)
    assert X.iloc[0]["ltv"] == 76  # input untouched


@needs_artifacts
def test_baseline_matches_the_scored_portfolio_and_el_rises_with_severity():
    from creditcast.stress import engine

    eng = engine()
    base = eng.run(0, 0)
    scored = pd.read_parquet(ART / "test_scored.parquet")
    assert base["mean_pd"] == pytest.approx(scored["pd_champion"].mean(), rel=0.01)
    assert base["expected_loss"] == pytest.approx(scored["expected_loss"].sum(), rel=0.01)
    els = [eng.run(u, h)["expected_loss"] for u, h in [(0, 0), (2, -5), (4, -15), (8, -30)]]
    assert els == sorted(els) and len(set(els)) == 4


@needs_artifacts
def test_configured_scenarios_report_is_ordered_and_complete():
    r = json.loads((ART / "stress_report.json").read_text())
    s = r["scenarios"]
    assert set(s) == {"baseline", "adverse", "severely_adverse"}
    assert (
        s["baseline"]["expected_loss"]
        < s["adverse"]["expected_loss"]
        < s["severely_adverse"]["expected_loss"]
    )
    assert s["severely_adverse"]["approval_rate"] < s["baseline"]["approval_rate"]
    assert [b["band"] for b in s["baseline"]["pd_by_band"]] == ["AAA", "AA", "A", "BBB", "BB", "B"]

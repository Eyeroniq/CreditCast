"""Macro features (ROADMAP 5.1): point-in-time only, sensible fallbacks, and
the same values in the pipeline and in serving."""

import pandas as pd
import pytest

from creditcast.features import engineer, rate_benchmark
from creditcast.pipeline.macro import NATIONAL, lookup_macro, macro_table


def _series(months=30):
    m = pd.period_range("2019-01", periods=months, freq="M").astype(str)
    unemp = pd.concat(
        [pd.DataFrame({"state": s, "month": m, "value": [base + i * 0.1 for i in range(months)]})
         for s, base in [("TX", 4.0), ("MI", 6.0)]]
    )  # fmt: skip
    hpi = pd.concat(
        [pd.DataFrame({"state": s, "month": m, "value": [100 * 1.01**i for i in range(months)]})
         for s in ("TX", "MI")]
    )  # fmt: skip
    return {"unemployment": unemp, "hpi": hpi}


def test_values_come_from_the_month_before_origination():
    t = macro_table(_series(), lag=1).set_index(["state", "vintage"])
    # TX unemployment in 2020-03 (index 14) is 5.4; a 2020-04 loan sees it.
    assert t.loc[("TX", "2020-04"), "unemp_rate"] == pytest.approx(5.4)
    assert t.loc[("TX", "2020-04"), "unemp_chg_12m"] == pytest.approx(1.2)  # 12 x 0.1
    assert t.loc[("TX", "2020-04"), "hpi_chg_12m"] == pytest.approx((1.01**12 - 1) * 100, abs=1e-3)


def test_changing_the_origination_month_or_later_never_changes_the_feature():
    s = _series()
    before = macro_table(s, lag=1).set_index(["state", "vintage"]).loc[("TX", "2020-04")]
    for name in ("unemployment", "hpi"):
        df = s[name]
        df.loc[(df["state"] == "TX") & (df["month"] >= "2020-04"), "value"] = 999.0
    after = macro_table(s, lag=1).set_index(["state", "vintage"]).loc[("TX", "2020-04")]
    pd.testing.assert_series_equal(before, after)


def test_lag_below_one_month_is_refused():
    with pytest.raises(ValueError, match=">= 1"):
        macro_table(_series(), lag=0)


def test_unknown_state_uses_national_and_future_month_uses_latest():
    t = macro_table(_series(), lag=1)
    rows = pd.DataFrame(
        [
            {"property_state": "ZZ", "vintage": "2020-04"},
            {"property_state": None, "vintage": "2020-04"},
            {"property_state": "TX", "vintage": "2035-01"},
            {"property_state": "TX", "vintage": None},
        ]
    )
    out = lookup_macro(rows, t)
    us = t.set_index(["state", "vintage"]).loc[(NATIONAL, "2020-04"), "unemp_rate"]
    assert (
        out["unemp_rate"].iloc[0] == pytest.approx(us) == pytest.approx(5.4 + 1.0)
    )  # mean(TX, MI)
    assert out["unemp_rate"].iloc[1] == pytest.approx(us)
    latest_tx = t[t["state"] == "TX"].sort_values("vintage")["unemp_rate"].iloc[-1]
    assert out["unemp_rate"].iloc[2] == out["unemp_rate"].iloc[3] == pytest.approx(latest_tx)
    assert not out.isna().any().any()


def test_engineer_single_row_matches_batch_with_macro():
    """Serving engineers one applicant at a time; it must equal the Gold batch."""
    loans = pd.DataFrame(
        [{"vintage": v, "property_state": s, "orig_interest_rate": 4.0, "ltv": 80, "dti": 35.0}
         for v in ("2020-02", "2020-05", "2020-09") for s in ("TX", "MI", "ZZ")]
    )  # fmt: skip
    bench, table = rate_benchmark(loans), macro_table(_series(), lag=1)
    batch = engineer(loans, bench, table)
    assert {"unemp_rate", "unemp_chg_12m", "hpi_chg_12m"} <= set(batch.columns)
    for i in range(len(loans)):
        one = engineer(loans.iloc[[i]].reset_index(drop=True), bench, table)
        pd.testing.assert_series_equal(one.iloc[0], batch.iloc[i], check_names=False)

"""Feature tests (Phase 1.5): the point-in-time rate benchmark and one shared
`engineer` for pipeline and serving (no train/serve skew)."""

import pandas as pd
import pytest

from creditcast.features import engineer, rate_benchmark


def _loans():
    rows = []
    for m, rate in [("2020-01", 3.0), ("2020-02", 4.0), ("2020-03", 5.0), ("2020-04", 6.0)]:
        for k in range(3):
            rows.append({"vintage": m, "orig_interest_rate": rate, "ltv": 70 + k, "dti": 30.0 + k})
    return pd.DataFrame(rows)


def test_benchmark_uses_only_prior_months():
    b = rate_benchmark(_loans(), window=2).set_index("vintage")["rate_benchmark"]
    assert b["2020-02"] == pytest.approx(3.0)  # only Jan
    assert b["2020-03"] == pytest.approx(3.5)  # Jan + Feb
    assert b["2020-04"] == pytest.approx(4.5)  # Feb + Mar (window 2)
    assert b["2020-05"] == pytest.approx(5.5)  # next, unseen month exists


def test_benchmark_ignores_the_loans_own_month():
    loans = _loans()
    before = rate_benchmark(loans).set_index("vintage")["rate_benchmark"]["2020-03"]
    loans.loc[loans["vintage"] == "2020-03", "orig_interest_rate"] = 99.0
    after = rate_benchmark(loans).set_index("vintage")["rate_benchmark"]["2020-03"]
    assert before == after


def test_single_row_matches_batch():
    """Serving engineers one row at a time; it must equal the batch result."""
    loans = _loans()
    bench = rate_benchmark(loans)
    batch = engineer(loans, bench)
    for i in range(len(loans)):
        one = engineer(loans.iloc[[i]].reset_index(drop=True), bench)
        pd.testing.assert_series_equal(one.iloc[0], batch.iloc[i], check_names=False)


def test_unknown_or_missing_vintage_uses_latest_benchmark():
    bench = rate_benchmark(_loans())
    latest = float(bench["rate_benchmark"].iloc[-1])
    row = pd.DataFrame(
        [
            {"vintage": None, "orig_interest_rate": 7.0, "ltv": 85, "dti": 40.0},
            {"vintage": "2030-01", "orig_interest_rate": 7.0, "ltv": 85, "dti": 40.0},
        ]
    )
    out = engineer(row, bench)
    assert out["rate_spread"].tolist() == [round(7.0 - latest, 3)] * 2

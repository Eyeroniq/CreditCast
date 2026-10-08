"""Silver label tests: the point-in-time 12m default flag, right-censoring
(Phase 1.3) and resolved-loss LGD fields (Phase 1.4), on hand-built panels.

Each case is one loan originated 2020-01 with a hand-written performance
history, run through the real DuckDB Silver build in a temp directory.
"""
import copy

import numpy as np
import pandas as pd
import pytest

from creditcast.config import Config, load_config
from creditcast.pipeline.silver import build_silver

ORIG = {"vintage": "2020-01", "orig_date": pd.Timestamp("2020-01-01"),
        "fico": 720, "dti": 35.0, "ltv": 80, "orig_interest_rate": 4.0,
        "orig_upb": 200_000, "orig_loan_term": 360, "occupancy_status": "P",
        "loan_purpose": "P", "property_type": "SF", "first_time_homebuyer": "N",
        "borrower_race": "White"}


def _month(age: int, vintage: str = "2020-01") -> str:
    return str(pd.Period(vintage, freq="M") + age)


def _history(loan_id, n_months, dpd=None, zb=None, loss=None, vintage="2020-01"):
    """n_months of performance; dpd/zb/loss are {age: value} overrides."""
    dpd, zb, loss = dpd or {}, zb or {}, loss or {}
    rows = []
    for age in range(1, n_months + 1):
        rows.append({"loan_id": loan_id, "monthly_reporting_period": _month(age, vintage),
                     "loan_age": age, "current_upb": 200_000.0 - 300 * age,
                     "current_loan_delinquency_status": dpd.get(age, "0"),
                     "zero_balance_code": zb.get(age), "net_loss": loss.get(age, np.nan)})
    return rows


CASES = {
    # id: (history rows, expected default_12m, label_complete, resolved)
    1: (_history(1, 24), 0, 1, 0),                                    # clean 12m+
    2: (_history(2, 5), 0, 0, 0),                                     # data ends early
    3: (_history(3, 9, dpd={4: "3", 5: "4", 6: "5", 7: "6", 8: "6"},
                 zb={9: "09"}, loss={9: 50_000.0}), 1, 1, 1),         # default + REO
    4: (_history(4, 6, zb={6: "01"}), 0, 1, 0),                       # prepaid -> genuine 0
    5: (_history(5, 24, dpd={13: "3", 14: "4"}), 0, 1, 0),            # 90+ only after window
    6: (_history(6, 12, dpd={10: "3", 11: "4", 12: "5"}), 1, 1, 0),   # default, unresolved
    7: (_history(7, 20, dpd={10: "3", 11: "4", 12: "5", 13: "6"},
                 zb={14: "09"}, loss={14: 30_000.0}), 1, 1, 1),       # REO after 12m window
    8: (_history(8, 20, dpd={4: "3", 5: "4"}), 1, 1, 1),              # cures: back to current
    # Originated 2021-06: its 12m window ends 2022-06, after the panel's last
    # month (2022-01). Even though it defaulted early, it is censored — keeping
    # it while dropping its non-defaulting peers would inflate the default rate.
    9: (_history(9, 7, dpd={2: "3", 3: "4", 4: "5", 5: "6", 6: "6", 7: "6"},
                 vintage="2021-06"), 1, 0, 0),
}
VINTAGE = {9: "2021-06"}


@pytest.fixture(scope="module")
def silver(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("silver")
    cfg = Config(copy.deepcopy(dict(load_config())))
    cfg["paths"] = {**cfg["paths"], "bronze": str(tmp / "bronze"),
                    "silver": str(tmp / "silver")}
    (tmp / "bronze" / "origination").mkdir(parents=True)
    (tmp / "bronze" / "performance").mkdir(parents=True)
    orig = pd.DataFrame([{"loan_id": i, **ORIG, "vintage": VINTAGE.get(i, ORIG["vintage"])}
                         for i in CASES])
    perf = pd.DataFrame([r for rows, *_ in CASES.values() for r in rows])
    perf["zero_balance_code"] = perf["zero_balance_code"].astype("string")
    orig.to_parquet(tmp / "bronze" / "origination" / "orig_2020.parquet", index=False)
    perf.to_parquet(tmp / "bronze" / "performance" / "perf_2020.parquet", index=False)

    cfg["target"] = {**cfg["target"], "censoring": "keep_flagged"}
    out = build_silver(cfg)
    return pd.read_parquet(out).set_index("loan_id")


@pytest.mark.parametrize("loan_id", sorted(CASES))
def test_label_censoring_and_resolution(silver, loan_id):
    _, default, complete, resolved = CASES[loan_id]
    row = silver.loc[loan_id]
    assert row["default_12m"] == default
    assert row["label_complete"] == complete
    assert row["resolved"] == resolved


def test_resolved_loss_is_taken_from_the_disposition(silver):
    # Loan 7 defaults inside the 12m window but is disposed at month 14 — the
    # old window-limited query lost this and treated it as a 0% loss.
    assert silver.loc[7, "net_loss"] == pytest.approx(30_000.0)
    assert silver.loc[3, "net_loss"] == pytest.approx(50_000.0)
    assert np.isnan(silver.loc[6, "net_loss"])          # unresolved -> no loss
    assert silver.loc[8, "net_loss"] == pytest.approx(0.0)   # cure -> zero loss


def test_ead_is_balance_at_first_default_month(silver):
    assert silver.loc[3, "ead"] == pytest.approx(200_000.0 - 300 * 4)

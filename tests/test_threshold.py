"""Decision-threshold tests (Phase 1.1) and champion consistency (Phase 1.7)."""

import json

import numpy as np
import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.governance.decision import (
    closed_form_threshold,
    default_threshold,
    empirical_threshold,
)
from creditcast.models.calibration import cross_fit_transform


def test_threshold_minimizes_cost():
    # PD perfectly separates: defaults at 0.9, goods at 0.1 -> any cut-off in
    # between costs 0; the chosen threshold must approve all goods.
    p = np.r_[np.full(90, 0.1), np.full(10, 0.9)]
    y = np.r_[np.zeros(90), np.ones(10)]
    thr = empirical_threshold(p, y, load_config())
    assert 0.1 <= thr < 0.9


def test_closed_form_threshold_is_cost_ratio():
    cfg = load_config()
    c_fn, c_fp = float(cfg.decision.cost_fn), float(cfg.decision.cost_fp)
    assert closed_form_threshold(cfg) == pytest.approx(c_fp / (c_fp + c_fn))
    assert default_threshold([0.5], [1], cfg, method="closed_form") == closed_form_threshold(cfg)


def test_calibrated_pds_respect_floor():
    from creditcast.models.calibration import fit_calibrator

    cfg = load_config()
    rng = np.random.default_rng(1)
    raw = rng.random(3000)
    y = (rng.random(3000) < raw**4 * 0.3).astype(int)  # many PDs near 0
    out = fit_calibrator(raw, y, cfg).transform(raw)
    assert out.min() >= float(cfg.calibration.pd_floor)


def test_cross_fit_is_out_of_fold_and_in_range():
    rng = np.random.default_rng(0)
    raw = rng.random(2000)
    y = (rng.random(2000) < raw * 0.2).astype(int)
    out = cross_fit_transform(raw, y, load_config())
    assert out.shape == raw.shape
    assert np.all((out >= 0) & (out <= 1))


ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "governance_report.json").exists() or not (ART / "calib_scored.parquet").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)


@needs_artifacts
def test_threshold_is_chosen_on_calib_not_test():
    cfg = load_config()
    gov = json.loads((ART / "governance_report.json").read_text())
    calib = pd.read_parquet(ART / "calib_scored.parquet")
    test = pd.read_parquet(ART / "test_scored.parquet")
    assert gov["decision"]["threshold_source"].startswith("calib")
    expected = default_threshold(calib["pd_champion"], calib["default_12m"], cfg)
    assert gov["decision"]["threshold"] == pytest.approx(expected)
    # calib and test never share loans
    assert not set(calib["loan_id"]) & set(test["loan_id"])


@needs_artifacts
def test_champion_column_matches_config():
    cfg = load_config()
    test = pd.read_parquet(ART / "test_scored.parquet")
    champ = f"pd_{cfg.decision.champion}"
    np.testing.assert_allclose(test["pd_champion"], test[champ])


# ---- 6.2.5 approval-limit curve ---------------------------------------------------
def _toy_book():
    rng = np.random.default_rng(3)
    n = 4000
    pd_ = rng.beta(1.2, 20, n)
    return pd.DataFrame(
        {
            "pd_champion": pd_,
            "default_12m": (rng.random(n) < pd_).astype(int),
            "expected_loss": pd_ * 0.3 * 200_000,
            "ead": np.full(n, 200_000.0),
            "borrower_race": rng.choice(["White", "Black", "Asian"], n),
        }
    )


def test_threshold_curve_is_monotone_and_consistent():
    from creditcast.governance.decision import threshold_curve

    cfg = load_config()
    book = _toy_book()
    curve = threshold_curve(book, "pd_champion", cfg, grid=[0.02, 0.05, 0.1, 0.2])
    appr = [p["approval_rate"] for p in curve]
    el = [p["expected_loss_approved"] for p in curve]
    assert appr == sorted(appr) and el == sorted(el)  # looser limit: more approvals, more loss
    for p in curve:
        assert 0 <= p["di_min"] <= 1 + 1e-9
        assert set(p["group_approval"]) == {"White", "Black", "Asian"}
        a = book["pd_champion"] <= p["threshold"]
        assert p["approval_rate"] == pytest.approx(a.mean())
        assert p["expected_loss_approved"] == pytest.approx(book.loc[a, "expected_loss"].sum())


@needs_artifacts
def test_curve_artifact_matches_governance_at_policy_threshold():
    gov = json.loads((ART / "governance_report.json").read_text())
    curve = json.loads((ART / "threshold_curve.json").read_text())
    assert curve["policy_threshold"] == pytest.approx(gov["decision"]["threshold"])
    at = min(curve["points"], key=lambda p: abs(p["threshold"] - curve["policy_threshold"]))
    if abs(at["threshold"] - curve["policy_threshold"]) < 1e-9:
        assert at["approval_rate"] == pytest.approx(gov["decision"]["approval_rate"])
        assert at["di_min"] == pytest.approx(gov["fairness"]["di_ratio_min_observed"])

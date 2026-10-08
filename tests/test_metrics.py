"""Validation maths and fairness metrics on hand-made data with known answers
(ROADMAP 2.3)."""

import numpy as np
import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.governance.fairness import fairness_report, group_metrics
from creditcast.validation import calibration_tests as cal
from creditcast.validation import discrimination as disc


# ---- discrimination ------------------------------------------------------------
def test_perfect_and_random_ranking():
    y = np.array([0] * 50 + [1] * 50)
    perfect = np.linspace(0, 1, 100)  # defaulters score highest
    assert disc.auc(y, perfect) == pytest.approx(1.0)
    assert disc.gini(y, perfect) == pytest.approx(1.0)
    assert disc.ks_statistic(y, perfect) == pytest.approx(1.0)
    assert disc.gini(y, perfect[::-1]) == pytest.approx(-1.0)  # inverted ranking


def test_gains_capture_all_defaults_and_report_shape():
    rng = np.random.default_rng(0)
    p = rng.random(2000)
    y = (rng.random(2000) < p * 0.2).astype(int)
    g = disc.gains_table(y, p, n_bands=10)
    assert len(g) == 10
    assert g["cum_capture_rate"].iloc[-1] == pytest.approx(1.0)
    assert g["cum_capture_rate"].is_monotonic_increasing
    rep = disc.discrimination_report(y, p, 10)
    assert {"gini", "ks", "auc", "gains"} <= rep.keys()
    assert 0 < rep["gini"] < 1


# ---- calibration ---------------------------------------------------------------
def test_well_calibrated_predictions_have_small_errors():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.01, 0.3, 50_000)
    y = (rng.random(50_000) < p).astype(int)  # outcomes drawn from p itself
    rep = cal.calibration_report(y, p, 10)
    assert rep["ece"] < 0.01
    assert rep["max_band_error"] < 0.02
    rel = cal.reliability_curve(y, p, 10)
    assert np.allclose(rel["predicted"], rel["observed"], atol=0.02)


def test_miscalibration_is_detected():
    rng = np.random.default_rng(2)
    p = rng.uniform(0.01, 0.3, 20_000)
    y = (rng.random(20_000) < p / 2).astype(int)  # truth is half the prediction
    assert cal.expected_calibration_error(y, p, 10) > 0.03
    assert cal.hosmer_lemeshow(y, p, 10)["p_value"] < 0.01


# ---- fairness -------------------------------------------------------------------
def _book():
    # Group A: 100 loans, PD 0.02 -> all approved. Group B: 100 loans, half at
    # PD 0.02 and half at PD 0.20 -> 50% approved. Privileged group = A.
    rows = [{"borrower_race": "A", "pd_champion": 0.02, "default_12m": 0} for _ in range(100)]
    rows += [
        {"borrower_race": "B", "pd_champion": 0.02 if i < 50 else 0.20, "default_12m": 0}
        for i in range(100)
    ]
    return pd.DataFrame(rows)


def _cfg(privileged="A"):
    import copy
    from creditcast.config import Config

    cfg = Config(copy.deepcopy(dict(load_config())))
    cfg["fairness"] = {**cfg["fairness"], "privileged_group": privileged}
    return cfg


def test_disparate_impact_against_privileged_group():
    rep = fairness_report(_book(), "pd_champion", 0.0625, _cfg("A"))
    by = {g["group"]: g for g in rep["groups"]}
    assert by["A"]["approval_rate"] == 1.0 and by["B"]["approval_rate"] == 0.5
    assert rep["di_ratio_min_observed"] == pytest.approx(0.5)
    assert rep["passes_four_fifths"] is False
    # among good borrowers, B is approved 50 points less often
    assert rep["max_equal_opportunity_diff"] == pytest.approx(0.5)


def test_fairness_passes_when_groups_are_treated_alike():
    book = _book()
    book["pd_champion"] = 0.02
    rep = fairness_report(book, "pd_champion", 0.0625, _cfg("A"))
    assert rep["passes_four_fifths"] and rep["di_ratio_min_observed"] == pytest.approx(1.0)


def test_unknown_privileged_group_falls_back_to_best_group():
    gm = group_metrics(_book(), "pd_champion", 0.0625, _cfg("Z"))
    assert set(gm["group"]) == {"A", "B"}
    rep = fairness_report(_book(), "pd_champion", 0.0625, _cfg("Z"))
    assert rep["di_ratio_min_observed"] == pytest.approx(0.5)

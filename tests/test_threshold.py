"""Decision-threshold tests (Phase 1.1) and champion consistency (Phase 1.7)."""
import json

import numpy as np
import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.governance.decision import default_threshold
from creditcast.models.calibration import cross_fit_transform


def test_threshold_minimizes_cost():
    # PD perfectly separates: defaults at 0.9, goods at 0.1 -> any cut-off in
    # between costs 0; the chosen threshold must approve all goods.
    p = np.r_[np.full(90, 0.1), np.full(10, 0.9)]
    y = np.r_[np.zeros(90), np.ones(10)]
    thr = default_threshold(p, y, load_config())
    assert 0.1 <= thr < 0.9


def test_cross_fit_is_out_of_fold_and_in_range():
    rng = np.random.default_rng(0)
    raw = rng.random(2000)
    y = (rng.random(2000) < raw * 0.2).astype(int)
    out = cross_fit_transform(raw, y, load_config())
    assert out.shape == raw.shape
    assert np.all((out >= 0) & (out <= 1))


ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "governance_report.json").exists()
    or not (ART / "calib_scored.parquet").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)")


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

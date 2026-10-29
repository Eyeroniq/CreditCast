"""Champion-consistent explanations (Phase 1.7): both champions return the
same frame shape, and scorecard reasons are points lost vs the best bin."""

import copy

import pytest

from creditcast.config import Config, load_config

ART = load_config().path("artifacts")
pytestmark = pytest.mark.skipif(
    not (ART / "scorecard.joblib").exists() or not (ART / "challenger.joblib").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)

from creditcast.dataset import feature_columns, load_gold  # noqa: E402
from creditcast.governance import explain, reason_codes  # noqa: E402
from creditcast.models import scorecard as sc_mod  # noqa: E402


def _cfg(champion: str) -> Config:
    cfg = Config(copy.deepcopy(dict(load_config())))
    cfg["decision"] = {**cfg["decision"], "champion": champion}
    return cfg


@pytest.fixture(scope="module")
def risky_row():
    gold = load_gold()
    return gold.sort_values("fico").iloc[[0]][feature_columns()]


@pytest.mark.parametrize("champion", ["challenger", "scorecard"])
def test_local_drivers_shape(champion, risky_row):
    local = explain.local_drivers(risky_row, _cfg(champion))
    assert list(local.columns) == ["feature", "value", "shap"]
    assert set(local["feature"]) == set(feature_columns())
    codes = reason_codes.reason_codes(local, top_n=4)
    assert 1 <= len(codes) <= 4


def test_scorecard_points_lost_are_non_negative_and_match_score(risky_row):
    sc = sc_mod.load()
    local = explain.scorecard_points_lost(sc, risky_row)
    assert (local["shap"] >= -1e-9).all()
    # best possible score minus points lost == applicant's score
    table = sc.table(style="detailed")
    best = table.groupby("Variable")["Points"].max().sum()
    assert best - local["shap"].sum() == pytest.approx(float(sc.score(risky_row)[0]), abs=0.5)


def test_economic_conditions_are_never_adverse_action_reasons():
    """Reg B: a decline must cite the applicant's own factors, not the economy."""
    import pandas as pd

    attr = pd.DataFrame(
        [
            {"feature": "unemp_rate", "value": 9.1, "shap": 0.9},
            {"feature": "fico", "value": 640, "shap": 0.5},
            {"feature": "hpi_chg_12m", "value": -8.0, "shap": 0.4},
            {"feature": "dti", "value": 47.0, "shap": 0.3},
        ]
    )
    got = reason_codes.reason_codes(attr)
    assert [r["feature"] for r in got] == ["fico", "dti"]
    assert [r["rank"] for r in got] == [1, 2]

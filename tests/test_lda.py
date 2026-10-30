"""Less-discriminatory-alternative search (ROADMAP 5.6)."""

import json

import numpy as np
import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.governance.lda import approval_ratios, reweighing_weights

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "lda_report.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)


def test_reweighing_makes_group_and_outcome_independent():
    rng = np.random.default_rng(0)
    g = pd.Series(rng.choice(["A", "B"], 20_000, p=[0.7, 0.3]))
    y = pd.Series((rng.random(20_000) < np.where(g == "B", 0.12, 0.04)).astype(int))
    w = reweighing_weights(g, y)
    weighted_rate = pd.Series(w * y).groupby(g).sum() / pd.Series(w).groupby(g).sum()
    assert weighted_rate["A"] == pytest.approx(weighted_rate["B"], abs=1e-9)
    assert w.sum() == pytest.approx(len(g))  # total weight preserved


def test_one_cut_off_for_everyone_and_ratios_vs_privileged():
    pd_hat = np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08])
    group = pd.Series(["W", "W", "W", "W", "B", "B", "B", "B"])
    ratios = approval_ratios(pd_hat, group, approve_share=0.5, privileged="W")
    assert ratios.to_dict() == {"B": 0.0}  # the four safest are all W
    ratios = approval_ratios(pd_hat[::-1].copy(), group, approve_share=0.75, privileged="W")
    assert ratios["B"] == pytest.approx(1.0 / 0.5)


@needs_artifacts
def test_chosen_alternative_is_fairer_within_tolerance():
    r = json.loads((ART / "lda_report.json").read_text())
    v, base = r["variants"], r["variants"]["baseline"]
    chosen = v[r["chosen"]]
    assert r["chosen"] != "fairlearn_dp"  # uses race in training: reported, never auto-chosen
    assert chosen["gini"] >= base["gini"] - r["gini_tolerance"]
    assert chosen["min_ratio"] >= base["min_ratio"]
    assert set(v) == {"baseline", "drop_dti", "cap_fico", "reweighing", "fairlearn_dp"}

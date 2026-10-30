"""Reject inference study (ROADMAP 5.4)."""

import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.reject_inference import historical_policy, underwriter_judgment

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "reject_inference.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)


def test_policy_applies_every_cut_off():
    df = pd.DataFrame(
        {"fico": [700, 650, 700, 700], "dti": [30, 30, 50, 30], "ltv": [80, 80, 80, 99]}
    )
    policy = NS(min_fico=660, max_dti=45, max_ltv=95)
    assert historical_policy(df, policy).tolist() == [True, False, False, False]


def test_underwriters_decline_bad_loans_more_often():
    n = 200_000
    df = pd.DataFrame({"default_12m": np.r_[np.ones(n // 2, int), np.zeros(n // 2, int)]})
    keep = underwriter_judgment(df, NS(catch_bad=0.35, false_alarm=0.05), np.random.default_rng(0))
    assert 1 - keep[: n // 2].mean() == pytest.approx(0.35, abs=0.01)
    assert 1 - keep[n // 2 :].mean() == pytest.approx(0.05, abs=0.01)


@needs_artifacts
def test_study_shows_when_reject_inference_matters():
    r = json.loads((ART / "reject_inference.json").read_text())
    rules, judged = r["scenarios"]["rules_only"], r["scenarios"]["rules_and_judgment"]
    # hidden outcomes: rejects really are riskier than booked loans
    assert rules["train"]["rejected_default_rate_hidden"] > rules["train"]["approved_default_rate"]
    # rules only (missing at random): ignoring rejects is close to unbiased
    assert abs(rules["methods"]["ignore"]["miss_old_rejects_pts"]) < 1.5
    # with underwriter judgment, booked-only data makes rejects look safer...
    assert judged["methods"]["ignore"]["miss_old_rejects_pts"] < -2
    # ...and the chosen method closes most of that gap
    best = judged["methods"][judged["chosen"]]["miss_old_rejects_pts"]
    assert abs(best) < abs(judged["methods"]["ignore"]["miss_old_rejects_pts"]) / 2
    assert r["chosen"] in {"parceling", "fuzzy"}

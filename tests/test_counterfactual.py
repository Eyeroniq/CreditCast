"""What-if search (ROADMAP 6.2.2), tested against a transparent fake model so
the expected answers are known exactly, plus one check on the real models."""

import numpy as np
import pytest

from creditcast.config import load_config
from creditcast.governance.counterfactual import what_if

BASE = dict(
    fico=650,
    dti=45.0,
    ltv=90,
    orig_interest_rate=5.0,
    orig_upb=300000,
    orig_loan_term=360,
    occupancy_status="P",
    loan_purpose="P",
    property_type="SF",
    first_time_homebuyer="N",
    vintage=None,
)
THR = 0.0605  # a hair above 0.06: avoids 0.02 + 0.04 = 0.0600000000001 float noise


def fake_pd(rows):
    """PD = 0.02 + DTI and LTV excess terms − credit-score term (monotone)."""
    out = []
    for r in rows:
        p = (
            0.02
            + max(0, r["dti"] - 30) * 0.003
            + max(0, r["ltv"] - 70) * 0.002
            - max(0, r["fico"] - 650) * 0.0002
        )
        out.append(min(max(p, 0.0), 1.0))
    return np.array(out)


def test_finds_smallest_change_per_lever_and_each_really_approves():
    r = what_if(BASE, fake_pd, THR)
    assert not r["already_approved"] and r["pd"] > THR
    by = {o["feature"]: o for o in r["options"]}
    # base pd = 0.02 + 15*0.003 + 20*0.002 = 0.105; need a drop of 0.045
    # dti alone: 0.02 + (dti-30)*0.003 + 0.04 <= 0.0605 -> dti <= 30.17 -> 30.0 (0.5 steps)
    assert by["dti"]["target"] == pytest.approx(30.0)
    for o in r["options"]:
        assert fake_pd([o["applicant"]])[0] <= THR  # confirmed approval
        assert o["pd_after"] <= THR
    # options are ordered by effort (share of each lever's range)
    efforts = [o["effort"] for o in r["options"]]
    assert efforts == sorted(efforts)
    assert len(r["options"]) <= 3


def test_borrowing_less_also_lowers_ltv():
    r = what_if(BASE, fake_pd, THR, max_options=4)
    upb = next((o for o in r["options"] if o["feature"] == "orig_upb"), None)
    if upb:
        app = upb["applicant"]
        assert app["orig_upb"] < BASE["orig_upb"] and app["ltv"] < BASE["ltv"]


def test_already_approved_returns_no_options():
    good = {**BASE, "dti": 25.0, "ltv": 60, "fico": 780}
    r = what_if(good, fake_pd, THR)
    assert r["already_approved"] and r["options"] == []


def test_no_single_change_is_reported_honestly():
    def hopeless(rows):  # nothing helps
        return np.full(len(rows), 0.9)

    r = what_if(BASE, hopeless, THR)
    assert r["options"] == [] and "No single change" in r["message"]


def test_never_suggests_non_actionable_features():
    r = what_if(BASE, fake_pd, THR, max_options=10)
    assert {o["feature"] for o in r["options"]} <= {"dti", "ltv", "orig_upb", "fico"}


ART = load_config().path("artifacts")


@pytest.mark.skipif(
    not (ART / "governance_report.json").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)
def test_real_model_suggestions_flip_the_full_decision():
    from creditcast.serving import ModelBundle

    b = ModelBundle()
    marginal = dict(
        fico=690,
        dti=38.0,
        ltv=82,
        orig_interest_rate=4.3,
        orig_upb=300000,
        orig_loan_term=360,
        occupancy_status="P",
        loan_purpose="N",
        property_type="CO",
        first_time_homebuyer="Y",
        vintage="2021-06",
    )
    r = what_if(marginal, b.pd_batch, b.threshold)
    if r["already_approved"]:
        pytest.skip("preset is approved under the current model")
    assert r["options"] or r["message"]
    for o in r["options"]:
        assert b.score(o["applicant"])["decision"] == "approve"

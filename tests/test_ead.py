"""EAD tests (Phase 1.6): scheduled amortized balance."""

import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.models.ead import amortized_balance, estimate_ead


def test_no_payments_is_full_principal():
    assert amortized_balance(100_000, 6.0, 360, 0) == pytest.approx(100_000)


def test_fully_paid_is_zero():
    assert amortized_balance(100_000, 6.0, 360, 360) == pytest.approx(0.0, abs=1e-6)


def test_zero_rate_amortizes_linearly():
    assert amortized_balance(120_000, 0.0, 120, 30) == pytest.approx(90_000)


def test_textbook_example():
    # $200k, 6%, 30y: payment ≈ $1,199.10; after 12 payments ≈ $197,544.
    assert amortized_balance(200_000, 6.0, 360, 12) == pytest.approx(197_544, abs=5)


def test_estimate_ead_below_original_upb():
    cfg = load_config()
    df = pd.DataFrame({"orig_upb": [300_000], "orig_interest_rate": [5.0], "orig_loan_term": [360]})
    ead = estimate_ead(df, cfg)[0]
    assert 0 < ead < 300_000
    assert ead == pytest.approx(
        amortized_balance(300_000, 5.0, 360, int(cfg.ead.expected_default_month))
        * float(cfg.ead.ccf)
    )

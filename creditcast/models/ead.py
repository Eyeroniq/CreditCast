"""EAD — Exposure at Default (Part 3.4).

For a fully-drawn, fully-amortizing mortgage EAD is the outstanding balance at
the moment of default, so the general Credit-Conversion-Factor framework
collapses to EAD = drawn_balance + CCF · undrawn. With no undrawn commitment we
use the **scheduled (amortized) balance** at the expected default month,
scaled by the configured CCF (1.0). Using the origination UPB instead would
overstate exposure — the borrower has already repaid some principal by then.

The hook is left explicit so a revolving/undrawn product can plug in a fitted
CCF model later.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config


def amortized_balance(upb, annual_rate_pct, term_months, months_paid) -> np.ndarray:
    """Remaining principal after `months_paid` level payments.

    B_k = P · [(1+r)^n − (1+r)^k] / [(1+r)^n − 1],  r = annual% / 1200.
    Zero-rate loans amortize linearly: B_k = P · (1 − k/n).
    """
    P = np.asarray(upb, float)
    r = np.asarray(annual_rate_pct, float) / 1200.0
    n = np.asarray(term_months, float)
    k = np.clip(np.asarray(months_paid, float), 0, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        growth_n = (1 + r) ** n
        bal = P * (growth_n - (1 + r) ** k) / (growth_n - 1)
    linear = P * (1 - k / n)
    return np.where(r > 0, bal, linear)


def estimate_ead(df: pd.DataFrame, cfg: Config | None = None) -> np.ndarray:
    """EAD per loan: CCF · scheduled balance at the expected default month."""
    cfg = cfg or load_config()
    ccf = float(cfg.ead.ccf)
    k = int(cfg.ead.expected_default_month)
    bal = amortized_balance(df["orig_upb"], df["orig_interest_rate"],
                            df["orig_loan_term"], k)
    return bal * ccf

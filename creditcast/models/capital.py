"""Regulatory capital — Basel IRB, retail residential mortgages (ROADMAP 5.5).

Expected loss (PD x LGD x EAD) is the average loss a bank prices and provisions
for. Capital covers *unexpected* loss: how much worse a bad year can be, at a
99.9% confidence level, under the Basel single-risk-factor model. For
residential mortgages the asset correlation is fixed at R = 0.15 and there is
no maturity adjustment:

    K   = LGD * N[ (G(PD) + sqrt(R) * G(0.999)) / sqrt(1 - R) ] - PD * LGD
    RWA = 12.5 * K * EAD                       (12.5 = 1 / 8% minimum ratio)

N is the standard normal CDF and G its inverse. `tests/test_capital.py`
reproduces the Basel II framework's published risk-weight table for
residential mortgages (Annex 5) to two decimals.

Floors (config `capital`): Basel III sets a 0.05% PD floor and a 5% LGD floor
for residential mortgages; they apply to the bank's own estimates before the
formula (the reference table is the unfloored function).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from creditcast.config import Config, load_config


def capital_k(pd_hat, lgd_hat, correlation: float = 0.15, confidence: float = 0.999) -> np.ndarray:
    """Capital requirement K per unit of exposure (unfloored Basel function)."""
    p = np.asarray(pd_hat, float)
    lgd = np.asarray(lgd_hat, float)
    if np.any((p <= 0) | (p >= 1)):
        raise ValueError("PD must be in (0, 1) for the IRB formula")
    if np.any((lgd < 0) | (lgd > 1)):
        raise ValueError("LGD must be in [0, 1]")
    r = float(correlation)
    stressed_pd = norm.cdf((norm.ppf(p) + np.sqrt(r) * norm.ppf(confidence)) / np.sqrt(1 - r))
    return np.clip(lgd * stressed_pd - p * lgd, 0.0, None)


def risk_weight(pd_hat, lgd_hat, correlation: float = 0.15, confidence: float = 0.999):
    """Risk weight as a fraction of exposure (12.5 x K): 0.564 = 56.4%."""
    return 12.5 * capital_k(pd_hat, lgd_hat, correlation, confidence)


def irb(pd_hat, lgd_hat, ead, cfg: Config | None = None) -> dict:
    """Floored per-loan K, capital and RWA, plus portfolio totals."""
    cfg = cfg or load_config()
    c = cfg.capital
    p = np.maximum(np.asarray(pd_hat, float), float(c.pd_floor))
    lgd = np.maximum(np.asarray(lgd_hat, float), float(c.lgd_floor))
    ead = np.asarray(ead, float)
    k = capital_k(p, lgd, float(c.correlation), float(c.confidence))
    capital = k * ead
    rwa = 12.5 * capital
    total_ead = float(ead.sum())
    return {
        "k": k,
        "capital": capital,
        "rwa": rwa,
        "total": {
            "capital": float(capital.sum()),
            "rwa": float(rwa.sum()),
            "ead": total_ead,
            "capital_rate": float(capital.sum() / total_ead) if total_ead else 0.0,
            "risk_weight": float(rwa.sum() / total_ead) if total_ead else 0.0,
        },
    }

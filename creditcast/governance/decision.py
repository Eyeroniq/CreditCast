"""Decisioning — cost-based PD threshold + risk bands (Part 10.5).

The approve/decline cutoff is a *business* decision made explicit: pick the PD
threshold that minimizes expected misclassification cost, where a false negative
(approving a defaulter) costs `cost_fn` and a false positive (declining a good
borrower) costs `cost_fp`. For calibrated PDs the optimum is the closed form
PD ≤ cost_fp / (cost_fp + cost_fn) (default, stable); the empirical minimum on
the calibration slice is kept for comparison. Risk bands map the scaled credit
score to rating grades from config.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config


def closed_form_threshold(cfg: Config | None = None) -> float:
    """Bayes-optimal cut-off for *calibrated* PDs: approve while the expected
    cost of approving (cost_fn · PD) is below that of declining
    (cost_fp · (1 − PD)), i.e. PD ≤ cost_fp / (cost_fp + cost_fn)."""
    cfg = cfg or load_config()
    cost_fn = float(cfg.decision.cost_fn)
    cost_fp = float(cfg.decision.cost_fp)
    return cost_fp / (cost_fp + cost_fn)


def default_threshold(
    pd_hat, y_true, cfg: Config | None = None, method: str | None = None
) -> float:
    """The decision cut-off, by `decision.threshold_method` (or `method`)."""
    cfg = cfg or load_config()
    method = method or str(cfg.decision.get("threshold_method", "empirical"))
    if method == "closed_form":
        return closed_form_threshold(cfg)
    if method != "empirical":
        raise ValueError(f"unknown threshold method: {method}")
    return empirical_threshold(pd_hat, y_true, cfg)


def empirical_threshold(pd_hat, y_true, cfg: Config | None = None) -> float:
    """PD cutoff minimizing realised cost (cost_fn·FN + cost_fp·FP) on a sample."""
    cfg = cfg or load_config()
    cost_fn = float(cfg.decision.cost_fn)
    cost_fp = float(cfg.decision.cost_fp)
    p = np.asarray(pd_hat, float)
    y = np.asarray(y_true, int)

    candidates = np.quantile(p, np.linspace(0.01, 0.99, 99))
    best_thr, best_cost = candidates[0], np.inf
    for thr in candidates:
        approve = p <= thr
        fn = int(((y == 1) & approve).sum())  # approved a defaulter
        fp = int(((y == 0) & ~approve).sum())  # declined a good borrower
        cost = cost_fn * fn + cost_fp * fp
        if cost < best_cost:
            best_cost, best_thr = cost, float(thr)
    return best_thr


def assign_band(score, cfg: Config | None = None) -> np.ndarray | str:
    """Map credit score -> rating grade using configured band floors."""
    cfg = cfg or load_config()
    # Ascending by floor so each higher-grade floor overwrites the lower grade:
    # every loan ends up in the highest band it qualifies for.
    bands = sorted(cfg.decision.bands, key=lambda b: float(b["min_score"]))
    scalar = np.isscalar(score)
    s = np.atleast_1d(np.asarray(score, float))
    out = np.empty(s.shape, dtype=object)
    out[:] = bands[0]["name"]
    for b in bands:
        out[s >= float(b["min_score"])] = b["name"]
    return out[0] if scalar else out


def decide(pd_hat, threshold: float) -> np.ndarray | str:
    p = np.asarray(pd_hat, float)
    decision = np.where(p <= threshold, "approve", "decline")
    return decision.item() if decision.ndim == 0 else decision


def decision_summary(
    scored: pd.DataFrame, pd_col: str, threshold: float, cfg: Config | None = None
) -> dict:
    cfg = cfg or load_config()
    p = scored[pd_col].to_numpy()
    approve = p <= threshold
    bands = assign_band(scored["credit_score"].to_numpy(), cfg)
    band_counts = pd.Series(bands).value_counts().to_dict()
    return {
        "threshold": float(threshold),
        "approval_rate": float(approve.mean()),
        "approved_default_rate": float(scored.loc[approve, "default_12m"].mean()),
        "declined_default_rate": float(scored.loc[~approve, "default_12m"].mean()),
        "band_distribution": {k: int(v) for k, v in band_counts.items()},
    }


def threshold_curve(
    scored: pd.DataFrame, pd_col: str, cfg: Config | None = None, grid=None
) -> list[dict]:
    """What-if over the approval cut-off (ROADMAP 6.2.5), for the cockpit slider.

    For each candidate threshold: approval rate, default rate among approved
    loans, share of all defaults that would be approved, expected loss of the
    approved book (money and bps of its exposure), and fairness — approval rate
    per protected group and the minimum disparate-impact ratio vs the
    privileged group. Descriptive only: the policy threshold is still chosen on
    the calibration slice, never on these outcomes.
    """
    cfg = cfg or load_config()
    grid = np.round(np.arange(0.005, 0.2501, 0.0025), 4) if grid is None else np.asarray(grid)
    p = scored[pd_col].to_numpy(float)
    y = scored["default_12m"].to_numpy(int)
    el = scored["expected_loss"].to_numpy(float)
    ead = scored["ead"].to_numpy(float)
    attr = str(cfg.fairness.protected_attribute)
    groups = scored[attr].astype(str).to_numpy()
    names = sorted(set(groups))
    priv = str(cfg.fairness.privileged_group)
    n_def = max(int(y.sum()), 1)

    out = []
    for thr in grid:
        a = p <= thr
        n_a = int(a.sum())
        by_group = {g: float(a[groups == g].mean()) for g in names}
        ref = by_group.get(priv) or max(by_group.values()) or 1.0
        di = {g: (r / ref if ref else 0.0) for g, r in by_group.items()}
        out.append(
            {
                "threshold": float(thr),
                "approval_rate": float(a.mean()),
                "approved_default_rate": float(y[a].mean()) if n_a else 0.0,
                "defaults_approved_share": float(y[a].sum() / n_def),
                "expected_loss_approved": float(el[a].sum()),
                "el_bps_approved": float(el[a].sum() / ead[a].sum() * 1e4) if n_a else 0.0,
                "di_min": float(min(di.values())),
                "group_approval": by_group,
            }
        )
    return out

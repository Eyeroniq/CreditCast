"""What-if / counterfactual search (ROADMAP 6.2.2).

For a declined applicant: what is the smallest *single* change that would get
them approved? Only levers an applicant can actually pull are searched —
debt-to-income, down payment (loan-to-value), borrowing less, and credit score.
Property type, purpose, etc. are never suggested.

The model is not guaranteed to be monotonic (e.g. very low DTI can carry extra
risk), so each lever is scanned on a grid from the current value toward its
better bound, the first approving grid point is refined on a finer grid, and
the final suggestion is re-scored to confirm it really flips the decision.
Three batched model calls in total, no SHAP — fast enough for live UI use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

N_COARSE = 40
N_FINE = 20


@dataclass(frozen=True)
class Lever:
    feature: str
    label: str
    bound: Callable[[dict], float]   # the best plausible value for this applicant
    step: float                      # display/rounding precision
    better: int                      # -1: lower is better, +1: higher is better
    apply: Callable[[dict, float], dict]
    describe: Callable[[dict, float], str]


def _set(field: str) -> Callable[[dict, float], dict]:
    return lambda app, v: {**app, field: v}


def _borrow_less(app: dict, upb: float) -> dict:
    # Same home value: a smaller loan lowers loan-to-value proportionally.
    ltv = app["ltv"] * upb / app["orig_upb"]
    return {**app, "orig_upb": upb, "ltv": max(1, int(round(ltv)))}


def _money(v: float) -> str:
    return f"${v:,.0f}"


LEVERS = [
    Lever("dti", "Lower debt-to-income", lambda a: 10.0, 0.5, -1, _set("dti"),
          lambda a, v: f"Lower debt-to-income from {a['dti']:g}% to {v:g}% "
                       "(pay down other debts or show more income)"),
    Lever("ltv", "Bigger down payment", lambda a: 30.0, 1, -1, _set("ltv"),
          lambda a, v: f"Lower loan-to-value from {a['ltv']:g}% to {v:g}% "
                       "(a larger down payment)"),
    Lever("orig_upb", "Borrow less", lambda a: max(40_000.0, a["orig_upb"] * 0.5), 1000, -1,
          _borrow_less,
          lambda a, v: f"Borrow {_money(v)} instead of {_money(a['orig_upb'])} "
                       f"(loan-to-value {a['ltv']:g}% → {_borrow_less(a, v)['ltv']}%)"),
    Lever("fico", "Improve credit score", lambda a: 850.0, 1, +1, _set("fico"),
          lambda a, v: f"Raise credit score from {a['fico']:g} to {v:g}"),
]


def _round_favourable(v: float, step: float, better: int) -> float:
    """Round to the display step in the applicant-friendly direction."""
    q = v / step
    q = np.floor(q) if better < 0 else np.ceil(q)
    out = q * step
    return float(int(out)) if float(step).is_integer() else round(float(out), 6)


def _normalise(lever: Lever, app: dict, v: float) -> dict:
    """Apply a lever value, respecting integer fields."""
    v = _round_favourable(v, lever.step, lever.better)
    return lever.apply(app, int(v) if lever.feature in ("fico", "ltv", "orig_upb") else v)


def what_if(applicant: dict, pd_batch: Callable[[list[dict]], np.ndarray],
            threshold: float, max_options: int = 3) -> dict:
    """Smallest single changes that flip a decline to an approval.

    `pd_batch(rows) -> PDs` is the champion model (ModelBundle.pd_batch).
    """
    base_pd = float(pd_batch([applicant])[0])
    if base_pd <= threshold:
        return {"already_approved": True, "pd": base_pd, "threshold": threshold,
                "options": [], "message": "Already approved — no change needed."}

    # ---- 1. coarse scan: every lever, one batch -------------------------------
    grids, rows = [], []
    for lv in LEVERS:
        cur, best = float(applicant[lv.feature]), float(lv.bound(applicant))
        if (best - cur) * lv.better <= 0:            # already at/after the bound
            grids.append(np.array([]))
            continue
        g = np.linspace(cur, best, N_COARSE + 1)[1:]
        grids.append(g)
        rows += [lv.apply(applicant, v) for v in g]
    pds = pd_batch(rows) if rows else np.array([])

    # ---- 2. refine between the last failing and first passing point ----------
    candidates, fine_rows, fine_grids, i = [], [], [], 0
    for lv, g in zip(LEVERS, grids):
        seg = pds[i:i + len(g)]
        i += len(g)
        hit = np.flatnonzero(seg <= threshold)
        if not len(hit):
            continue
        k = int(hit[0])
        lo = float(applicant[lv.feature]) if k == 0 else float(g[k - 1])
        fg = np.linspace(lo, float(g[k]), N_FINE + 1)[1:]
        candidates.append(lv)
        fine_grids.append(fg)
        fine_rows += [lv.apply(applicant, v) for v in fg]
    fpds = pd_batch(fine_rows) if fine_rows else np.array([])

    # ---- 3. round, then confirm each suggestion really approves ---------------
    proposals, j = [], 0
    for lv, fg in zip(candidates, fine_grids):
        seg = fpds[j:j + len(fg)]
        j += len(fg)
        first = int(np.flatnonzero(seg <= threshold)[0])
        proposals.append((lv, _normalise(lv, applicant, float(fg[first]))))
    confirm = pd_batch([p for _, p in proposals]) if proposals else np.array([])

    options = []
    for (lv, new_app), p in zip(proposals, confirm):
        if p > threshold:            # rounding crossed back over the line
            continue
        cur, target = float(applicant[lv.feature]), float(new_app[lv.feature])
        span = abs(float(lv.bound(applicant)) - cur) or 1.0
        options.append({
            "feature": lv.feature, "lever": lv.label,
            "current": cur, "target": target,
            "effort": round(abs(target - cur) / span, 3),   # share of the lever's range
            "pd_after": float(p),
            "text": lv.describe(applicant, target),
            "applicant": new_app,                            # lets the UI apply it
        })
    options.sort(key=lambda o: o["effort"])
    options = options[:max_options]
    return {
        "already_approved": False, "pd": base_pd, "threshold": threshold,
        "options": options,
        "message": (None if options else
                    "No single change is enough — this application would need "
                    "several improvements together."),
    }

"""Less-discriminatory-alternative (LDA) search (ROADMAP 5.6).

US fair-lending practice asks: is there another model, about as accurate, that
treats protected groups more evenly? This module retrains variants of one base
model (logistic regression on the model features, so the variants differ only
in the mitigation) and measures each on the out-of-time book:

- **Gini**, and
- the **lowest approval-rate ratio** of any group to the privileged group
  (the four-fifths rule), with every variant approving the *same share* of
  applicants as the live policy, so fairness differences aren't just a looser
  or stricter cut-off.

Variants:
- `baseline`: all features.
- `drop_dti`: without debt-to-income and the LTV x DTI interaction (DTI carries
  part of the historical gap between groups in this data).
- `cap_fico`: credit score capped at 720 (differences among high scores add
  little risk information but carry group differences).
- `reweighing`: training rows weighted so group and outcome are independent
  (Kamiran & Calders); the model never sees race.
- `fairlearn_dp`: fairlearn's exponentiated-gradient reduction towards equal
  approval rates. It uses race *during training only* (not to score anyone);
  some lenders' counsel won't accept even that, so it is reported, not
  automatically chosen.

Group-specific thresholds are never considered: they are illegal in lending.
The chosen LDA is the variant with the best fairness whose Gini is within
`fairness.lda_gini_tolerance` of the baseline (fairlearn excluded).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import categorical_columns, numeric_columns

VARIANTS = ["baseline", "drop_dti", "cap_fico", "reweighing", "fairlearn_dp"]
LABELS = {
    "baseline": "Baseline (all features)",
    "drop_dti": "Without debt-to-income",
    "cap_fico": "Credit score capped at 720",
    "reweighing": "Reweighing (group-balanced training)",
    "fairlearn_dp": "Fairness-constrained training (fairlearn)",
}
FICO_CAP = 720


def _pipeline(numeric: list[str], seed: int):
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_columns()),
        ]
    )
    return make_pipeline(pre, LogisticRegression(max_iter=2000, random_state=seed))


def reweighing_weights(group: pd.Series, y: pd.Series) -> np.ndarray:
    """Kamiran & Calders: w(g, y) = P(g) P(y) / P(g, y)."""
    df = pd.DataFrame({"g": group.to_numpy(), "y": y.to_numpy()})
    p_g = df["g"].value_counts(normalize=True)
    p_y = df["y"].value_counts(normalize=True)
    p_gy = df.value_counts(normalize=True)
    return np.array([p_g[g] * p_y[v] / p_gy[(g, v)] for g, v in zip(df["g"], df["y"], strict=True)])


def approval_ratios(pd_hat: np.ndarray, group: pd.Series, approve_share: float, privileged: str):
    """Approve the `approve_share` lowest-risk applicants (one cut-off for
    everyone); return each group's approval rate / the privileged group's."""
    cut = np.quantile(pd_hat, approve_share)
    approved = pd_hat <= cut
    rates = pd.Series(approved).groupby(group.to_numpy()).mean()
    return (rates / rates[privileged]).drop(privileged)


def _gini(y, p) -> float:
    return float(2 * roc_auc_score(y, p) - 1)


def run_search(cfg: Config | None = None) -> dict:
    from creditcast.pipeline.split import make_split

    cfg = cfg or load_config()
    seed = int(cfg.run.seed)
    protected = str(cfg.fairness.protected_attribute)
    privileged = str(cfg.fairness.privileged_group)
    split = make_split(cfg=cfg)
    train = pd.concat([split.train, split.calib, split.valid], ignore_index=True)
    test = split.test
    y_train = train["default_12m"].astype(int)
    y_test = test["default_12m"].to_numpy(int)

    gov = json.loads((cfg.path("artifacts") / "governance_report.json").read_text())
    approve_share = float(gov["decision"]["approval_rate"])

    num_all = numeric_columns()
    results: dict[str, dict[str, Any]] = {}

    def evaluate(name: str, pd_hat: np.ndarray) -> None:
        ratios = approval_ratios(pd_hat, test[protected], approve_share, privileged)
        results[name] = {
            "label": LABELS[name],
            "gini": _gini(y_test, pd_hat),
            "min_ratio": float(ratios.min()),
            "lowest_group": str(ratios.idxmin()),
            "ratios": {k: float(v) for k, v in ratios.items()},
        }

    def fit_predict(numeric, X_tr, X_te, weights=None) -> np.ndarray:
        m = _pipeline(numeric, seed)
        m.fit(X_tr, y_train, logisticregression__sample_weight=weights)
        return m.predict_proba(X_te)[:, 1]

    cols = num_all + categorical_columns()
    evaluate("baseline", fit_predict(num_all, train[cols], test[cols]))

    no_dti = [c for c in num_all if c not in ("dti", "ltv_dti")]
    cols_nd = no_dti + categorical_columns()
    evaluate("drop_dti", fit_predict(no_dti, train[cols_nd], test[cols_nd]))

    capped_tr, capped_te = train[cols].copy(), test[cols].copy()
    capped_tr["fico"] = capped_tr["fico"].clip(upper=FICO_CAP)
    capped_te["fico"] = capped_te["fico"].clip(upper=FICO_CAP)
    evaluate("cap_fico", fit_predict(num_all, capped_tr, capped_te))

    w = reweighing_weights(train[protected], y_train)
    evaluate("reweighing", fit_predict(num_all, train[cols], test[cols], w))

    thr = float(gov["decision"]["threshold"])
    evaluate("fairlearn_dp", _fairlearn(num_all, train, test, cols, y_train, protected, seed, thr))

    base = results["baseline"]
    tol = float(cfg.fairness.lda_gini_tolerance)
    eligible = [
        k for k in VARIANTS if k != "fairlearn_dp" and results[k]["gini"] >= base["gini"] - tol
    ]
    chosen = max(eligible, key=lambda k: results[k]["min_ratio"])
    return {
        "stamp": run_stamp(),
        "approval_share": approve_share,
        "floor": float(cfg.fairness.di_ratio_min),
        "gini_tolerance": tol,
        "variants": results,
        "chosen": chosen,
        "chosen_meets_floor": results[chosen]["min_ratio"] >= float(cfg.fairness.di_ratio_min),
    }


def _fairlearn(numeric, train, test, cols, y_train, protected, seed, threshold) -> np.ndarray:
    """Exponentiated-gradient reduction towards demographic parity; returns the
    randomised classifier's probability of being 'bad' (higher = riskier).

    The reduction constrains yes/no predictions at a 50% cut, and almost no
    loan reaches a 50% default probability, so unweighted it would be satisfied
    trivially. Weighting defaults by (1 - t) / t moves that 50% line to the
    policy's PD limit t, so parity is enforced at the actual decision."""
    from fairlearn.reductions import DemographicParity, ExponentiatedGradient

    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_columns()),
        ]
    )
    X_tr = pre.fit_transform(train[cols])
    X_te = pre.transform(test[cols])
    w_bad = (1 - threshold) / threshold
    eg = ExponentiatedGradient(
        LogisticRegression(max_iter=2000, random_state=seed, class_weight={0: 1.0, 1: w_bad}),
        constraints=DemographicParity(difference_bound=0.02),
        max_iter=40,
    )
    eg.fit(X_tr, y_train, sensitive_features=train[protected].to_numpy())
    # the randomised classifier's probability of predicting "default"
    return eg._pmf_predict(X_te)[:, 1]


def build_report(cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    out = cfg.path("artifacts") / "lda_report.json"
    out.write_text(json.dumps(run_search(cfg), indent=2))
    from creditcast.governance.report import refresh_model_card

    refresh_model_card(cfg)  # the card gains the trade-off table
    return out


if __name__ == "__main__":
    r = json.loads(build_report().read_text())
    for k, v in r["variants"].items():
        star = " <- chosen" if k == r["chosen"] else ""
        print(
            f"{k:<14} Gini {v['gini']:.4f}  min ratio {v['min_ratio']:.3f} ({v['lowest_group']}){star}"
        )

"""Reject inference study (ROADMAP 5.4).

A lender only learns outcomes for loans it approved, so a model built on booked
loans has never seen how the applicants it turned away would have performed.
The synthetic data knows every applicant's outcome, so the bias can be measured
directly:

1. A **historical policy** decides who was approved in the training years;
   rejects' outcomes are hidden. Two versions (`reject_inference` in config):
   - **rules only**: credit-score / DTI / LTV cut-offs. The decline used only
     information the model also sees, so (in theory) ignoring rejects is
     unbiased: the "missing at random" case.
   - **rules + underwriter judgment**: on top, underwriters turned down part
     of the applicants who were going to default (and a few who weren't),
     using information the model never sees. Booked loans then look safer
     than their features suggest: the case reject inference exists for.
2. Three ways to build the model from that data, all the same logistic model
   on the same features:
   - **ignore**: train on approved loans only;
   - **parceling**: score rejects with the ignore-model, then label each one
     bad at random with probability PD x `inflation` (rejects are usually
     worse than the booked-loan model thinks);
   - **fuzzy augmentation**: add every reject twice, as bad with weight
     PD x inflation and as good with the remaining weight.
   An **oracle** trained on everyone (impossible in real life) is the ceiling.
3. All are judged on the whole through-the-door population of the
   out-of-time years (what the model will actually face): Gini, and how far
   predicted default rates miss among the applicants the old policy rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import categorical_columns, numeric_columns


def historical_policy(df: pd.DataFrame, policy) -> np.ndarray:
    """True where the old rule-based policy would have approved."""
    return (
        (df["fico"] >= float(policy.min_fico))
        & (df["dti"] <= float(policy.max_dti))
        & (df["ltv"] <= float(policy.max_ltv))
    ).to_numpy()


def underwriter_judgment(df: pd.DataFrame, judgment, rng: np.random.Generator) -> np.ndarray:
    """True where underwriters would still have approved: they declined a share
    of the eventual defaulters (`catch_bad`) and of the good loans
    (`false_alarm`), using information outside the model."""
    bad = df["default_12m"].to_numpy(int) == 1
    decline_p = np.where(bad, float(judgment.catch_bad), float(judgment.false_alarm))
    return rng.random(len(df)) >= decline_p


def _model(seed: int):
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), numeric_columns()),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_columns()),
        ]
    )
    return make_pipeline(pre, LogisticRegression(max_iter=2000, random_state=seed))


def _fit(X: pd.DataFrame, y: np.ndarray, w: np.ndarray | None, seed: int):
    m = _model(seed)
    m.fit(X, y, logisticregression__sample_weight=w)
    return m


def _gini(y, p) -> float:
    return float(2 * roc_auc_score(y, p) - 1)


def run_study(cfg: Config | None = None) -> dict:
    """Both policy scenarios; the chosen method comes from the judgment one,
    the realistic case."""
    cfg = cfg or load_config()
    scenarios = {
        "rules_only": _scenario(cfg, judgment=False),
        "rules_and_judgment": _scenario(cfg, judgment=True),
    }
    return {
        "stamp": run_stamp(),
        "inflation": float(cfg.reject_inference.inflation),
        "scenarios": scenarios,
        "chosen": scenarios["rules_and_judgment"]["chosen"],
        "note": (
            "Study only: the production champion trains on every loan, since the "
            "synthetic book has outcomes for all of them. With real booked-loan "
            "data, the chosen method would be applied before training."
        ),
    }


def _scenario(cfg: Config, judgment: bool) -> dict:
    from creditcast.pipeline.split import make_split

    rc = cfg.reject_inference
    seed = int(cfg.run.seed)
    rng = np.random.default_rng(seed + 21)
    split = make_split(cfg=cfg)
    feats = numeric_columns() + categorical_columns()

    train = pd.concat([split.train, split.calib, split.valid], ignore_index=True)
    approved = historical_policy(train, rc.policy)
    if judgment:
        approved = approved & underwriter_judgment(train, rc.judgment, rng)
    acc, rej = train[approved], train[~approved]
    y_acc = acc["default_12m"].to_numpy(int)

    ignore = _fit(acc[feats], y_acc, None, seed)
    p_rej = np.clip(ignore.predict_proba(rej[feats])[:, 1] * float(rc.inflation), 0, 1)

    # parceling: one random draw per reject
    parcel_y = (rng.random(len(rej)) < p_rej).astype(int)
    parceling = _fit(
        pd.concat([acc[feats], rej[feats]]), np.concatenate([y_acc, parcel_y]), None, seed
    )
    # fuzzy augmentation: each reject as bad (weight p) and good (weight 1 - p)
    fuzzy = _fit(
        pd.concat([acc[feats], rej[feats], rej[feats]]),
        np.concatenate([y_acc, np.ones(len(rej), int), np.zeros(len(rej), int)]),
        np.concatenate([np.ones(len(acc)), p_rej, 1 - p_rej]),
        seed,
    )
    oracle = _fit(train[feats], train["default_12m"].to_numpy(int), None, seed)

    # judge on the whole out-of-time through-the-door population
    test = split.test
    y_test = test["default_12m"].to_numpy(int)
    # judged where the model will be used: the old rules' rejects (the same
    # applicants in both scenarios, so the numbers compare)
    old_rej = ~historical_policy(test, rc.policy)
    methods = {"ignore": ignore, "parceling": parceling, "fuzzy": fuzzy, "oracle": oracle}
    results = {}
    for name, m in methods.items():
        p = m.predict_proba(test[feats])[:, 1]
        results[name] = {
            "gini_all": _gini(y_test, p),
            "gini_old_rejects": _gini(y_test[old_rej], p[old_rej]),
            "predicted_rate_old_rejects": float(p[old_rej].mean()),
            "predicted_rate_old_approved": float(p[~old_rej].mean()),
        }
    actual_rej = float(y_test[old_rej].mean())
    for r in results.values():
        r["miss_old_rejects_pts"] = (r["predicted_rate_old_rejects"] - actual_rej) * 100

    # choose: smallest miss on the old rejects among real-world methods, Gini as tiebreak
    candidates = ["ignore", "parceling", "fuzzy"]
    chosen = min(
        candidates,
        key=lambda k: (round(abs(results[k]["miss_old_rejects_pts"]), 1), -results[k]["gini_all"]),
    )
    return {
        "judgment": judgment,
        "policy": {
            "min_fico": float(rc.policy.min_fico),
            "max_dti": float(rc.policy.max_dti),
            "max_ltv": float(rc.policy.max_ltv),
        },
        "inflation": float(rc.inflation),
        "train": {
            "approved": int(approved.sum()),
            "rejected": int((~approved).sum()),
            "reject_rate": float((~approved).mean()),
            "approved_default_rate": float(y_acc.mean()),
            "rejected_default_rate_hidden": float(rej["default_12m"].mean()),
        },
        "test": {
            "applicants": int(len(test)),
            "old_rejects": int(old_rej.sum()),
            "actual_rate_old_rejects": actual_rej,
            "actual_rate_old_approved": float(y_test[~old_rej].mean()),
        },
        "methods": results,
        "chosen": chosen,
    }


def build_report(cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    out = cfg.path("artifacts") / "reject_inference.json"
    out.write_text(json.dumps(run_study(cfg), indent=2))
    return out


if __name__ == "__main__":
    r = json.loads(build_report().read_text())
    for name, s in r["scenarios"].items():
        print(name, "| rejected", f"{s['train']['reject_rate']:.0%}", "| chosen", s["chosen"])
        for m, v in s["methods"].items():
            print(
                f"   {m:<10} Gini {v['gini_all']:.4f}  miss on old rejects {v['miss_old_rejects_pts']:+.2f} pts"
            )

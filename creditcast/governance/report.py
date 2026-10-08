"""Governance aggregator — one report the model-governance function expects.

Pulls together the decision policy, fairness analysis, global SHAP drivers, and
a worked adverse-action example, then emits:
  - artifacts/governance_report.json  (dashboard Governance screen)
  - governance/model_card.md          (the one-page model card artifact)
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import feature_columns
from creditcast.governance import decision, explain, fairness, reason_codes, shap_explain
from creditcast.pipeline.split import make_split

CHAMPION_PD = "pd_champion"  # the configured champion's calibrated PD (train.py)
CHAMPION_LABEL = {
    "challenger": "challenger (LightGBM, {cal}-calibrated)",
    "scorecard": "scorecard (WoE logistic, {cal}-calibrated)",
}


def build_governance(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    art = cfg.path("artifacts")
    scored = pd.read_parquet(art / "test_scored.parquet")
    train_metrics = json.loads((art / "train_metrics.json").read_text())
    validation = json.loads((art / "validation_report.json").read_text())

    # The cut-off is a *decision*, so it is chosen on the calibration slice
    # (cross-fitted PDs) — never on the OOT test outcomes it is reported on.
    calib = pd.read_parquet(art / "calib_scored.parquet")
    thr = decision.default_threshold(calib[CHAMPION_PD], calib["default_12m"], cfg)
    thr_alternatives = {
        "closed_form": decision.closed_form_threshold(cfg),
        "empirical_calib": decision.empirical_threshold(
            calib[CHAMPION_PD], calib["default_12m"], cfg
        ),
    }
    dec_summary = decision.decision_summary(scored, CHAMPION_PD, thr, cfg)
    fair = fairness.fairness_report(scored, CHAMPION_PD, thr, cfg)

    # Global SHAP drivers (precomputed artifact, refresh if missing)
    shap_path = art / "shap_global.json"
    if not shap_path.exists():
        shap_explain.save_global(cfg)
    shap_global = json.loads(shap_path.read_text())

    # Worked adverse-action example: a representative declined applicant
    test = make_split(cfg=cfg).test
    test = test.merge(scored[["loan_id", CHAMPION_PD, "credit_score"]], on="loan_id")
    declined = test[test[CHAMPION_PD] > thr].sort_values(CHAMPION_PD, ascending=False)
    example = None
    if len(declined):
        row = declined.iloc[[len(declined) // 2]]  # a median-risk decline
        local = explain.local_drivers(row[feature_columns()], cfg)
        codes = reason_codes.reason_codes(local, top_n=4)
        example = {
            "loan_id": int(row["loan_id"].iloc[0]),
            "pd": float(row[CHAMPION_PD].iloc[0]),
            "credit_score": float(row["credit_score"].iloc[0]),
            "band": decision.assign_band(row["credit_score"].iloc[0], cfg),
            "decision": "decline",
            "reason_codes": codes,
            "letter": reason_codes.narrate(codes, "decline"),
        }

    report = {
        "stamp": run_stamp(),
        "champion_model": CHAMPION_LABEL[str(cfg.decision.champion)].format(
            cal=cfg.calibration.method
        ),
        "decision": {
            **dec_summary,
            "threshold_method": str(cfg.decision.threshold_method),
            "threshold_source": "calib (cross-fitted)",
            "threshold_alternatives": thr_alternatives,
        },
        "fairness": fair,
        "shap_global": shap_global,
        "adverse_action_example": example,
    }
    (art / "governance_report.json").write_text(json.dumps(report, indent=2, default=float))

    # Approval-limit what-if curve for the cockpit slider (6.2.5)
    curve = {
        "policy_threshold": float(thr),
        "alternatives": thr_alternatives,
        "di_floor": float(cfg.fairness.di_ratio_min),
        "privileged_group": str(cfg.fairness.privileged_group),
        "points": decision.threshold_curve(scored, CHAMPION_PD, cfg),
    }
    (art / "threshold_curve.json").write_text(json.dumps(curve, default=float))
    _write_model_card(report, train_metrics, validation, cfg)
    return report


def _write_model_card(gov: dict, tm: dict, val: dict, cfg: Config) -> None:
    b = val["benchmark"]
    el = tm["expected_loss"]
    fair = gov["fairness"]
    di = fair["di_ratio_min_observed"]
    sc_gini = val["models"]["scorecard"]["discrimination"]["gini"]
    ch_gini = val["models"]["challenger"]["discrimination"]["gini"]
    ch_cal = val["models"]["challenger"]["calibration"]
    top_drivers = ", ".join(d["feature"] for d in gov["shap_global"][:5])
    s = gov["stamp"]

    card = f"""# Model Card — CreditCast PD/LGD/EAD Expected-Loss Model

> Auto-generated. data_version=`{s["data_version"]}` · code_version=`{s["code_version"]}` · seed=`{s["seed"]}`

## 1. Model details
- **Purpose:** Estimate 12-month Probability of Default (PD), Loss Given Default
  (LGD), Exposure at Default (EAD) and combine them into Expected Loss
  (EL = PD × LGD × EAD) for a residential-mortgage portfolio.
- **Models:** (A) regulatory **WoE/IV logistic scorecard**; (B) **LightGBM
  challenger**, {cfg.calibration.method}-calibrated. Champion for EL/decisioning: **{gov["champion_model"]}**.
- **Decision threshold:** approve if PD ≤ {gov["decision"]["threshold"]:.4f}
  (method `{gov["decision"]["threshold_method"]}`, FN:FP = {cfg.decision.cost_fn:g}:{cfg.decision.cost_fp:g};
  closed-form {gov["decision"]["threshold_alternatives"]["closed_form"]:.4f}, empirical on calib
  {gov["decision"]["threshold_alternatives"]["empirical_calib"]:.4f}). Never chosen on the OOT
  test outcomes it is evaluated on. PDs are floored at {cfg.calibration.pd_floor:g}.
- **Methodology:** Global Basel/IRB framework (jurisdiction-agnostic). Data is the
  Freddie Mac Single-Family schema (synthetic generator standing in for the GSE
  files; real files drop into the same pipeline).

## 2. Intended use
- Portfolio Expected-Loss estimation, IFRS-9-style provisioning, and lending
  decision support, with human oversight. **Not** for automated decisions without
  review, and not validated outside US-style residential mortgages.

## 3. Data & leakage discipline
- Point-in-time features (origination only), forward-looking 12-month target,
  **out-of-time** split (train ≤ {cfg.target.oot.train_vintage_end}, test ≥
  {cfg.target.oot.test_vintage_start}). No performance data leaks into features.
- Protected attribute (`borrower_race`) is **never** a model input.

## 4. Performance (out-of-time)
| Metric | Scorecard | Challenger |
|---|---|---|
| Gini | {sc_gini:.4f} | {ch_gini:.4f} |
| KS | {val["models"]["scorecard"]["discrimination"]["ks"]:.4f} | {val["models"]["challenger"]["discrimination"]["ks"]:.4f} |
| Calibration max band error | {val["models"]["scorecard"]["calibration"]["max_band_error"]:.4f} | {ch_cal["max_band_error"]:.4f} |
| ECE | {val["models"]["scorecard"]["calibration"]["ece"]:.4f} | {ch_cal["ece"]:.4f} |

- **Benchmark:** challenger − scorecard Gini gap = {b["gini_gap"]:+.4f}. {b["verdict"]}
- **Top global drivers (SHAP):** {top_drivers}.
- **Portfolio:** EL ≈ {el["portfolio_el"]:,.0f} on EAD {el["total_ead"]:,.0f}
  (≈ {el["el_rate_bps"]:.0f} bps); mean PD {el["mean_pd"]:.2%}, mean LGD {el["mean_lgd_hat"]:.2%}.

## 5. Fairness
- Disparate-impact (4/5ths) at the decision threshold: min ratio **{di:.3f}**
  (floor {fair["di_ratio_floor"]}) → **{"PASS" if fair["passes_four_fifths"] else "REVIEW"}**.
- Max equal-opportunity difference: {fair["max_equal_opportunity_diff"]:.3f}.
- **Discussion:** the model excludes race, yet neutral features (e.g. credit
  score, DTI) proxy historical disparity, producing disparate impact. Mitigation
  options: feature review, reject-option / fairness-constrained training
  (fairlearn), and monitoring — *not* group-specific thresholds (illegal in
  lending). Surfacing and tracking this is a regulatory expectation (EU AI Act
  high-risk credit scoring).

## 6. Limitations
- Synthetic data calibrated to plausible mortgage behaviour, not a specific
  institution's book. Macro scenarios are implicit in vintages, not modelled
  explicitly.
- LGD is trained only on *resolved* defaults ({tm["lgd_population"]["train_resolved_defaults"]:,} of {tm["lgd_population"]["train_defaults"]:,}
  training defaults; workout window {cfg.lgd.workout_window_months} months).
- Labels are right-censoring-aware (policy: `{cfg.target.censoring}`).
- EAD is the scheduled amortized balance after {cfg.ead.expected_default_month} payments.

## 7. Monitoring & governance
- CI performance gates (Gini / calibration / PSI). Scheduled PSI/CSI drift
  monitoring vs the training baseline. MLflow tracking + model registry for
  reproducibility. Every artifact stamped with code+data version and seed.
"""
    out = (
        cfg.path("model_card")
        if "model_card" in cfg["paths"]
        else Path(__file__).resolve().parent / "model_card.md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(card, encoding="utf-8")


if __name__ == "__main__":
    r = build_governance()
    f = r["fairness"]
    print(
        f"[governance] threshold={r['decision']['threshold']:.4f} "
        f"approval={r['decision']['approval_rate']:.1%} | "
        f"min DI={f['di_ratio_min_observed']:.3f} "
        f"-> {'PASS' if f['passes_four_fifths'] else 'REVIEW'}"
    )
    print(f"[governance] model card -> {load_config().path('model_card')}")
    if r["adverse_action_example"]:
        print("[governance] sample adverse-action reasons:")
        for c in r["adverse_action_example"]["reason_codes"]:
            print(f"    {c['rank']}. {c['reason']}")

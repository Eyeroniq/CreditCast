# Model Card — CreditCast PD/LGD/EAD Expected-Loss Model

> Auto-generated. data_version=`synthetic-v1` · code_version=`0.1.0` · seed=`42`

## 1. Model details
- **Purpose:** Estimate 12-month Probability of Default (PD), Loss Given Default
  (LGD), Exposure at Default (EAD) and combine them into Expected Loss
  (EL = PD × LGD × EAD) for a residential-mortgage portfolio.
- **Models:** (A) regulatory **WoE/IV logistic scorecard**; (B) **LightGBM
  challenger**, isotonic-calibrated. Champion for EL/decisioning: **challenger (LightGBM, isotonic-calibrated)**.
- **Decision threshold:** approve if PD ≤ 0.0344 (cost-minimizing,
  FN:FP = 15:1), chosen on the calibration slice —
  never on the OOT test outcomes it is evaluated on.
- **Methodology:** Global Basel/IRB framework (jurisdiction-agnostic). Data is the
  Freddie Mac Single-Family schema (synthetic generator standing in for the GSE
  files; real files drop into the same pipeline).

## 2. Intended use
- Portfolio Expected-Loss estimation, IFRS-9-style provisioning, and lending
  decision support, with human oversight. **Not** for automated decisions without
  review, and not validated outside US-style residential mortgages.

## 3. Data & leakage discipline
- Point-in-time features (origination only), forward-looking 12-month target,
  **out-of-time** split (train ≤ 2019-12, test ≥
  2020-01). No performance data leaks into features.
- Protected attribute (`borrower_race`) is **never** a model input.

## 4. Performance (out-of-time)
| Metric | Scorecard | Challenger |
|---|---|---|
| Gini | 0.4483 | 0.4327 |
| KS | 0.3401 | 0.3209 |
| Calibration max band error | 0.0221 | 0.0169 |
| ECE | 0.0080 | 0.0069 |

- **Benchmark:** challenger − scorecard Gini gap = -0.0156. Negligible accuracy gap — the interpretable scorecard is fully competitive. Deploy the scorecard; retain the challenger as an ongoing benchmark.
- **Top global drivers (SHAP):** fico, ltv_dti, ltv, occupancy_status, orig_interest_rate.
- **Portfolio:** EL ≈ 68,124,889 on EAD 4,082,620,862
  (≈ 167 bps); mean PD 4.32%, mean LGD 35.76%.

## 5. Fairness
- Disparate-impact (4/5ths) at the decision threshold: min ratio **0.677**
  (floor 0.8) → **REVIEW**.
- Max equal-opportunity difference: 0.212.
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
- LGD is trained only on *resolved* defaults (1,434 of 1,434
  training defaults; workout window 36 months).
- Labels are right-censoring-aware (policy: `drop`).
- EAD is the scheduled amortized balance after 6 payments.

## 7. Monitoring & governance
- CI performance gates (Gini / calibration / PSI). Scheduled PSI/CSI drift
  monitoring vs the training baseline. MLflow tracking + model registry for
  reproducibility. Every artifact stamped with code+data version and seed.

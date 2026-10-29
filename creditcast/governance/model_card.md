# Model Card — CreditCast PD/LGD/EAD Expected-Loss Model

> Auto-generated. data_version=`synthetic-v3` · code_version=`0.1.0` · seed=`42`

## 1. Model details
- **Purpose:** Estimate 12-month Probability of Default (PD), Loss Given Default
  (LGD), Exposure at Default (EAD) and combine them into Expected Loss
  (EL = PD × LGD × EAD) for a residential-mortgage portfolio.
- **Models:** (A) regulatory **WoE/IV logistic scorecard**; (B) **LightGBM
  challenger**, sigmoid-calibrated. Champion for EL/decisioning: **challenger (LightGBM, sigmoid-calibrated)**.
- **Decision threshold:** approve if PD ≤ 0.0625
  (method `closed_form`, FN:FP = 15:1;
  closed-form 0.0625, empirical on calib
  0.0722). Never chosen on the OOT
  test outcomes it is evaluated on. PDs are floored at 0.0003.
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
| Gini | 0.4289 | 0.4340 |
| KS | 0.3194 | 0.3263 |
| Calibration max band error | 0.0241 | 0.0268 |
| ECE | 0.0097 | 0.0092 |

- **Benchmark:** challenger − scorecard Gini gap = +0.0051. Negligible accuracy gap — the interpretable scorecard is fully competitive. Deploy the scorecard; retain the challenger as an ongoing benchmark.
- **Top global drivers (SHAP):** ltv_dti, fico, ltv, occupancy_status, orig_interest_rate.
- **Portfolio:** EL ≈ 40,636,906 on EAD 3,050,441,699
  (≈ 133 bps); mean PD 4.50%, mean LGD 28.52%.
- **Regulatory capital (Basel IRB, residential mortgages, R = 0.15,
  99.9%):** 198,256,145 for unexpected loss (RWA
  2,478,201,814, average risk weight 81%).
  EL covers the average loss; capital covers a 1-in-1,000-year year on top. The
  synthetic book defaults far more often than a real prime book, so its risk
  weight is high.

## 5. Fairness
- Disparate-impact (4/5ths) at the decision threshold: min ratio **0.802**
  (floor 0.8) → **PASS**.
- Max equal-opportunity difference: 0.163.
- **Discussion:** the model excludes race, yet neutral features (e.g. credit
  score, DTI) proxy historical disparity, producing disparate impact. Mitigation
  options: feature review, reject-option / fairness-constrained training
  (fairlearn), and monitoring — *not* group-specific thresholds (illegal in
  lending). Surfacing and tracking this is a regulatory expectation (EU AI Act
  high-risk credit scoring).

## 6. Limitations
- Synthetic data calibrated to plausible mortgage behaviour, not a specific
  institution's book.
- Macro features (state unemployment, its 12-month change, 12-month house-price
  growth; lagged 1 month) come from synthetic series. Training
  vintages saw only calm conditions, so tree-model PDs flatten beyond that range
  (e.g. 2020 unemployment): stress scenarios need a separate macro sensitivity.
  Macro features are never cited as adverse-action reasons, and property state
  is used only to look them up, never as a model input.
- LGD is trained only on *resolved* defaults (1,415 of 1,415
  training defaults; workout window 36 months).
- Labels are right-censoring-aware (policy: `drop`).
- EAD is the scheduled amortized balance after 6 payments.

## 7. Monitoring & governance
- CI performance gates (Gini / calibration / PSI). Scheduled PSI/CSI drift
  monitoring vs the training baseline. MLflow tracking + model registry for
  reproducibility. Every artifact stamped with code+data version and seed.

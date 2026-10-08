# CreditCast · Improvement Roadmap

> **Purpose of this file.** This is the single source of truth for improving
> CreditCast. Every future work session should start by reading the
> **Status tracker** below, pick the next open task, follow its steps, and
> tick it off here when its *Done when* checks pass. Keep this file updated
> in the same commit as the code change.

**Project in one line:** CreditCast predicts how much money a bank may lose on
a mortgage — `Expected Loss = PD × LGD × EAD` — and wraps the models in
validation, fairness, explainability, monitoring, an API, a dashboard
("Risk Cockpit") and an AI assistant ("Risk Copilot").

**Review rating at the start of this roadmap (2026-10-08): 7.5 / 10.**
Strong design (out-of-time validation, calibration, governance), held back by
a few methodology leaks, thin tests/CI, an unprotected API, synthetic-only data,
and a dashboard that is hard to use for non-experts.

---

## Contents

- [How to work through this roadmap](#how-to-work-through-this-roadmap)
- [Status tracker](#status-tracker)
- [Phase 0 — Rename to CreditCast](#phase-0--rename-to-creditcast-)
- [Phase 1 — Fix methodology mistakes](#phase-1--fix-methodology-mistakes-)
- [Phase 2 — Testing, CI and reproducibility](#phase-2--testing-ci-and-reproducibility-)
- [Phase 3 — API & production hardening](#phase-3--api--production-hardening-)
- [Phase 4 — Real data](#phase-4--real-data-)
- [Phase 5 — Advanced modeling & regulation](#phase-5--advanced-modeling--regulation-)
- [Phase 6 — User-friendly, interactive UI](#phase-6--user-friendly-interactive-ui-)
- [Order, dependencies & effort](#order-dependencies--effort)
- [Glossary](#glossary)

---

## How to work through this roadmap

1. **One task = one branch = one PR.** Branch name: `roadmap/<task-id>-<slug>`,
   e.g. `roadmap/1.1-threshold-on-calib`.
2. **Before coding:** read the task's *Files* list and *Steps*.
3. **After coding, always run:**
   ```bash
   pip install -r requirements.txt
   python -m pytest -q
   python -m creditcast.cli all        # full lifecycle + CI gates (exit 0 = pass)
   ```
   For UI tasks also run `cd app/dashboard && npm install && npm run build`.
4. **Record metric changes.** Methodology fixes *will* change Gini / EL /
   approval rate. Paste the before → after numbers from
   `creditcast/artifacts/train_metrics.json` and `validation_report.json` into
   the task's *Result* line below. A metric getting *worse* after a leak fix is
   expected and correct — it means the old number was too optimistic.
5. **Tick the box** in the status tracker and fill in the date.
6. **Never hardcode thresholds** — every new number goes in
   `creditcast/conf/config.yaml` (project rule).

---

## Status tracker

Legend: `[ ]` open · `[~]` in progress · `[x]` done · `[-]` dropped

| ID | Task | Status | Date | Notes |
|----|------|--------|------|-------|
| 0 | Rename CreditForge → CreditCast (code) | [x] | 2026-10-08 | Open: 0.M2 host at dhyyraj.in, 0.M3 optional folder rename |
| 1.1 | Threshold chosen on calib, not test | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.2 | Separate valid (early stop) and calib slices | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.3 | Right-censoring in default label | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.4 | LGD only on resolved defaults | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.5 | Remove `rate_spread` train/serve skew | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.6 | Amortized-balance EAD | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.7 | Reason codes follow the champion model | [x] | 2026-10-08 | branch `roadmap/phase-1-methodology` |
| 1.8 | Phase 1 follow-ups (PD floor, threshold stability, generator cures/cutoff) | [x] | 2026-10-08 | Also fixed a censoring bias in 1.3 and switched calibration to sigmoid |
| 2.1 | GitHub Actions CI | [x] | 2026-10-08 | PR #2; first run green (python 1m48s, web 1m23s) |
| 2.2 | Scheduled drift workflow | [x] | 2026-10-08 | PR #5; forced test run opened issue #6 (closed) |
| 2.3 | Expand test suite (≥70% coverage) | [ ] | | |
| 2.4 | Lock dependencies | [ ] | | MLflow 3.x broke the old file store — fixed in Phase 1 branch; pinning still needed |
| 2.5 | Model registry & versioning | [ ] | | |
| 2.6 | Lint / format / types + pre-commit | [ ] | | |
| 3.1 | Rate-limit Copilot | [x] | 2026-10-08 | Also /score and /portfolio; per real client IP behind Caddy |
| 3.2 | Bound & validate API inputs | [x] | 2026-10-08 | 16 bad-input cases → 422 |
| 3.3 | Tighten CORS, optional API key | [x] | 2026-10-08 | Same-origin by default |
| 3.4 | Structured logs + decision audit trail | [x] | 2026-10-08 | `decisions.jsonl`, no raw inputs |
| 3.5 | Health/readiness + Docker HEALTHCHECK | [x] | 2026-10-08 | Caddy waits for healthy app |
| 3.6 | Fix `lru_cache` staleness | [x] | 2026-10-08 | |
| 4.1 | Freddie Mac loader | [ ] | | |
| 4.2 | Data-quality report | [ ] | | |
| 4.3 | Re-tune thresholds on real data | [ ] | | |
| 4.4 | Synthetic vs real comparison in model card | [ ] | | |
| 5.1 | Macro-economic features | [ ] | | |
| 5.2 | Stress testing | [ ] | | |
| 5.3 | Lifetime PD (IFRS 9 / CECL) | [ ] | | |
| 5.4 | Reject inference | [ ] | | |
| 5.5 | Basel IRB regulatory capital | [ ] | | |
| 5.6 | Fairness mitigation analysis | [ ] | | |
| 5.7 | Copilot evaluation suite | [ ] | | |
| 6.0 | UI foundation (Tailwind/shadcn, tokens, layout) | [ ] | | Do first in Phase 6 |
| 6.1.1 | Plain-language labels | [ ] | | Quick win |
| 6.1.2 | Tooltips + Glossary page | [ ] | | Quick win |
| 6.1.3 | Page verdict summaries | [ ] | | |
| 6.1.4 | Guided tour | [ ] | | |
| 6.1.5 | Human-friendly decision card | [ ] | | |
| 6.2.1 | Live scoring with sliders | [ ] | | Quick win |
| 6.2.2 | What-if / counterfactual panel | [ ] | | Needs backend endpoint |
| 6.2.3 | Compare applicants | [ ] | | |
| 6.2.4 | Clickable drill-down charts | [ ] | | |
| 6.2.5 | Interactive threshold slider | [ ] | | Needs backend endpoint |
| 6.2.6 | Searchable loan table + CSV | [ ] | | |
| 6.2.7 | Stress-test playground | [ ] | | Depends on 5.2 |
| 6.2.8 | Better Copilot chat | [ ] | | |
| 6.3.1 | Responsive / mobile layout | [ ] | | Quick win |
| 6.3.2 | Light / dark theme toggle | [ ] | | |
| 6.3.3 | Loading, empty & error states | [ ] | | |
| 6.3.4 | Accessibility (WCAG AA) | [ ] | | |
| 6.3.5 | Component library migration | [ ] | | Part of 6.0 |
| 6.3.6 | PDF downloads | [ ] | | |
| 6.3.7 | Frontend tests (Vitest + Playwright) | [ ] | | |

---

## Phase 0 — Rename to CreditCast ✅

**Done in code (2026-10-08):**
- Package folder `creditforge/` → `creditcast/`; all imports, `config.yaml`
  paths, `config.py` (`DEFAULT_CONFIG_PATH`), Dockerfile, `.gitignore`,
  `.dockerignore`, `requirements*.txt` headers.
- Dashboard: `package.json` name `creditcast-cockpit`, sidebar brand, page
  title; API title "CreditCast Scoring API"; model card; validation report
  HTML; MLflow experiment `creditcast`; Copilot agent prompts.
- The `BONITAS` sub-brand was removed everywhere (2026-10-08).
- Hosting moved from Hugging Face Spaces to **self-hosting at https://dhyyraj.in**:
  HF deploy files removed; `deploy/docker-compose.yml` + `deploy/Caddyfile`
  (automatic HTTPS) + `deploy/README.md` added; container port 7860 → 8000.

**Manual steps (outside the code):**

| ID | Step | Command / action |
|----|------|------------------|
| 0.M1 | New GitHub repo | ✅ Done — https://github.com/Eyeroniq/CreditCast (private), remote `eyeroniq`; the old `origin` (sidnov6/CreditForge) is left untouched |
| 0.M2 | Host at dhyyraj.in | Point DNS (A records for `@` and `www`) at a Docker server, add `.env` with `GROQ_API_KEY`, run `docker compose -f deploy/docker-compose.yml up -d --build` (steps in `deploy/README.md`); then drop "launching soon" from the README |
| 0.M3 | Rename local folder | `CreditCast/CreditForge/` → `CreditCast/CreditCast/` (optional) |
| 0.M4 | Refresh lockfile | ✅ Done — `npm ci` + build pass locally and in CI |

---

## Phase 1 — Fix methodology mistakes 🔴

**Goal:** every number CreditCast reports is honest — no information from the
test period leaks into decisions, and PD/LGD/EAD measure what they claim to.
**Priority: highest. Do this before showing metrics to anyone.**

**Expected side effect:** OOT Gini, approval rate and fairness numbers will
shift (likely slightly worse). That is the point. Update thresholds in
`config.yaml` only if a gate now fails *for a justified reason*, and write the
reason in the model card.

### 1.1 Choose the approve/decline threshold without the test set

- **Problem:** `creditcast/governance/report.py:30` calls
  `decision.default_threshold(scored[CHAMPION_PD], scored["default_12m"])` on
  `test_scored.parquet` — i.e. it *uses the test outcomes* to pick the cut-off,
  then reports approval rate and fairness on the same test set. That is
  leakage: results look better than they will on unseen loans.
- **Files:** `creditcast/train.py`, `creditcast/governance/report.py`,
  `creditcast/governance/decision.py`, `tests/test_threshold.py` (new).
- **Steps:**
  1. In `train.py`, after fitting calibrators, also persist the calibration
     slice's calibrated champion PDs + labels:
     `artifacts/calib_scored.parquet` with columns
     `loan_id, default_12m, pd_challenger, pd_scorecard`.
  2. In `report.py`, load `calib_scored.parquet` and compute
     `thr = decision.default_threshold(calib["pd_challenger"], calib["default_12m"], cfg)`.
  3. Keep using `test_scored.parquet` only to *apply* `thr` for
     `decision_summary` and `fairness_report`.
  4. Save `thr` together with its provenance in `governance_report.json`:
     `"decision": {"threshold": ..., "threshold_source": "calib"}`.
  5. Show "threshold chosen on calibration data" in the Governance screen.
- **Tests:** a test that monkeypatches `default_threshold`, runs
  `build_governance` on a tiny fixture, and asserts the `y_true` passed in
  equals the calib labels, never the test labels.
- **Done when:** `threshold_source == "calib"`; test passes; `cli all` passes.
- **Result (2026-10-08):** threshold 0.0620 *(chosen on test — leak)* → **0.0344
  (chosen on cross-fitted calib PDs)**. Approval 74.7% → 63.0%; approved-loan
  default rate 2.82% → 2.39%; min DI ratio 0.749 → 0.677 (fairness REVIEW).
  Note: on the test set 0.0344 and 0.0625 give the *same* approval (63.0%) —
  the isotonic PDs have no values in between — so the approval change comes
  from the retrained/recalibrated model, not the threshold method. Cross-fitting
  (`calibration.cross_fit_transform`) was added so the calib PDs used to pick
  the threshold are out-of-fold. See 1.8 for stability follow-up.

### 1.2 Separate early-stopping data from calibration data

- **Problem:** `train.py` passes `split.calib` to `fit_challenger` as the
  early-stopping `eval_set`, then fits the calibrator on the same slice. The
  model has already been tuned to that slice, so calibration is biased.
- **Files:** `creditcast/pipeline/split.py`, `creditcast/train.py`,
  `creditcast/conf/config.yaml`, `tests/test_leakage.py`.
- **Steps:**
  1. Config: add `target.oot.valid_fraction: 0.10` next to `calib_fraction`.
  2. `Split` dataclass gains `valid: pd.DataFrame`. In `make_split`, carve
     `calib` (stratified, seeded) from the training pool, then carve `valid`
     from what remains, then `train` = remainder.
  3. `train.py`: `fit_challenger(split.train, split.valid, cfg)`; calibrators
     still fit on `split.calib`.
  4. Update `Split.summary()` and `assert_no_vintage_overlap` to cover
     `valid`. Also assert the three in-time slices have **no shared
     `loan_id`**.
- **Tests:** extend `test_leakage.py` — overlapping loan IDs between
  valid/calib must raise; valid vintages ≥ boundary must raise.
- **Done when:** four disjoint slices; tests pass; summary prints four rows.
- **Result (2026-10-08):** split 36,458 / 6,434 / 17,108 → **train 32,169 /
  valid 4,289 / calib 6,434 / test 17,108**. Challenger best iteration 43 → 82.
  OOT Gini challenger 0.4354 → 0.4327, scorecard 0.4498 → 0.4483 (within noise;
  smaller train set). Calibration max band error 0.0184 → 0.0169.

### 1.3 Handle right-censoring in the default label

- **Problem:** in `pipeline/silver.py` a loan with fewer than 12 monthly
  performance rows after origination (e.g. originated near the data cutoff, or
  paid off early) is labelled `default_12m = 0` simply because no default was
  *seen*. With real Freddie Mac data the latest vintages will be badly
  mislabelled.
- **Files:** `creditcast/pipeline/silver.py`, `creditcast/pipeline/gold.py`,
  `creditcast/conf/config.yaml`, `tests/test_silver_label.py` (new).
- **Steps:**
  1. In the DuckDB query compute per loan `months_observed` = count of
     distinct `rep_idx` in `(vint_idx, vint_idx + horizon]`, and
     `exit_idx` = first month with a non-default zero-balance code (e.g. `01`
     prepaid).
  2. Define `label_complete = 1` if `months_observed = horizon` **or** the loan
     defaulted **or** the loan exited by prepayment (a prepaid loan cannot
     default later — its 0 label is genuine).
  3. Config: `target.censoring: drop | keep_flagged` (default `drop`).
  4. Drop incomplete rows before writing Silver (or keep with the flag), and
     print `"[silver] N loans censored (incomplete 12m window)"`.
- **Tests:** synthetic mini-panels: (a) 12 clean months → label 0, complete;
  (b) 5 months then data ends → incomplete; (c) default at month 4 → label 1,
  complete; (d) prepaid at month 6 → label 0, complete; (e) 90+ DPD at month
  13 → label 0 (outside window).
- **Done when:** all five cases pass; Silver log shows the censored count.
- **Result (2026-10-08):** implemented with configurable Freddie codes
  (`target.default_zb_codes`, `prepay_zb_codes`, `RA` status). 7 hand-built
  loan histories in `tests/test_silver_label.py` pass. Synthetic data: **0
  loans censored** (the generator always emits ≥ 12 months or a prepay) — the
  logic will matter for real Freddie data (Phase 4). See 1.8 for adding a data
  cutoff to the generator so censoring is exercised.

### 1.4 Fit LGD only on resolved defaults

- **Problem:** `models/lgd.py` sets `loss_occurred = lgd.fillna(0) > 0`. A
  default whose foreclosure sale hasn't happened inside the window has
  `net_loss = NULL` → treated as 0% loss → LGD biased downward.
- **Files:** `creditcast/pipeline/silver.py`, `creditcast/pipeline/gold.py`,
  `creditcast/models/lgd.py`, `creditcast/conf/config.yaml`.
- **Steps:**
  1. Config: `lgd.workout_window_months: 36` (LGD needs a longer window than
     PD's 12 months).
  2. In Silver, compute `resolved = 1` when a terminal zero-balance code
     (`09` REO, or cure back to current for N months) occurs within
     `def_idx + workout_window`; take `net_loss` from that row.
  3. In Gold, `lgd` is non-null only for resolved defaults.
  4. `lgd.py::_defaulted` filters `resolved == 1`; remove the `fillna(0)`.
  5. Report "resolved defaults used for LGD: n / total defaults" in training
     metrics and the model card.
  6. Generator: raise `perf_horizon_months` to ≥ 12 + workout window so the
     synthetic data contains resolutions.
- **Done when:** mean predicted vs realized LGD on resolved OOT defaults
  within ±0.05; model card states the population.
- **Result (2026-10-08):** resolved defaults 1,880 → **2,706 / 2,706** (defaults
  disposed after month 12 were previously dropped and their loss treated as
  0%). OOT LGD mean predicted vs realized **0.271 vs 0.382 (bias −0.11) →
  0.387 vs 0.377 (+0.01)**; LGD MAE 0.135 → 0.095. Mean LGD 24.8% → 35.8%;
  portfolio EL 116 → **167 bps**. Finding: every synthetic default ends in a
  loss, so the "cure" stage has one class — `LGDModel` now falls back to a
  constant P(loss) (the old model's cure stage was only learning the window
  artefact). See 1.8.

### 1.5 Remove train/serve skew in `rate_spread`

- **Problem:** `gold.py::_engineer` computes `rate_spread` against the mean
  rate of the loan's *own vintage* (which includes loans originated later in
  that month, and the whole test period's vintages). `serving.py` falls back
  to the *global* mean for any unseen vintage — i.e. always, in production. So
  the feature has a different meaning at serve time.
- **Files:** `creditcast/features.py` (new), `creditcast/pipeline/gold.py`,
  `creditcast/serving.py`, `tests/test_feature_parity.py` (new).
- **Steps:**
  1. Create `creditcast/features.py` with one function
     `engineer(df, benchmark) -> df` used by **both** Gold and serving.
  2. Benchmark = trailing 3-month average note rate of loans originated
     *strictly before* the loan's month (point-in-time). Persist the benchmark
     table to `artifacts/rate_benchmark.parquet` at train time.
  3. Serving: look up the benchmark for the applicant's month; if the month is
     beyond the table, use the latest available benchmark (and say so in the
     response as `"benchmark_month"`).
  4. Delete the duplicated logic in `serving.py::_build_features`.
- **Tests:** feed the same raw row through the pipeline path and the serving
  path → identical feature vector.
- **Done when:** parity test passes; no feature code duplicated.
- **Result (2026-10-08):** `creditcast/features.py` (`rate_benchmark`,
  `engineer`) used by Gold and serving; benchmark persisted to
  `data/gold/rate_benchmark.parquet` (trailing 3 months, strictly prior).
  `tests/test_feature_parity.py` (4 tests) pass. Gini essentially unchanged.
  (The optional `benchmark_month` field in the API response was not added.)

### 1.6 Use amortized balance for EAD

- **Problem:** `models/ead.py` returns `orig_upb × CCF`. By the time a
  borrower defaults they have repaid principal, so EAD (and EL) is overstated.
- **Files:** `creditcast/models/ead.py`, `creditcast/validation/report.py`,
  `tests/test_ead.py` (new).
- **Steps:**
  1. Implement the standard amortization formula: remaining balance after
     `k` payments = `P·[(1+r)^n − (1+r)^k] / [(1+r)^n − 1]`, with monthly rate
     `r = rate/1200`, term `n`.
  2. `k` = expected months to default (config `ead.expected_default_month: 6`
     for a 12-month horizon, or the empirical median from training defaults).
  3. Validation report: add EAD accuracy — mean absolute % error of predicted
     vs `ead_realized` on OOT defaults.
- **Tests:** zero-rate loan, k = 0 (= P), k = n (= 0), known textbook example.
- **Done when:** tests pass; EAD error shown in validation report.
- **Result (2026-10-08):** OOT EAD mean abs. % error vs realized **1.38% →
  0.46%**; total EAD 4.135bn → 4.083bn. `validation_report.json` now has a
  `loss_components` block (EAD MAPE/bias, LGD MAE/means).

### 1.7 Reason codes follow the champion model

- **Problem:** reason codes come from LightGBM SHAP, while the dashboard shows
  the scorecard's credit score and band. If the champion is switched to the
  scorecard, explanations would not match the decision.
- **Files:** `creditcast/conf/config.yaml`, `creditcast/serving.py`,
  `creditcast/governance/reason_codes.py`, `creditcast/governance/report.py`,
  `creditcast/train.py`.
- **Steps:**
  1. Config: `decision.champion: challenger | scorecard`. Replace the hardcoded
     `CHAMPION_PD = "pd_challenger"` and `pd_cal = ch_cal...` with this value.
  2. Scorecard reason codes = characteristics where the applicant lost the
     most points vs the maximum attainable points (standard adverse-action
     method). Implement `scorecard_reasons(scorecard, X)`.
  3. `serving.score()` selects the reason method by champion.
- **Done when:** switching `champion` in config changes PD, decision *and*
  reasons consistently; test covers both.
- **Result (2026-10-08):** `decision.champion` config; `pd_champion` column in
  `test_scored` / `calib_scored`; API, Copilot tools, gates, governance and
  dashboard use it. `creditcast/governance/explain.py` gives SHAP (challenger)
  or points-lost (scorecard) reasons; verified points-lost sum reconciles to
  the score. Default remains `challenger`.

### 1.8 Phase 1 follow-ups (found while implementing)

- **PD floor:** isotonic calibration returns PD = 0.0000 for the best
  applicants (e.g. the "Prime" preset). Add `calibration.pd_floor: 0.0003`
  (Basel 3 bp floor) applied after calibration in train + serving.
- **Threshold stability:** the empirical cost curve on calib is flat/noisy
  (cost 3,306–3,511 across PD 0.034–0.08). Consider the closed-form cut-off for
  calibrated PDs, `cost_fp / (cost_fp + cost_fn)` = 1/16 = 0.0625, or bootstrap
  the empirical minimum; report both.
- **Generator realism:** add cures (defaults that return to current / prepay
  with 0 loss) so the LGD cure stage is meaningful, and a data cutoff date so
  recent vintages are genuinely right-censored (exercises 1.3).
- **Fairness:** min DI fell to 0.677 at the honest threshold — feeds 5.6.
- **Dependencies:** MLflow 3.x refuses the legacy `./mlruns` file store and
  crashed training; `tracking.py` now uses SQLite (`mlflow.db`) and is truly
  best-effort. Pin versions in 2.4.

**Result (2026-10-08), branch `roadmap/1.8-followups`:**

- **PD floor** `calibration.pd_floor: 0.0003` applied inside `Calibrator.transform`
  (train, cross-fit and serving). Zero PDs: some → **none**; the "Prime"
  preset went 0.0000% → 1.12%.
- **Threshold:** new `decision.threshold_method` (default **`closed_form`** =
  cost_fp / (cost_fp + cost_fn) = **0.0625**); the empirical calib minimum is
  still computed and reported (`threshold_alternatives`, model card).
- **Calibration isotonic → sigmoid (new finding).** Isotonic produced only 48
  distinct PDs; one step held **23% of the test book**, and 16% sat on PD
  0.0556 just under the cut-off, so approval jumped 63% ↔ 86% depending on
  which side a step landed. Sigmoid on the same model: max band error 0.0235 →
  **0.0185**, ECE 0.0081 → **0.0055**, largest tie 23% → **0.9%**, approval now
  moves smoothly with the cut-off (76.8 / 80.7 / 84.1% at −10% / 0 / +10%), and
  OOT Gini *rose* (ties had blurred the ranking).
- **Censoring bias fixed (bug in 1.3).** The per-loan rule kept recent
  defaulters but dropped their non-defaulting peers when the data ended
  mid-window, which inflates recent default rates. Labels now also require the
  loan's whole window to end by the data cutoff (last reporting month).
  Covered by a new test case (late-vintage early default → censored).
- **Generator v2** (`data_version: synthetic-v2`): `cure_rate: 0.25` (cures
  return to current, 0 loss) and `data_cutoff: "2022-06"`. Silver resolves
  cures via `lgd.cure_months: 6` months back at current. Result: 4,328 loans
  censored (the 2021-07…12 vintages); 626 cures in the LGD population, so
  the cure stage is a real two-class model again; 2,478 / 2,504 defaults
  resolved (26 too close to the cutoff).
- Tests 52 → 56, all pass; all CI gates pass. Fairness min DI 0.799 —
  REVIEW, just under the 0.80 floor (feeds 5.6).

| Metric (OOT) | After Phase 1 | After 1.8 |
|---|---|---|
| Data | synthetic-v1 | synthetic-v2 (cures, cutoff) |
| Test loans | 17,108 | 12,780 (censored vintages removed) |
| Gini scorecard / challenger | 0.4483 / 0.4327 | 0.4391 / 0.4278 |
| KS challenger | 0.3209 | 0.3290 |
| Calibration max band error | 0.0169 (isotonic) | 0.0185 (sigmoid) |
| Threshold | 0.0344 (empirical) | 0.0625 (closed form) |
| Approval rate / approved-loan default rate | 63.0% / 2.39% | 80.7% / 3.16% |
| Min disparate-impact ratio | 0.677 | 0.799 |
| LGD mean pred vs realized | 0.387 vs 0.377 | 0.282 vs 0.300 |
| LGD MAE | 0.095 | 0.173 (bimodal now: cures at 0) |
| Portfolio EL rate | 167 bps | 122 bps |
| Min PD | 0 | 0.0003 |

Numbers are not directly comparable across the two columns because the
synthetic data changed (v1 → v2); the point is that every component now
behaves sensibly on data with cures and censoring.

### Phase 1 summary (synthetic data, seed 42)

| Metric | Before | After |
|---|---|---|
| Split train / valid / calib / test | 36,458 / – / 6,434 / 17,108 | 32,169 / 4,289 / 6,434 / 17,108 |
| OOT Gini scorecard / challenger | 0.4498 / 0.4354 | 0.4483 / 0.4327 |
| KS challenger | 0.3244 | 0.3209 |
| Calibration max band error (challenger) | 0.0184 | 0.0169 |
| Threshold (source) | 0.0620 (test — leak) | 0.0344 (calib, cross-fitted) |
| Approval rate | 74.7% | 63.0% |
| Approved-loan default rate | 2.82% | 2.39% |
| Min disparate-impact ratio | 0.749 | 0.677 |
| LGD: OOT mean predicted vs realized | 0.271 vs 0.382 | 0.387 vs 0.377 |
| LGD MAE (OOT resolved defaults) | 0.135 | 0.095 |
| EAD mean abs. % error | 1.38% | 0.46% |
| Portfolio EL rate | 116 bps | 167 bps |
| Tests | 24 | 52 (all pass) |

---

## Phase 2 — Testing, CI and reproducibility 🟠

**Goal:** any change that breaks a model or the app fails automatically, and
the same code always produces the same numbers.

### 2.1 GitHub Actions CI

- **Problem:** README promises CI gates, but there is no `.github/` folder.
- **Files:** `.github/workflows/ci.yml` (new), `README.md` (badge).
- **Steps:**
  1. Job `python` (ubuntu-latest, Python 3.11): checkout → setup-python with
     pip cache → `pip install -r requirements.txt` →
     `python -m pytest -q --cov=creditcast` →
     `python -m creditcast.cli all` (gates exit non-zero on failure).
  2. Upload `creditcast/artifacts/*.json` and the validation HTML as build
     artifacts.
  3. Job `web`: Node 20 → `npm ci` → `npm run lint` → `npm run build` in
     `app/dashboard`.
  4. Job `docker` (main branch only): `docker build .` to prove the image
     builds.
  5. Add the CI badge to the README.
- **Done when:** a PR shows three green checks; a deliberately broken gate
  (e.g. `gini_min: 0.99`) turns CI red.
- **Result (2026-10-08):** `.github/workflows/ci.yml` merged (PR #2). PRs run
  `python` + `web` (both green on the first run); `docker` runs only on `main`
  pushes / manual dispatch. Job summary shows the OOT metrics table; reports,
  model card and `coverage.xml` are uploaded. Coverage 41% (target in 2.3).
  ESLint deferred to 2.6 (`next lint` has no config yet). The "broken gate turns
  CI red" check was not run on GitHub; locally `cli gates` exits non-zero on failure.

### 2.2 Scheduled drift workflow

- **Files:** `.github/workflows/monitor.yml` (new).
- **Steps:** weekly `cron: "0 6 * * 1"` → install → `cli generate pipeline
  train monitor` (or download latest artifacts) → upload
  `monitoring_report.json` → if `healthy == false`, open/refresh a GitHub
  issue labelled `drift-alert` (use `gh issue create`).
- **Done when:** manual `workflow_dispatch` run works; forcing an alert opens
  an issue.
- **Result (2026-10-08):** `.github/workflows/monitor.yml` merged (PR #5).
  Mondays 06:00 UTC + manual runs; the summary table goes to the run page,
  `monitoring_report.json` is kept 30 days. Manual run with `force_alert`
  succeeded (all steps green) and opened issue #6, labelled `drift-alert`, with
  the drift table (score PSI 0.0007, healthy). Closed as a test. On synthetic
  data the check is always healthy; it becomes meaningful once real batches
  arrive (Phase 4) — at that point monitor new data instead of rebuilding the
  seeded test set.

### 2.3 Expand the test suite

Current: 4 test files (`test_agent_tools`, `test_el_math`, `test_leakage`,
`test_transforms_stability`). Add:

| New test file | Covers |
|---------------|--------|
| `test_silver_label.py` | 90+ DPD, REO, window edges, censoring (1.3) |
| `test_split.py` | 4-way split, disjoint IDs, stratification (1.2) |
| `test_calibration.py` | isotonic output is monotonic and within [0,1]; Platt path |
| `test_threshold.py` | cost-minimizing threshold on a toy set; calib-only source (1.1) |
| `test_reason_codes.py` | top-N ordering, decoding of category codes, empty on approve |
| `test_fairness.py` | DI ratio and equal-opportunity math on a hand-made frame |
| `test_ead.py` | amortization formula (1.6) |
| `test_feature_parity.py` | pipeline vs serving features identical (1.5) |
| `test_api.py` | FastAPI `TestClient`: `/api/health`, `/api/score` valid & invalid, `/api/portfolio` bounds |
| `conftest.py` | session fixture that runs a **small** pipeline (`n_loans: 3000`) into a temp dir so tests are fast and isolated |

- **Done when:** `pytest --cov=creditcast` ≥ 70%; whole suite < 3 minutes.

### 2.4 Lock dependencies

- **Problem:** `requirements.txt` uses `>=` only — a new `optbinning`,
  `shap` or `lightgbm` release can silently change results or break
  unpickling of saved models.
- **Steps:** keep `requirements.in` / `requirements-serve.in` as the loose
  lists; generate `requirements.txt` / `requirements-serve.txt` with
  `uv pip compile` (or `pip-compile`) pinned with hashes; Dockerfile installs
  the pinned files; document "how to upgrade deps" in README.
- **Done when:** two builds a month apart produce identical metrics.

### 2.5 Model registry & versioning

- **Files:** `creditcast/tracking.py`, `creditcast/serving.py`, config.
- **Steps:**
  1. Bump `run.code_version` automatically from git SHA in the stamp.
  2. Each training run writes artifacts to `artifacts/<run_id>/` and updates
     `artifacts/CURRENT` → run_id.
  3. Log to MLflow (local file store) by default; register the champion as
     `creditcast-pd` with version and metrics.
  4. Serving reads `config.serving.model_version` (default `CURRENT`).
  5. `/api/health` returns the served model version.
- **Done when:** can roll back by changing one config value.

### 2.6 Lint / format / types

- **Steps:** add `ruff` (lint + format) and `mypy` (on `creditcast/models`,
  `creditcast/governance`, `creditcast/serving.py`) via `pyproject.toml`;
  `.pre-commit-config.yaml`; ESLint for the dashboard; run in CI.
- **Done when:** CI fails on lint errors; codebase is clean.

---

## Phase 3 — API & production hardening 🟠

**Goal:** the public demo can't be abused, and every decision is auditable.
**Files mostly:** `app/api/main.py`, `creditcast/serving.py`, `Dockerfile`.

### 3.1 Rate-limit the Copilot

- **Problem:** `/api/agent/chat` has no limit — anyone can burn the Groq quota.
- **Steps:** add `slowapi`; limit `/api/agent/chat` to e.g. `10/minute` and
  `100/day` per IP, `/api/score` to `60/minute`; cap `AgentQuery.question` at
  500 chars (`Field(max_length=500)`); return friendly 429 JSON that the UI
  shows ("You're asking quickly — try again in a minute").
- **Done when:** 11th request in a minute returns 429.
- **Result (2026-10-08):** `slowapi` limits from `config.yaml` → `api.rate_limits`:
  `/api/agent/chat` 10/min + 100/day, `/api/score` 60/min, `/api/portfolio`
  30/min (health/reports unlimited). 429 returns a readable `detail` plus
  `Retry-After`; the cockpit now shows the API's own message. Question length
  1–500 chars. `deploy/docker-compose.yml` sets `FORWARDED_ALLOW_IPS` so limits
  key on the **real visitor IP** behind Caddy — verified on a live server:
  visitor A got 10 → 429 while visitor B was unaffected. Note: invalid bodies
  are rejected (422) before the limiter runs, so they are not counted.

### 3.2 Bound and validate inputs

- **Steps:**
  1. `/api/portfolio?n=`: `n: int = Query(500, ge=1, le=1000)`.
  2. `Applicant`: categoricals become `Literal["P","I","S"]` etc.; `vintage`
     gets `pattern=r"^\d{4}-(0[1-9]|1[0-2])$"`; `orig_upb` gets `le=5_000_000`.
  3. Catch unexpected exceptions in `/score` → 500 with a request ID, never a
     stack trace.
- **Done when:** fuzzing bad payloads only yields 422s; tests in `test_api.py`.
- **Result (2026-10-08):** `Applicant` forbids unknown fields; category codes are
  `Literal`s; NaN/∞ rejected; `orig_upb` ≤ 5M; `vintage` must be `YYYY-MM`;
  `/api/portfolio?n=` 1…1000. Every request gets an `X-Request-ID`; unexpected
  errors in `/score` and `/agent/chat` return 500 with that ID and no internals.
  `tests/test_api.py`: 24 tests (16 bad-input cases, limits, 500 handling).
  Tests 56 → 80.

### 3.3 Tighten CORS and add optional auth

- **Steps:** `allow_origins` from env `CC_ALLOWED_ORIGINS` (default: same
  origin only, since UI and API share a container); optional header
  `X-API-Key` checked against env `CC_API_KEY` for `/api/score` when set
  (demo stays open if unset).
- **Done when:** cross-origin browser call blocked; key works when configured.
- **Result (2026-10-08):** CORS is off unless `CC_ALLOWED_ORIGINS` is set
  (verified live: a request from another origin gets no
  `Access-Control-Allow-Origin`). `CC_API_KEY` (constant-time compare) guards
  `/api/score` and `/api/agent/chat` when set → 401 without the right
  `X-API-Key`. Documented that the public cockpit needs it **unset** (a browser
  can't keep a secret); rate limits protect the public site instead. README
  shows the split-dev setting.

### 3.4 Structured logs + decision audit trail

- **Steps:** JSON logging (`structlog` or std `logging` + JSON formatter);
  for every `/api/score` log `request_id, timestamp, model_version,
  input_hash (SHA-256 of normalized inputs, no raw PII), pd, decision,
  reason_feature_list, latency_ms`; append to `logs/decisions.jsonl` (rotated).
- **Done when:** any decision can be traced to model version + inputs hash.
- **Result (2026-10-08):** `app/api/audit.py`: JSON logs to stdout, and every
  `/api/score` decision appended to `decisions.jsonl` (10 MB × 10 rotation,
  `CC_LOG_DIR`, Docker volume `decision_logs`). Record: request_id, model
  version (run stamp + champion + 12-char SHA-256 fingerprint of the model
  files), input SHA-256, PD, decision, band, threshold, reason features,
  latency. No raw inputs (tested). The score response also returns
  `request_id` and `model_fingerprint`. Verified live.

### 3.5 Health and readiness

- **Steps:** `/api/health` = process up; `/api/ready` = every artifact loads
  (touch each `cached_property` in `ModelBundle`) and returns model version;
  Dockerfile `HEALTHCHECK CMD curl -f http://localhost:${PORT}/api/ready`;
  warm up the bundle at startup (`lifespan` event) so the first user isn't
  slow.
- **Done when:** removing an artifact makes the container unhealthy.
- **Result (2026-10-08):** `/api/ready` checks every required file
  (`serving.REQUIRED_ARTIFACTS`) on each call, then loads them; 503 lists what
  is missing (tested with an empty artifacts dir). The app warms the bundle
  at startup (FastAPI lifespan). Dockerfile `HEALTHCHECK` calls `/api/ready`
  with Python (no curl in the slim image); compose makes Caddy wait for
  `service_healthy`. The healthcheck command was verified against a live
  server; the Docker daemon wasn't running locally, so the container
  healthcheck itself is exercised by the `docker` CI job on `main`.

### 3.6 Fix cache staleness

- **Problem:** `dataset.feature_manifest()` and `config.load_config()` are
  `lru_cache`d — after retraining in the same process (tests, notebooks) the
  old manifest is reused.
- **Steps:** add `reload()` helpers that call `.cache_clear()`; call them at
  the end of `build_gold()` and in the test fixture.
- **Done when:** a test that rebuilds Gold with different features sees the
  new manifest.
- **Result (2026-10-08):** `config.reload()` and `dataset.reload()`;
  `build_gold` calls `dataset.reload()` after writing the manifest.
  `tests/test_cache_reload.py` covers both. Tests 80 → 89.

---

## Phase 4 — Real data 🟡

**Goal:** metrics describe real mortgages, not the synthetic generator.

### 4.1 Freddie Mac loader

- **Source:** Freddie Mac Single-Family Loan-Level Dataset — the free
  *Sample* files (≈50k loans per vintage year), registration required at
  freddiemac.com. **Never commit the data** (already gitignored).
- **Files:** `creditcast/pipeline/ingest_freddie.py` (new),
  `creditcast/conf/config.yaml`, `creditcast/cli.py`.
- **Steps:**
  1. Config: `data.source: synthetic | freddie`, `data.freddie_dir: "data/raw/freddie"`.
  2. Parse pipe-delimited origination (`sample_orig_YYYY.txt`) and performance
     (`sample_svcg_YYYY.txt`) files with DuckDB `read_csv` using the official
     column list; map to `ORIG_SCHEMA` / `PERF_SCHEMA` names in
     `generate.py`.
  3. Handle Freddie specifics: delinquency status `"RA"` (REO acquired) →
     treat as default; missing-value sentinels (FICO `9999`, DTI `999`, LTV
     `999`) → NULL; `vintage` from first-payment date.
  4. `borrower_race` is **not** in Freddie data → fairness must switch to a
     proxy method (e.g. BISG from geography+surname is not available either)
     → for real data, run fairness on available attributes only and document
     the limitation; keep the synthetic fairness demo.
  5. CLI: `python -m creditcast.cli all --source freddie`.
- **Done when:** full lifecycle runs on ≥ 3 sample years.

### 4.2 Data-quality report

- **Steps:** per vintage: row counts, % missing per column, % out of range,
  duplicate IDs, default rate; save `artifacts/data_quality.json` + HTML;
  dashboard tab "Data quality".
- **Done when:** report produced every pipeline run; anomalies highlighted.

### 4.3 Re-tune thresholds on real data

- Re-check `scorecard.iv_min/iv_max`, risk band floors (`decision.bands`),
  `validation.gini_min/ks_min`, `generator`-specific comments. Bands must be
  populated with monotonic default rates.
- **Done when:** all gates pass for documented reasons.

### 4.4 Synthetic vs real comparison

- Model card gets a "Data source" table: Gini, KS, calibration error, EL rate,
  default rate for synthetic and real, with commentary.

---

## Phase 5 — Advanced modeling & regulation 🟡

**Goal:** the depth a bank risk team (or interviewer) expects beyond a
12-month PD.

### 5.1 Macro-economic features

- Join monthly state unemployment (BLS), house-price index (FHFA HPI) and
  30-year mortgage rate (FRED `MORTGAGE30US`) by origination month and
  property state. Store raw series in `data/macro/` with a loader
  `pipeline/macro.py`. Use only values known **at** origination (lag ≥ 1
  month) to keep the leakage rule.
- **Done when:** macro features appear in IV table; leakage tests cover them.

### 5.2 Stress testing

- `creditcast/stress.py`: scenarios in config
  (`baseline`, `adverse`, `severely_adverse` — e.g. unemployment +3/+6 pts,
  HPI −10/−25%). Shift macro inputs, re-score the portfolio, report EL, PD
  by band, approval rate per scenario. API `POST /api/stress` with custom
  shocks. Feeds UI task 6.2.7.
- **Done when:** severe scenario increases EL monotonically vs baseline.

### 5.3 Lifetime PD (IFRS 9 / CECL)

- Discrete-time survival model (logistic hazard on loan-month panel) giving
  monthly default probabilities over the remaining term → lifetime PD and
  lifetime EL. Add IFRS 9 staging: Stage 1 (12m EL), Stage 2 (significant
  increase in credit risk → lifetime EL), Stage 3 (defaulted).
- **Done when:** lifetime PD ≥ 12m PD for every loan; staging summary in
  Portfolio screen.

### 5.4 Reject inference

- The model only sees approved (booked) loans. Simulate a rejected population
  in the generator, then compare: (a) ignore rejects, (b) parceling,
  (c) fuzzy augmentation. Report Gini on the full through-the-door population.
- **Done when:** a short report shows the bias and the chosen method.

### 5.5 Regulatory capital (Basel IRB)

- Implement the Basel retail-mortgage risk-weight formula (correlation
  R = 0.15, confidence 99.9%) → capital K and RWA per loan and portfolio.
  Show capital next to EL ("EL covers expected loss; capital covers
  unexpected loss").
- **Done when:** unit test matches a published worked example.

### 5.6 Fairness mitigation analysis

- Search for a *less discriminatory alternative* (LDA): retrain variants
  (drop/cap proxy-heavy features, monotonic constraints, fairness-constrained
  training via `fairlearn.reductions`) and plot Gini vs DI ratio. **Never** use
  group-specific thresholds (illegal in lending). Document chosen trade-off.
- **Done when:** trade-off chart in Governance screen and model card.

### 5.7 Copilot evaluation suite

- `tests/eval/copilot_questions.yaml`: ~20 questions with expected facts
  (e.g. "OOT Gini of the challenger" → value from `train_metrics.json` ±0.001).
  Runner calls the orchestrator, checks every number in the answer exists in
  tool outputs (no hallucinated figures). Runs nightly when `GROQ_API_KEY` is
  present (skipped otherwise).
- **Done when:** ≥ 90% pass rate tracked over time.

---

## Phase 6 — User-friendly, interactive UI 🎨

**Goal:** anyone — loan officer, manager, interviewer — can open the Risk
Cockpit, understand it without credit-risk jargon, and *play* with the model.

**Current state (`app/dashboard/`):** Next.js 14 (App Router, static export),
React 18, Recharts; one global CSS file (`app/globals.css`, dark theme only);
pages `/` (Score), `/portfolio`, `/validation`, `/monitoring`, `/governance`,
`/copilot`; shared `components/ui.jsx`, `Sidebar.jsx`, `AgentChart.jsx`;
API client `lib/api.js`.

**Gaps found:**
- No responsive layout (zero `@media` rules; fixed 232px sidebar).
- Dropdowns show raw codes (`I`, `C`, `MH`, `SF`).
- Plain number inputs, no hints on good/bad ranges; must click **Score** after
  every change.
- Jargon (PD, LGD, EAD, Gini, KS, PSI, SHAP) never explained.
- Dark only; few ARIA labels; red/green used as the only signal.
- Lots of inline `style={{...}}`; raw error text; no loading skeletons.

### 6.0 UI foundation (do first)

- **Steps:**
  1. Add Tailwind CSS + shadcn/ui (Radix primitives) — gives accessible
     Tooltip, Slider, Tabs, Dialog, Select, Sheet (mobile nav), Toast.
     (`next.config.js` keeps `output: "export"`; shadcn works with static
     export.)
  2. Convert colours in `globals.css` `:root` into Tailwind theme tokens;
     define both light and dark palettes (feeds 6.3.2).
  3. New `components/` structure: `layout/` (AppShell, Sidebar, MobileNav,
     PageHeader), `metrics/` (StatCard, VerdictChip, InfoTip), `charts/`
     (themed Recharts wrappers), `forms/` (SliderField, SelectField).
  4. `lib/labels.js` — single dictionary of code → plain label (6.1.1) and
     `lib/glossary.js` — term → short + long explanation (6.1.2).
  5. Replace inline styles page by page as each page is touched.
- **Done when:** app builds with the new shell; visual parity with today.

### 6.1 Make it understandable

#### 6.1.1 Plain-language labels *(quick win)*
- `lib/labels.js`:
  `occupancy_status: {P: "Primary home", I: "Investment property", S: "Second home"}`,
  `loan_purpose: {P: "Purchase", C: "Cash-out refinance", N: "Rate/term refinance"}`,
  `property_type: {SF: "Single-family", CO: "Condo", PU: "Planned community (PUD)", MH: "Manufactured home"}`,
  `first_time_homebuyer: {Y: "Yes", N: "No"}`, plus feature names
  (`fico` → "Credit score", `dti` → "Debt-to-income", `ltv` → "Loan-to-value",
  `orig_upb` → "Loan amount", `ltv_dti` → "Combined leverage", …).
- Use it in dropdowns, SHAP chart axis labels, tables and Copilot charts.
- **Done when:** no raw code or snake_case feature name visible anywhere.

#### 6.1.2 Tooltips + Glossary page *(quick win)*
- `InfoTip` component (ⓘ icon → Radix Tooltip on hover, Popover on tap).
- Attach to every metric: PD, LGD, EAD, EL, credit score, risk band, Gini, KS,
  calibration error, Hosmer-Lemeshow, PSI/CSI, SHAP, WoE, IV, disparate
  impact, equal opportunity, threshold.
- Each entry: one-line plain meaning + example + "good value" hint, e.g.
  *Gini — How well the model separates borrowers who repay from those who
  don't. 0 = guessing, 1 = perfect. Above 0.35 is acceptable here.*
- New `/glossary` page, searchable, grouped (Loss maths · Model quality ·
  Stability · Fairness · Explainability).
- **Done when:** every metric label has an ⓘ; glossary has ≥ 20 terms.

#### 6.1.3 Page verdict summaries
- A `VerdictBanner` at the top of each page built from the report JSON
  (rules in `lib/verdicts.js`, thresholds read from API responses — not
  hardcoded):
  - Validation: *"✓ Model quality is good — Gini 0.52 (min 0.35), calibration
    error 1.1% (max 3%)."*
  - Monitoring: *"⚠ 2 features drifting — DTI and loan amount changed since
    training."*
  - Governance: *"⚠ Fairness review needed — lowest approval ratio 0.76 (rule:
    ≥ 0.80)."*
- Status chips: ✓ green / ⚠ amber / ✗ red, always with icon + text.
- **Done when:** all six pages show a one-sentence verdict.

#### 6.1.4 Guided tour
- `react-joyride` (or `driver.js`) tour across the 6 screens, ~8 steps;
  auto-starts on first visit (flag in `localStorage`, wrapped in try/catch);
  "Take the tour" button in the sidebar.
- **Done when:** tour completes in < 1 minute and can be replayed.

#### 6.1.5 Human-friendly decision card
- Replace the current decision block on `/` with:
  - Big **Approved ✓ / Declined ✗** with a one-line why
    (*"Main reasons: high debt-to-income and low credit score."*).
  - **Risk gauge** (semi-circle, PD on a 0–20% scale with threshold marker).
  - **Grade scale** AAA → B as a coloured bar with the applicant's grade
    highlighted.
  - EL shown as money with "out of a loan of $X" context.
  - Reasons as plain sentences with icons; SHAP chart collapsed under
    "Show detailed breakdown".
- **Done when:** a non-expert can explain the decision from the card alone.

### 6.2 Make it interactive

#### 6.2.1 Live scoring with sliders *(quick win)*
- Replace number inputs with `SliderField` (slider + editable number):
  credit score 300–850, DTI 0–70, LTV 1–125, rate 0–15, amount 40k–1.2M,
  term select (180/240/360).
- Coloured zones on each track (green/amber/red) from typical risk ranges
  (store ranges in `lib/ranges.js`).
- Auto re-score on change, debounced 300 ms; cancel in-flight requests
  (`AbortController`); keep last result visible with a subtle "updating…"
  indicator. Keep presets as one-click chips.
- **Done when:** moving a slider updates decision and PD within ~0.5 s with no
  flicker.

#### 6.2.2 What-if / counterfactual panel
- **Backend:** `POST /api/whatif` in `app/api/main.py` →
  `creditcast/governance/counterfactual.py`: for each actionable feature
  (DTI, LTV, loan amount, credit score) binary-search the smallest single
  change that flips decline → approve, within plausible bounds; return up to 3
  options. Non-actionable features (property type, purpose) excluded.
- **UI:** for declines show *"You could be approved if: DTI ≤ 38% · or LTV ≤
  80% · or loan amount ≤ $290,000"* with an "Apply" button that moves the
  sliders.
- **Done when:** every decline shows ≥ 1 path (or "no single change is
  enough").

#### 6.2.3 Compare applicants
- "Pin" button on a result; up to 3 pinned cards in a comparison drawer:
  decision, PD, score, grade, EL, top 3 reasons side by side; differences
  highlighted.
- **Done when:** compare works with presets and custom inputs.

#### 6.2.4 Clickable drill-down charts
- Portfolio: click a risk band bar or EL-by-band bar → filters the loan table
  (6.2.6) to that band; click a PD histogram bin → loans in that range.
- Validation: hover on gains/ROC curves shows exact values; Monitoring:
  brush/zoom on drift over time.
- Active filters shown as removable chips.
- **Done when:** every chart has hover tooltips and Portfolio charts filter
  the table.

#### 6.2.5 Interactive threshold slider
- **Backend:** `GET /api/threshold-sim?thr=` → for the scored OOT set returns
  approval rate, approved-default rate, total EL of approved loans, and
  per-group approval rates + DI ratio. Precompute a curve over ~100
  thresholds at governance time (`artifacts/threshold_curve.json`) so the UI
  can scrub without API calls.
- **UI (Governance):** slider for the cut-off; three linked live readouts
  (approval rate, expected loss, fairness DI with the 0.80 line); marker for
  the cost-optimal threshold (from 1.1).
- **Done when:** scrubbing updates all readouts smoothly.

#### 6.2.6 Searchable, sortable loan table
- Use TanStack Table: search by loan ID, sort any column, filters (band,
  vintage, decision, defaulted), pagination (25/50/100), CSV export of the
  filtered rows, plain-language column headers with ⓘ.
- API: add `offset`, `sort`, `filter` params to `/api/portfolio` (bounded by
  3.2) or ship the sample once and filter client-side (≤ 1,000 rows).
- **Done when:** smooth with 1,000 rows; export matches filters.

#### 6.2.7 Stress-test playground *(after 5.2)*
- New `/stress` page: sliders for unemployment change, house-price change,
  rate shock; preset scenario buttons (Baseline / Adverse / Severe); live
  readouts for portfolio EL, EL rate (bps), band mix chart, approval rate;
  baseline vs scenario side by side.
- **Done when:** results render in < 1 s per change.

#### 6.2.8 Better Copilot chat
- Suggested question chips ("Is the model fair?", "Which segment drives most
  loss?", "Why was the high-risk preset declined?").
- Streaming answers (server-sent events from `/api/agent/chat/stream`).
- Collapsible "How I got this" tool trace; copy answer button; per-answer
  charts inline; history kept in `localStorage` (try/catch) with "New chat".
- Friendly states: LLM key missing → explain + link to setup; rate-limited
  (3.1) → countdown.
- **Done when:** first question is one click away; answers stream.

### 6.3 Look & feel, accessibility, quality

#### 6.3.1 Responsive / mobile layout *(quick win)*
- Breakpoints: < 768 px → sidebar becomes a top bar + Sheet (hamburger) or a
  bottom nav; grids `cols-2/3` stack to one column; charts use
  `ResponsiveContainer` with min heights; tables scroll inside their card
  only; 16 px side gutters.
- **Done when:** usable at 375 px wide with no horizontal page scroll (check
  every page).

#### 6.3.2 Light / dark theme toggle
- Tokens for both palettes (6.0); toggle in sidebar; respects
  `prefers-color-scheme` by default; choice stored in `localStorage`
  (try/catch); Recharts colours read from CSS variables.
- **Done when:** both themes pass WCAG AA contrast.

#### 6.3.3 Loading, empty & error states
- Skeleton components for cards/charts/tables; empty states with guidance
  ("No artifacts yet — run `python -m creditcast.cli all`"); errors as
  friendly messages + Retry; global toast for network errors; `lib/api.js`
  maps HTTP codes to messages (404 artifacts missing, 422 invalid input,
  429 slow down, 503 Copilot not configured).
- **Done when:** no raw error string ever reaches the screen.

#### 6.3.4 Accessibility (WCAG AA)
- Labels/ARIA on all inputs; charts get `aria-label` summaries + a "View as
  table" toggle; full keyboard navigation incl. sliders; visible focus rings;
  colour-blind-safe palette and never colour alone (✓ ✗ ⚠ icons + text);
  respects `prefers-reduced-motion`.
- **Done when:** Lighthouse accessibility ≥ 90 on every page; keyboard-only
  walkthrough works.

#### 6.3.5 Component library migration
- Part of 6.0; finish by removing all inline `style={{...}}` blocks from
  `app/**/page.jsx` and consolidating `components/ui.jsx` into the new kit.
- **Done when:** `grep -r "style={{" app/dashboard/app` returns nothing.

#### 6.3.6 PDF downloads
- "Download PDF" on Score (decision + reasons letter — uses existing
  `adverse_action_letter`), Validation and Governance summaries. Use
  print-optimized CSS + `window.print()` first (zero dependencies); move to
  `@react-pdf/renderer` only if layout needs it.
- **Done when:** each of the three screens exports a clean one-to-two-page PDF.

#### 6.3.7 Frontend tests
- Vitest + React Testing Library for components (labels, verdict rules,
  slider debounce, error mapping); Playwright smoke test against the built
  container: open each page, score each preset, check a decision renders, run
  at desktop and 375 px widths. Add to CI (2.1 `web` job).
- **Done when:** UI tests green in CI.

### Target screen map after Phase 6

```
Home (new)          plain-English overview: portfolio health, model status, alerts
Score applicant     sliders + live gauge + reasons + what-if + compare
Portfolio           KPI cards, clickable band/vintage charts, searchable loan table
Model quality       (was Validation) verdict chips + charts with tooltips
Stability           (was Monitoring) drift alerts timeline
Fairness & rules    (was Governance) threshold slider + fairness trade-off
Stress test (new)   scenario sliders (needs 5.2)
Risk Copilot        chat with suggested questions + streaming
Glossary (new)      every term explained simply
```

---

## Order, dependencies & effort

```
Phase 0 (done)
   │
   ├── Phase 1 methodology ──► Phase 2 tests/CI ──► Phase 4 real data ──► Phase 5 advanced
   │        │                       │                                        │
   │        └──► Phase 3 API hardening                                       │
   │                                                                          │
   └── Phase 6 UI (parallel track) ── 6.2.2 / 6.2.5 need small API endpoints ┘
                                       6.2.7 needs 5.2
```

| Phase | Effort | Impact | Notes |
|-------|--------|--------|-------|
| 0 Rename | done | branding | 0.M2 (host at dhyyraj.in) and optional 0.M3 left |
| 1 Methodology | ~1 week | ★★★★★ | metrics become honest |
| 2 Tests / CI | ~1 week | ★★★★ | 2.1 can start right away |
| 3 API hardening | 2–3 days | ★★★ | needed before sharing the demo widely |
| 4 Real data | 1–2 weeks | ★★★★★ | biggest credibility jump |
| 5 Advanced | ongoing | ★★★ | depth for interviews / bank use |
| 6 UI | ~2 weeks | ★★★★ | parallel to 1–3; quick wins in 2–3 days |

**Recommended next tasks:**
1. **1.1** threshold leak (small, high impact)
2. **2.1** CI workflow (protects every later change)
3. **3.1 + 3.2** rate limiting + input bounds (protects the live demo)
4. **6.0 → 6.1.1 → 6.1.2 → 6.2.1 → 6.3.1** UI quick wins

---

## Glossary

| Term | Plain meaning |
|------|---------------|
| **PD** — Probability of Default | Chance a borrower stops paying (90+ days late) within 12 months |
| **LGD** — Loss Given Default | Share of the money lost if they default, after selling the house |
| **EAD** — Exposure at Default | Amount still owed when they default |
| **EL** — Expected Loss | PD × LGD × EAD — the average loss to budget for |
| **OOT** — Out-of-time validation | Train on older loans, test on newer ones (never a random split) |
| **Leakage** | Using information the model wouldn't have at decision time; makes results look falsely good |
| **Right-censoring** | Not watching a loan long enough to know its outcome |
| **WoE / IV** | Weight of Evidence (risk score per bucket) / Information Value (how useful a feature is) |
| **Scorecard** | Traditional points-based model banks and regulators trust |
| **Challenger** | A more complex ML model (LightGBM) compared against the scorecard |
| **Calibration** | Making predicted percentages match real default rates |
| **Gini / KS** | How well the model separates good and bad borrowers (higher = better) |
| **PSI / CSI** | How much the population (score / a feature) has shifted since training |
| **SHAP** | How much each feature pushed one applicant's risk up or down |
| **Reason codes** | Plain-language reasons given to a declined applicant (legally required) |
| **Disparate impact (4/5ths rule)** | Each group's approval rate should be ≥ 80% of the reference group's |
| **IFRS 9 / CECL** | Accounting rules requiring lifetime expected-loss provisions |
| **Basel IRB** | Bank-capital rules where banks use their own PD/LGD models |
| **Stress test** | Re-running the portfolio under a recession scenario |
| **Counterfactual** | The smallest change that would flip a decision |

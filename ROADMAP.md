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
| 2.3 | Expand test suite (≥70% coverage) | [x] | 2026-10-09 | 89% coverage, 122 tests in ~9 s; CI floor 80% |
| 2.4 | Lock dependencies | [x] | 2026-10-09 | uv-compiled, hash-checked; serve lock constrained by training lock; CI checks sync |
| 2.5 | Model registry & versioning | [x] | 2026-10-09 | File registry v0001…; rollback via CLI or `serving.pinned_version`; reproducible builds |
| 2.6 | Lint / format / types + pre-commit | [x] | 2026-10-09 | ruff + mypy + ESLint in CI; formatting commit blame-ignored |
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
| 5.1 | Macro-economic features | [x] | 2026-10-30 | Synthetic state series (real-file drop-in); 3 lagged features; not gated, not adverse-action reasons |
| 5.2 | Stress testing | [x] | 2026-10-30 | Re-scoring + satellite macro sensitivity; EL +70% adverse, +193% severe; CI gate |
| 5.3 | Lifetime PD (IFRS 9 / CECL) | [x] | 2026-10-31 | Logistic hazard on loan-months; lifetime ≥ 12m gate; IFRS 9 staging card on Portfolio |
| 5.4 | Reject inference | [ ] | | |
| 5.5 | Basel IRB regulatory capital | [x] | 2026-10-30 | Matches Basel II Annex 5 table (38 values); capital on Portfolio, Score, Stress |
| 5.6 | Fairness mitigation analysis | [ ] | | |
| 5.7 | Copilot evaluation suite | [ ] | | |
| 6.0 | UI foundation (Tailwind/shadcn, tokens, layout) | [~] | 2026-10-08 | Shared components + responsive shell done on the existing CSS; Tailwind/shadcn migration deferred (see 6.0 result) |
| 6.1.1 | Plain-language labels | [x] | 2026-10-08 | |
| 6.1.2 | Tooltips + Glossary page | [x] | 2026-10-08 | 25 terms |
| 6.1.3 | Page verdict summaries | [x] | 2026-10-23 | 5 report pages; limits read from the API, never hardcoded |
| 6.1.4 | Guided tour | [x] | 2026-10-09 | 8 steps across 4 pages; built in-house (no library) |
| 6.1.5 | Human-friendly decision card | [x] | 2026-10-08 | Done with 6.2.1 |
| 6.2.1 | Live scoring with sliders | [x] | 2026-10-08 | |
| 6.2.2 | What-if / counterfactual panel | [x] | 2026-10-09 | `POST /api/whatif`, ~50 ms |
| 6.2.3 | Compare applicants | [x] | 2026-10-22 | Up to 3 pins, best/worst per row highlighted; client-side only |
| 6.2.4 | Clickable drill-down charts | [x] | 2026-10-23 | Portfolio charts filter the table; Monitoring drift chart zooms with a brush |
| 6.2.5 | Interactive threshold slider | [x] | 2026-10-09 | Precomputed 99-point curve; no API calls while scrubbing |
| 6.2.6 | Searchable loan table + CSV | [x] | 2026-10-09 | Client-side, 1,000 rows, no new dependency |
| 6.2.7 | Stress-test playground | [x] | 2026-10-30 | /stress page; ~0.25 s per change; no rate-shock slider (no rate channel) |
| 6.2.8 | Better Copilot chat | [x] | 2026-10-23 | SSE progress stream, history, copy, trace, rate-limit countdown |
| 6.3.1 | Responsive / mobile layout | [x] | 2026-10-08 | No sideways scroll at 375 px on all 7 pages |
| 6.3.2 | Light / dark theme toggle | [x] | 2026-10-09 | System/Light/Dark; all text ≥ 4.5:1; fixed a dark-theme contrast failure |
| 6.3.3 | Loading, empty & error states | [x] | 2026-10-09 | Skeletons, typed friendly errors, Retry |
| 6.3.4 | Accessibility (WCAG AA) | [x] | 2026-10-23 | axe (Lighthouse's engine) gate in CI: 0 WCAG A/AA violations, 7 pages × 2 themes × 2 sizes; keyboard walkthrough test |
| 6.3.5 | Component library migration | [ ] | | Part of 6.0 |
| 6.3.6 | PDF downloads | [x] | 2026-10-22 | Decision letter (1 page), two reports (2 pages each); real PDFs checked |
| 6.3.7 | Frontend tests (Vitest + Playwright) | [x] | 2026-10-22 | 21 component + 24 e2e tests (desktop + phone); new CI job |
| 6.4 | Glass visual refresh | [x] | 2026-10-22 | Graphite + frosted glass + mint accent, top pill nav, motion; user request |

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
- **Result (2026-10-09):** coverage (creditcast + app) **53% → 89%**; 99 →
  **122 tests**, whole suite **~9 s**. Most of the table above was already done in
  Phases 1–6. New here:
  - `tests/test_lifecycle.py`: runs `creditcast.cli all` **in-process** on a
    4,000-loan config in a temp folder (~5 s). It checks every stage's outputs,
    report coherence, gates, serving with the fresh models, the `split` CLI, and
    that the real model card is untouched. Enabled by `CREDITCAST_CONFIG`
    (config override), `paths.model_card` and `tracking.enabled`. Generate,
    train, validation, governance, drift, gates and CLI were all at 0% before.
  - `tests/test_metrics.py`: Gini/AUC/KS/gains, calibration (ECE, band error,
    Hosmer–Lemeshow), fairness (DI, equal opportunity, privileged-group
    fallback), on data with known answers.
  - `tests/test_agents_loop.py`: Copilot routing, tool loop, chart collection,
    iteration cap, malformed arguments, missing key and rate-limit fallback,
    driven by a scripted fake LLM (no Groq key needed).
  - **Bug found and fixed:** when the router model replied without JSON, the
    intended fallback to the analyst never ran (the slice produced `"{}"`), so
    real questions got the canned "I focus on this platform…" reply. Unusable
    routing now falls back to the analyst; an explicit `{"plan": [], "direct": …}`
    is still respected.
  - CI now measures `creditcast` + `app` and fails below **80%** coverage.

### 2.4 Lock dependencies

- **Problem:** `requirements.txt` uses `>=` only — a new `optbinning`,
  `shap` or `lightgbm` release can silently change results or break
  unpickling of saved models.
- **Steps:** keep `requirements.in` / `requirements-serve.in` as the loose
  lists; generate `requirements.txt` / `requirements-serve.txt` with
  `uv pip compile` (or `pip-compile`) pinned with hashes; Dockerfile installs
  the pinned files; document "how to upgrade deps" in README.
- **Done when:** two builds a month apart produce identical metrics.
- **Result (2026-10-09):** loose lists moved to `requirements.in` /
  `requirements-serve.in`; `scripts/lock-deps.sh` (uv 0.12.23, `--universal`,
  Python 3.11 target, `--generate-hashes`) writes `requirements.txt` (150
  packages) and `requirements-serve.txt`. The serve lock is compiled with
  `--constraint requirements.txt`, so the Docker runtime unpickles models with
  the exact numpy / pandas / scikit-learn / lightgbm / optbinning / shap
  versions the trainer stage used (they were previously resolved independently
  at build time). pip installs in hash-checking mode. New CI step regenerates
  the locks and fails on any diff (re-running is a verified no-op).
  `.gitattributes` keeps LF endings. README → "Dependencies" explains adding
  and upgrading. The "a month apart" check can only be confirmed with time;
  this PR's CI metrics match the previous unpinned runs exactly because the
  locked versions are the ones those runs used.

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
- **Result (2026-10-09):** `creditcast/registry.py` is a file-based registry.
  - **register:** a run that passes the gates is snapshotted to
    `artifacts/registry/v0001…` (all artifacts, plus the gold feature manifest,
    rate benchmark and model card). The `manifest.json` holds the git commit,
    run stamp, model fingerprint, gates result and headline metrics. A run with
    byte-identical model files reuses the latest version.
  - **activate:** restores a version into the working locations, deletes files
    it didn't have, and verifies the fingerprint.

  CLI: `cli all` auto-registers on passing gates; plus `register`, `models list`
  (with `*` = active) and `models use vNNNN`. **Config rollback:**
  `serving.pinned_version: "v0001"` is applied by the API at startup. Verified
  on the real 60k pipeline: v0001 (sigmoid) and v0002 (isotonic) registered;
  pinning v0001 → `/api/ready` served v0001's fingerprint. `/api/health`
  returns the live version and git sha. `run_stamp()` gains `git_sha`
  (`$GIT_SHA`, passed as a Docker build arg in CI/compose, else
  `git rev-parse`).

  **Reproducibility fix (found while verifying):** retraining gave a different
  scorecard file only because optbinning stores wall-clock fit timings
  (`_time_*`) in the pickle. These are zeroed on save, so identical training
  now gives byte-identical models on the same platform: two retrains and a
  fresh full `cli all` all gave fingerprint `7bed00881754`. A lifecycle test
  guards it.

  **Deviations from the plan:**
  - Snapshot-and-restore instead of serving from `artifacts/<run_id>/`
    directly, because about a dozen loaders assume the working folder.
  - No MLflow model-registry entry: the file registry is the source of truth,
    and MLflow keeps run tracking.
  - In Docker each image retrains and contains only its own version, so
    rolling back the live site means redeploying an earlier commit (the
    fingerprint confirms the model); `deploy/README.md` explains this.

  Tests: `tests/test_registry.py` (register, dedupe, next version, rollback
  removes newer-only files, unknown version, tamper detection, health) plus
  lifecycle tests. 122 → 132 tests.

### 2.6 Lint / format / types

- **Steps:** add `ruff` (lint + format) and `mypy` (on `creditcast/models`,
  `creditcast/governance`, `creditcast/serving.py`) via `pyproject.toml`;
  `.pre-commit-config.yaml`; ESLint for the dashboard; run in CI.
- **Done when:** CI fails on lint errors; codebase is clean.
- **Result (2026-10-09):** `pyproject.toml` configures ruff 0.16.10 (rules E, W, F,
  I, B, UP; line length 100) and mypy 2.4.0 (typed core: `models/`,
  `governance/`, `serving.py`, `features.py`, `config.py`). Both are pinned in
  `requirements.in` and locked. Steps:
  1. A pure `ruff format` commit (52 files), listed in `.git-blame-ignore-revs`;
     122 tests pass before and after.
  2. 33 lint findings fixed: exception chaining in the API (`raise … from e`);
     `zip(strict=True)` in the what-if search (outputs must line up with their
     candidates); unused/ambiguous names; import order.
  3. 3 mypy errors fixed: `challenger.predict_pd` was annotated `Series` but
     returns an array; the what-if options list is typed.
  4. Dashboard: ESLint 8.57.1 + `eslint-config-next` 14.2.15
     (`next/core-web-vitals`); 1 finding fixed.

  CI now runs `ruff check`, `ruff format --check`, `mypy` and `npm run lint`.
  `.pre-commit-config.yaml` provides the same checks as optional local hooks.

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
- **Result (2026-10-30):** data version `synthetic-v3`.
  - **Series:** `creditcast/pipeline/macro.py` writes seeded synthetic monthly
    state unemployment and house-price index for 10 states to
    `data/macro/unemployment.csv` and `hpi.csv` (state, month, value: the
    shape of the BLS/FHFA files, so real ones drop in with
    `macro.source: files`). The path follows 2013–2022: slow fall in
    unemployment, a 2020 shock (largest in MI, smallest in TX), fast 2021
    house-price growth. Real public series weren't used: tied to synthetic
    loans they would only show relationships the generator invented. The
    30-year mortgage-rate series was left out because `rate_spread` already
    compares each loan's rate with the prior months' market rate.
  - **Generator:** each loan gets a `property_state` (Freddie's field), and
    the latent default logit now includes the origination-time macro values
    (`generator.macro_effect`). The full effect made the calm-years-trained
    model miss calibration in 2020–21 (4.1% vs the 3% gate), so the effect is
    half that (2.7%, passes); with no effect it was 2.3%.
  - **Features:** `unemp_rate`, `unemp_chg_12m`, `hpi_chg_12m`, looked up by
    (state, month) from series lagged `macro.lag_months` = 1 (a lag below 1
    is refused). Unknown state → national average; missing or future month
    → latest available. `engineer()` adds them for both Gold and serving
    (table persisted as `gold/macro_features.parquet`, registered with the
    model). State itself is never a model input (geography can proxy for
    race).
  - **IV / use:** they appear in the IV table at IV ≈ 0.01 (below the 0.02
    cut, so the scorecard drops them: the training years barely varied). The
    LightGBM champion uses the unemployment pair modestly (SHAP rank 9–10).
    Beyond the training range (2020 unemployment) tree PDs flatten, so the
    same applicant scores the same in TX and MI in July 2020. 5.2 therefore
    needs a separate macro sensitivity rather than re-scoring alone.
  - **Drift:** macro inputs are meant to move, so they're reported as
    "Economic conditions since training" on Stability and in the reports
    (`macro_csi`), and excluded from the CSI gate and drift alerts, which
    still guard every borrower input.
  - **Compliance:** macro features are never cited as adverse-action reasons
    (Reg B requires the applicant's own reasons); test added.
  - **Also fixed:** `shap_global.json` was only computed when missing, so the
    governance report and dashboard had been showing feature importances from
    an older model; it's now recomputed every run.
  - **Gates:** all pass (Gini 0.434, calibration 2.7%, borrower CSI 0.001);
    fairness min ratio 0.802 on this data (was 0.799 on v2, a data change,
    not a fix).
  - **UI / API:** optional `property_state` on `/api/score` (2 capital
    letters); state picker on Score (presets CA / TX / MI); state on the
    decision letter; glossary entry; plain labels for the three features.
  - **Tests:** `tests/test_macro.py` (value from the month before
    origination, changing that month or later never changes the feature,
    lag ≥ 1 enforced, fallbacks, single-row = batch), plus the reason-code
    exclusion test.

### 5.2 Stress testing

- `creditcast/stress.py`: scenarios in config
  (`baseline`, `adverse`, `severely_adverse` — e.g. unemployment +3/+6 pts,
  HPI −10/−25%). Shift macro inputs, re-score the portfolio, report EL, PD
  by band, approval rate per scenario. API `POST /api/stress` with custom
  shocks. Feeds UI task 6.2.7.
- **Done when:** severe scenario increases EL monotonically vs baseline.
- **Result (2026-10-30):** `creditcast/stress.py`, `cli stress` (part of
  `cli all`), `artifacts/stress_report.json`, `GET /api/stress` (configured
  scenarios) and `POST /api/stress` (custom shock, bounded by
  `stress.limits`, rate-limited).
  - **Scenarios** (`stress.scenarios`, shifts on each loan's actual
    origination conditions): adverse = unemployment +3 pts, house prices
    −10%; severely adverse = +6 pts, −25%.
  - **Why two PD channels:** re-scoring alone barely moves, because the
    champion was trained on calm 2015–2019 conditions and trees are flat
    beyond them (see 5.1). So PD = champion on the shocked features, plus a
    **satellite** logit shift: a logistic model of default on the macro
    features with the champion's logit as an offset, fitted on every
    labelled vintage (2015–2021, including the 2020 shock). It measures
    macro sensitivity the champion doesn't already carry, the usual top-down
    bank stress design. Fitted: +0.033 per point of unemployment, +0.043 per
    point of 12-month rise, −0.024 per % of house-price growth (all with the
    expected sign; a wrong-sign coefficient would be set to 0 so stress can
    never lower risk).
  - **LGD:** a house-price fall re-marks LTV to LTV / (1 + fall) and the LGD
    model is re-run. PD doesn't get the re-marked LTV: its house-price
    channel is the HPI feature plus the satellite, and both would count the
    fall twice (the first draft did: severe PD 18%, approval 6%).
  - **Results (12,780 OOT loans):** baseline PD 4.50%, EL 133 bps, approval
    82%; adverse PD 6.95%, EL 227 bps (+70%), approval 62%; severely adverse
    PD 11.54%, EL 390 bps (+193%), approval 27%. Mean PD within every risk
    band rises too (B band 16.8% → 24.3% → 35.9%). Bands come from scorecard
    points, which ignore macro inputs, so loans keep their band and the
    report shows PD by band.
  - **Gate:** "Stress EL rises with severity" (smallest EL ratio between
    consecutive scenarios > 1; currently 1.70) added to the CI gates.
  - **Tests:** `tests/test_stress.py`: the satellite recovers known
    coefficients on simulated data; wrong-sign coefficients are dropped;
    shocks move the right columns and re-mark LTV only for LGD; the baseline
    reproduces the scored portfolio's PD and EL within 1%; EL rises across
    four increasing shocks; report completeness. API tests for validation
    (422s) and a custom run.

### 5.3 Lifetime PD (IFRS 9 / CECL)

- Discrete-time survival model (logistic hazard on loan-month panel) giving
  monthly default probabilities over the remaining term → lifetime PD and
  lifetime EL. Add IFRS 9 staging: Stage 1 (12m EL), Stage 2 (significant
  increase in credit risk → lifetime EL), Stage 3 (defaulted).
- **Done when:** lifetime PD ≥ 12m PD for every loan; staging summary in
  Portfolio screen.
- **Result (2026-10-31):** `creditcast/lifetime.py`, `cli lifetime` (part of
  `cli all`), `artifacts/lifetime_report.json` + `lifetime_scored.parquet`,
  `GET /api/lifetime`; data version `synthetic-v4`.
  - **Generator:** defaults used to happen only in months 1–12, which would
    give every loan zero risk after year one. Loans that survive year one can
    now default in months 13–24 (`generator.late_default_ratio` = 0.8 × the
    12-month PD), from a separate random stream; the main stream is consumed
    exactly as for a healthy loan. Result: silver and gold are bit-for-bit
    identical to v3 (checked), so the 12-month models, gates and Gini don't
    move. A test proves every loan's first 12 months are unchanged.
  - **Survival model:** logit h(t) = a[age bucket] + b · logit(PD₁₂), on
    912k training-vintage loan-months (2,951 first defaults); 8 three-month
    buckets show the seasoning hump (peak in months 4–9). b = 1.03.
    Prepayment is a competing exit (0.91%/month observed).
  - **Lifetime PD** = PD₁₂ + Σ₁₃..T S(t−1)·h(t), so year one is the
    champion's figure and lifetime ≥ 12-month for every loan (new CI gate,
    smallest gap +7.7 pts). Mean 4.50% → 22.0%. Beyond month 24 the hazard is
    held at the months 19–24 level, which errs high (real mortgage hazards
    ease with age); stated in the glossary.
  - **Back-test (cumulative first default by month 24):** training vintages
    6.7% predicted vs 6.9% observed; 2020 H1 vintages 6.8% vs 8.3%. The gap
    is the 2020 shock the champion's 12-month PD already under-reads (see
    5.1), not the curve. My first back-test showed 15% observed: it counted
    every defaulted loan but only fully-observed survivors; now it uses whole
    vintages old enough to be seen for 24 months.
  - **IFRS 9 at 2022-06** (out-of-time loans still open: 10,106; 2,674
    already repaid or written off): Stage 3 = 90+ DPD; Stage 2 = 30+ DPD
    backstop, or 12-month PD now ≥ 2× origination and +0.5 pts (re-scored
    with the reporting-date economy); Stage 1 otherwise. Allowance: Stage 1
    12-month ECL, Stage 2 lifetime ECL (amortising balance, discounted at the
    note rate), Stage 3 LGD × balance. Result: 9,842 / 148 / 116 loans,
    coverage 1.2% / 4.5% / 29.9%, total $36.5M. The 2022 economy is benign,
    so Stage 2 comes from the DPD backstop.
  - **Dashboard:** IFRS 9 staging card on Portfolio (loans, owed, allowance,
    coverage per stage, plus "How lifetime risk is estimated" with the
    back-tests); "Lifetime risk" and "IFRS 9 stage" columns in the loan
    table ("Off book" for loans already closed); glossary entries.
  - **Tests:** `tests/test_lifetime.py`: the fitted hazard is the likelihood
    maximum (zero gradient) and recovers a known curve; lifetime ≥ 12-month
    across terms and equal with one year left; amortisation runs to zero;
    lifetime ECL > 12-month ECL ≈ PD × LGD × balance; the generator test; and
    staging consistency on the real report. Plus an API test.

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
- **Result (2026-10-30):** `creditcast/models/capital.py`:
  K = LGD · N[(G(PD) + √R · G(0.999)) / √(1 − R)] − PD · LGD, RWA = 12.5 · K ·
  EAD, with R = 0.15 and no maturity adjustment (residential mortgages).
  Basel III floors applied to our estimates first: PD 0.05%, LGD 5%
  (`capital` in config).
  - **Worked example:** `tests/test_capital.py` reproduces the Basel II
    framework's illustrative risk-weight table for residential mortgages
    (Annex 5): 19 PDs × LGD 45% and 25%, all 38 values to 0.01 pts (e.g. PD
    1%, LGD 45% → 56.40%).
  - **Where it shows:** `/api/portfolio` (capital, RWA, average risk weight,
    capital by grade, per-loan capital), `/api/score` (applicant capital and
    risk weight), each stress scenario, the governance report and the model
    card. Dashboard: "Capital required (Basel)" on Portfolio (next to EL),
    in the Score page's EL card, and on Stress (with change vs baseline),
    plus a glossary entry explaining expected vs unexpected loss.
  - **Numbers (OOT book):** capital $198M (RWA $2.48B, risk weight 81%)
    against EL $40.6M; under stress 112% (adverse) and 148% (severely
    adverse). 81% is far above real prime mortgage books (roughly 15–35%)
    because the synthetic book defaults about 4.5% a year; this is stated in
    the model card and glossary.

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
- **Result (2026-10-08, partial):** the quick wins were built on the existing
  CSS instead of migrating to Tailwind/shadcn first. The CSS was already tidy,
  token-based (`:root` variables) and small, and a framework migration would
  have restyled every page in one risky change. Added: `lib/labels.js`,
  `lib/glossary.js`, and shared `InfoTip`, `CardTitle`, `TableWrap`,
  `SliderField` in `components/ui.jsx`; a responsive shell with a mobile menu.
  Remaining: decide on Tailwind/shadcn when 6.3.2 (light theme) / 6.3.5 need
  it, and remove the remaining inline styles.

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
- **Result (2026-10-08):** dropdowns, SHAP charts (score + governance), CSI
  table, drift alerts and the portfolio table use plain labels; navigation and
  page titles reworded ("Model quality", "Fairness & explanations", …). The
  backend reason for `rate_spread` now says "above the recent market average"
  (it no longer compares within a vintage since 1.5). Copilot charts still
  show backend labels (6.2.8).

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
- **Result (2026-10-08):** 25 terms in `lib/glossary.js`; ⓘ on every stat card,
  card heading and validation-table metric. Hover / keyboard focus / tap to
  open; on phones the explanation shows as a panel pinned to the bottom of the
  screen. Closed tooltips use `display:none` (a hidden-but-laid-out tooltip
  was found to widen pages on mobile). `/glossary` page with search, grouped by
  topic, anchor per term; added to the navigation.

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
- **Result (2026-10-23):** `lib/verdicts.js` holds one pure rule per page and
  `VerdictBanner` (in `components/ui.jsx`) shows it under the page heading:
  ✓ green / ⚠ amber / ✗ red / ℹ blue, always icon + text, `role="status"`.
  Every limit is read from the API response (validation thresholds, PSI
  watch/unstable levels, the four-fifths floor), so the banner can't disagree
  with the CI gates. On the current synthetic data:
  - Quality: "✓ Model quality is good: Gini 0.43 (min 0.35), worst
    calibration error 1.8% (max 3%)."
  - Stability: "✓ No drift: the score and all 13 inputs match training
    (largest shift PSI 0.03, watch level 0.1)." With alerts it names the
    drifting inputs in plain words; red if any is unstable.
  - Fairness: "⚠ Fairness review needed: Black applicants are approved at
    0.799× the rate of White applicants (rule: at least 0.8)." The ratio uses
    3 decimals so 0.7986 never reads as a passing "0.80".
  - Portfolio (ℹ, informational): approval rate and expected loss as a share
    of the amount lent.
  - Copilot: online, or offline because the server has no LLM key.
  - Score and Glossary have no banner: the decision card is the Score page's
    verdict, and the Glossary is reference.
  Tests: 10 Vitest cases for the rules (pass/warn/fail, plain-word feature
  names, no rounding up to the floor) and a Playwright check on all 5 pages.

#### 6.1.4 Guided tour
- `react-joyride` (or `driver.js`) tour across the 6 screens, ~8 steps;
  auto-starts on first visit (flag in `localStorage`, wrapped in try/catch);
  "Take the tour" button in the sidebar.
- **Done when:** tour completes in < 1 minute and can be replayed.
- **Result (2026-10-09):** `components/Tour.jsx`, built in-house rather than
  with react-joyride/driver.js, because the steps span several pages (it
  navigates and waits for each target) and it should use the theme tokens.
  Eight steps: welcome/navigation, live sliders, decision card, portfolio
  charts, loan table, approval-limit explorer, Copilot, glossary. Targets are
  `[data-tour="…"]` attributes, not CSS classes. The target is spotlighted
  (dimmed page, accent ring) and the card is placed below or above it and
  clamped to the screen. On phones the card pins to the bottom, and a hidden
  target (the collapsed menu) falls back to a centred card. Skip / Back / Next
  / Finish, ← → keys, Esc, and focus moves to the card (`role="dialog"`).
  Auto-starts once on a first visit to the start page (flag in
  `localStorage`, try/catch); "✦ Take the tour" in the menu replays it.
  Verified in the browser: auto-start on first visit; all 8 steps found and
  spotlighted their targets on desktop; clicking through took 2.3 s, so a
  person reading finishes well under a minute; no auto-start on the next
  visit; replay works; phone layout (centred step 1, bottom-pinned card);
  Skip and Esc close it.

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
- **Result (2026-10-08):** sliders + exact number boxes for credit score, DTI,
  LTV, rate and loan amount, with green/amber/red risk zones; term and
  categories as plain-language selects. Re-scores 0.4 s after the last change;
  `AbortController` cancels superseded requests; the last result stays on
  screen with "updating…"; API errors (e.g. rate limit) show without losing
  it. Verified in the browser: Marginal preset declined at PD 6.89%; typing
  credit score 780 re-scored automatically to Approved (3.18%). The decision
  card (6.1.5) shows ✓/✗ verdict + one-line why, a risk meter with the approval
  limit, the AAA→B grade scale, stats with ⓘ, plain reasons, and SHAP folded
  under "Show detailed breakdown".

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
- **Result (2026-10-09):** `creditcast/governance/counterfactual.py` scans four
  levers (lower DTI, bigger down payment / lower LTV, borrow less — which also
  lowers LTV at the same home value — and higher credit score) on a coarse
  grid, refines between the last failing and first passing point, rounds in
  the applicant's favour, then re-scores to confirm (3 batched model calls via
  the new `ModelBundle.pd_batch`, no SHAP; ~20–55 ms). Grid search rather than
  binary search because the model isn't monotonic (e.g. DTI's U-shape). Up to
  3 options, easiest first ("effort" = share of the lever's range). Interest
  rate is excluded (set by the lender). `POST /api/whatif` (30/min, same
  validation + API-key rules as `/score`). UI: a panel under declined
  decisions with **Apply** buttons that move the sliders. Verified: Marginal →
  credit score 690→708, LTV 82→74%, or borrow $272k (each confirmed to
  approve via the full `score()`); clicking "Borrow less" re-scored to
  Approved at 5.95%; High-risk → "No single change is enough". Tests:
  `tests/test_counterfactual.py` (fake transparent model with known answers +
  real model), API tests; suite 89 → 97.

#### 6.2.3 Compare applicants
- "Pin" button on a result; up to 3 pinned cards in a comparison drawer:
  decision, PD, score, grade, EL, top 3 reasons side by side; differences
  highlighted.
- **Done when:** compare works with presets and custom inputs.
- **Result (2026-10-22):** "⊕ Pin to compare" on the decision card snapshots
  the exact inputs and result behind it (pinning waits for the latest score,
  and the same applicant can't be pinned twice). A "Compare applicants" card
  under the form shows up to 3 pins side by side: decision, default risk,
  model score, grade, expected loss, the five main inputs and the top 3
  reasons. When pins differ, each row's best value is green (with a dot) and
  the worst red. Each column can be loaded back into the form or unpinned;
  "Clear all" empties it. Presets keep their names, custom inputs become
  "Applicant N". No API changes. Tests: 5 Vitest (row highlighting, render,
  unpin) and 1 Playwright flow (pin Prime + High-risk, load, clear).

#### 6.2.4 Clickable drill-down charts
- Portfolio: click a risk band bar or EL-by-band bar → filters the loan table
  (6.2.6) to that band; click a PD histogram bin → loans in that range.
- Validation: hover on gains/ROC curves shows exact values; Monitoring:
  brush/zoom on drift over time.
- Active filters shown as removable chips.
- **Done when:** every chart has hover tooltips and Portfolio charts filter
  the table.
- **Result (2026-10-09, partial):** on Portfolio, clicking a bar in "Loans per
  risk grade" or "Expected loss per risk grade" filters the table to that grade;
  clicking a bin of the default-risk histogram filters to that PD range; click
  again to clear. Unselected bars dim; tooltips say "click to filter"; the
  page scrolls to the table; active filters show as removable chips with
  "Clear all". Verified: clicking BB → 389 BB loans. Every chart already had
  hover tooltips. Still open: brush/zoom on the Monitoring time series.
- **Result (2026-10-23, complete):** the Stability page's "Score shift by
  origination month" chart has a Recharts brush under it: drag either handle
  (or the middle) to zoom into a range of months. The title row then shows
  the range ("2020-05 to 2021-06") and a "Reset zoom" link, and every month
  gets an axis label. The brush is styled in CSS (SVG fill attributes can't
  read theme variables) and hidden when printing. Playwright drags the
  handle, checks fewer bars show, then resets.

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
- **Result (2026-10-09):** `decision.threshold_curve()` computes 99 cut-offs
  (0.5%–25%, 0.25-pt steps) on the OOT book at governance time →
  `artifacts/threshold_curve.json` → `GET /api/threshold-curve` (one fetch; the
  `?thr=` per-request variant wasn't needed). Each point: approval rate,
  default rate among approved, share of all defaults approved, expected loss of
  the approved book ($ and bps), min disparate-impact ratio and approval rate
  per group. `components/ThresholdExplorer.jsx` on the Fairness page: slider
  that snaps to the curve, four live readouts with deltas vs policy, a ✓/✗
  4/5ths chip, a chart of approval rate and fairness ratio vs limit with the
  policy, current limit and 0.80 floor marked, and "Reset to policy". The
  text states the policy limit comes from the cost ratio and that per-group
  limits are illegal. Verified in the browser: 3% limit → approval 46.7%
  (−34.0 pts), defaults among approved 1.96%, EL $7.00M, ratio 0.565 ✗.
  The curve matches governance exactly at the policy point (80.7%, 0.799). The
  chart's line animation is off: it is an interactive explorer, and paused
  animation frames left the lines flat during verification. Tests: curve
  monotonicity/consistency on a toy book + artifact consistency; 97 → 99.

#### 6.2.6 Searchable, sortable loan table
- Use TanStack Table: search by loan ID, sort any column, filters (band,
  vintage, decision, defaulted), pagination (25/50/100), CSV export of the
  filtered rows, plain-language column headers with ⓘ.
- API: add `offset`, `sort`, `filter` params to `/api/portfolio` (bounded by
  3.2) or ship the sample once and filter client-side (≤ 1,000 rows).
- **Done when:** smooth with 1,000 rows; export matches filters.
- **Result (2026-10-09):** `components/LoanTable.jsx`, written without TanStack
  (1,000 rows client-side is trivial, so no new dependency). Portfolio now loads
  the 1,000 highest-expected-loss loans (the API cap) and says so. Search by loan
  ID; filters for grade, origination month, decision and actual outcome;
  click-to-sort on every column (`aria-sort`, ▲/▼); 25/50/100 rows per page
  with Prev/Next; "Showing x–y of n (filtered from 1,000)"; plain headers with
  ⓘ; cells stay on one line and the table scrolls inside its card on phones.
  CSV export of the filtered and sorted rows with raw numbers. Verified in the
  browser: sort ↓/↑ on default risk (44.66% / 2.22% first); declined + defaulted
  → 129 loans, all matching; BB filter → CSV with exactly 389 rows, all BB. No
  horizontal page scroll at 375 px.

#### 6.2.7 Stress-test playground *(after 5.2)*
- New `/stress` page: sliders for unemployment change, house-price change,
  rate shock; preset scenario buttons (Baseline / Adverse / Severe); live
  readouts for portfolio EL, EL rate (bps), band mix chart, approval rate;
  baseline vs scenario side by side.
- **Done when:** results render in < 1 s per change.
- **Result (2026-10-30):** new **Stress** page (`app/stress/page.jsx`, in the
  top nav after Portfolio) on the 5.2 engine. Preset buttons (Baseline /
  Adverse / Severely adverse, from the configured scenarios) and two sliders
  (unemployment −2…+10 pts, house prices −40…+20%) re-run `POST /api/stress`
  0.3 s after the last change, cancelling superseded calls. Readouts show
  scenario vs baseline: expected loss (with % change), loss rate in bps,
  average default risk, approval rate at the same limit; a grouped bar chart
  compares average PD per risk grade (with a text summary for screen
  readers), and "How the stress test works" explains the satellite with its
  fitted coefficients. Verdict banner: the worst configured scenario in one
  sentence.
  - **Speed:** about 0.25 s per change on the API (0.54 s for the first),
    within the 1 s target.
  - **No rate-shock slider:** the engine has no interest-rate channel (5.1
    deliberately left out a mortgage-rate series), so a slider would do
    nothing; it can come with a rate feature later.
  - **Band mix:** grades come from the scorecard, which ignores economic
    inputs, so the mix doesn't change; the chart shows PD per grade instead.
  - **Tests:** Playwright (presets update approvals 62% → 27% → 82%; a typed
    unemployment value re-runs and deselects the preset), the stress page in
    the smoke and axe scans (both themes, desktop and phone), and a Vitest
    case for the verdict sentence.

#### 6.2.8 Better Copilot chat
- Suggested question chips ("Is the model fair?", "Which segment drives most
  loss?", "Why was the high-risk preset declined?").
- Streaming answers (server-sent events from `/api/agent/chat/stream`).
- Collapsible "How I got this" tool trace; copy answer button; per-answer
  charts inline; history kept in `localStorage` (try/catch) with "New chat".
- Friendly states: LLM key missing → explain + link to setup; rate-limited
  (3.1) → countdown.
- **Done when:** first question is one click away; answers stream.
- **Result (2026-10-23):**
  - **Backend:** `orchestrator.run_events()` yields `plan` → per specialist
    `agent_start` / `agent_done` (with that specialist's section, charts and
    trace) → `done` (the full result; `run()` now just takes the last event).
    `POST /api/agent/chat/stream` sends these as server-sent events, with the
    same validation and rate limit as `/agent/chat`. A missing key is a plain
    503 before streaming starts; a failure mid-answer is one `error` event
    carrying the request id (no internals). `X-Accel-Buffering: no` so proxies
    don't hold events back.
  - **Streaming granularity:** progress and each specialist's section stream
    as they finish; tokens within a section don't. Each section comes from a
    forced tool call, and the free-tier Groq models aren't streamed token by
    token here, which keeps the grounding logic unchanged.
  - **UI:** six suggested questions (first answer is one click); live rows
    ("Fairness Officer is calling tools…" → ✓); sections fade in as they
    arrive; "How I got this · N tool calls" (collapsible trace); "Copy
    answer"; history in `localStorage` (try/catch, last 30 messages) with
    "＋ New chat"; a 429 shows the API's message plus a countdown from
    `Retry-After` that blocks asking until it ends; no key → explanation with
    a link to console.groq.com. A stream that closes early says the answer
    was cut off instead of spinning.
  - **Tests:** pytest for the event order and that `run()` matches the final
    event, the 503 / SSE / mid-stream error paths, and input bounds;
    Playwright (with the agent endpoints mocked, the real page and stream
    parser) for a streamed answer with trace, an axe scan of it, history
    after reload, New chat, the rate-limit countdown and the no-key state.

### 6.3 Look & feel, accessibility, quality

#### 6.3.1 Responsive / mobile layout *(quick win)*
- Breakpoints: < 768 px → sidebar becomes a top bar + Sheet (hamburger) or a
  bottom nav; grids `cols-2/3` stack to one column; charts use
  `ResponsiveContainer` with min heights; tables scroll inside their card
  only; 16 px side gutters.
- **Done when:** usable at 375 px wide with no horizontal page scroll (check
  every page).
- **Result (2026-10-08):** below 900 px the sidebar becomes a top bar with a
  ☰ Menu (closes after navigating); grids collapse (4 → 2 → 1 columns); tables
  scroll inside their card; 16 px side gutters. Measured `scrollWidth` = 375
  on all 7 pages at 375 px.

#### 6.3.2 Light / dark theme toggle
- Tokens for both palettes (6.0); toggle in sidebar; respects
  `prefers-color-scheme` by default; choice stored in `localStorage`
  (try/catch); Recharts colours read from CSS variables.
- **Done when:** both themes pass WCAG AA contrast.
- **Result (2026-10-09):** light palette added as CSS tokens, applied with
  `html[data-theme="light"]` or by the OS preference when the user hasn't
  chosen dark; `color-scheme` set so native form controls match. All ~65
  hard-coded chart hex colours across 7 components became theme variables
  (SVG attributes accept `var(--…)`), so Recharts follows the theme. The last
  CSS literals (button text, active nav, tinted pills/bands via
  `color-mix`, shadows) were tokenised. `components/ThemeToggle.jsx` in the
  sidebar cycles System → Light → Dark and saves the choice in `localStorage`
  (try/catch); an inline head script applies it before first paint (no
  flash). **Contrast computed** for every text token on bg/panel/panel-2:
  light theme worst case 4.73:1. This also found a **dark-theme failure**: the
  existing `--muted-2` (hints and sub-text) was 3.33:1, so it was raised to
  `#748396` (4.69:1). Verified in the browser: the cycle, persistence across a
  reload, and charts and pages rendering in light colours.

#### 6.3.3 Loading, empty & error states
- Skeleton components for cards/charts/tables; empty states with guidance
  ("No artifacts yet — run `python -m creditcast.cli all`"); errors as
  friendly messages + Retry; global toast for network errors; `lib/api.js`
  maps HTTP codes to messages (404 artifacts missing, 422 invalid input,
  429 slow down, 503 Copilot not configured).
- **Done when:** no raw error string ever reaches the screen.
- **Result (2026-10-09):** `lib/api.js` throws a typed `ApiError` (status, kind,
  request id, raw detail); network failures become "offline". Plain messages
  per kind (offline, 404 "not generated yet", 422, 429, 401, 503, 5xx);
  server `detail` is kept where it is written for people (429, 422, 500 with
  request id) and replaced for 404 developer hints. `useFetch` gains `retry`.
  `PageSkeleton` (shimmer, reduced-motion aware, `role="status"`) replaces the
  "loading…" text on Portfolio, Model quality, Stability and Fairness, shaped
  like each page. `ErrorState` card: friendly title, message, **Try again**,
  link home, technical details folded away. The approval-limit explorer has
  its own skeleton/error so the rest of the page keeps working. Route and
  root error boundaries rewritten in plain language. Verified in the browser:
  missing monitoring report → "Not available yet", then Try again loaded the
  page without a reload; 31 quick portfolio calls → "Slow down a moment";
  simulated network failure → "Can't reach CreditCast"; slowed network →
  skeleton matching the layout.

#### 6.3.4 Accessibility (WCAG AA)
- Labels/ARIA on all inputs; charts get `aria-label` summaries + a "View as
  table" toggle; full keyboard navigation incl. sliders; visible focus rings;
  colour-blind-safe palette and never colour alone (✓ ✗ ⚠ icons + text);
  respects `prefers-reduced-motion`.
- **Done when:** Lighthouse accessibility ≥ 90 on every page; keyboard-only
  walkthrough works.
- **Result (2026-10-23):** `e2e/a11y.spec.mjs` runs axe-core
  (`@axe-core/playwright` 4.13.0, the engine Lighthouse's accessibility score
  is built on) against WCAG 2.0/2.1 A + AA on all 7 pages, in dark and light,
  at desktop and phone sizes (28 scans), plus the open states (tour dialog,
  compare card, phone menu). Any violation fails CI and is listed with the
  elements involved. It found and we fixed:
  - Score: the ⓘ button sat inside the SHAP `<summary>` (nested
    interactive); moved into the panel.
  - Quality: Recharts gives every scatter point `role="img"` with no label.
    New `ChartFrame` (in `components/ui.jsx`) hides chart internals from
    screen readers and gives a one-sentence text equivalent; used on both
    Quality charts.
  - Phones: sideways-scrolling tables weren't keyboard reachable;
    `TableWrap` is now focusable (arrow keys scroll it).
  - Keyboard walkthrough (new test) caught the slider focus ring being
    invisible (a generic `input:focus` glow on a 6px track); range inputs now
    get an outline plus a thumb halo.
  The walkthrough: tab to the credit-score slider, press End to turn a
  decline into an approval, then open Portfolio from the nav with Enter.
  Lighthouse itself isn't added as a dependency: its automated accessibility
  audits are axe rules, which this gate already runs on every page and state. Still open from the
  original wish list: a "View as table" toggle on every chart.

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
- **Result (2026-10-22):** print CSS + `window.print()` ("Save as PDF"), no
  dependency.
  - **Score:** `components/DecisionLetter.jsx`, a formal one-page letter built
    from the live result: date, reference (request id), model fingerprint,
    application summary in plain labels, decision, PD vs limit, grade, expected
    loss, principal reasons, "what could change the outcome" (the what-if
    options), and a demo disclaimer. On paper the Score page prints only the
    letter.
  - **Model quality and Fairness:** a "Download report (PDF)" button and a
    print-only header (title, date, data/code version, git sha, demo note).
  - **Print styles:** always the light palette; menu, buttons, sliders,
    tooltips and filters hidden; cards never split; A4 page.

  Two problems found by rendering real PDFs (headless Edge, then pages
  rasterised and inspected):
  1. Animated charts printed **empty** (captured on their first frame). Chart
     animation is now off on all printable pages.
  2. Charts were laid out for the screen and **shrunk** onto paper (tiny axis
     labels). The button now switches to a `print-layout` (content exactly A4
     wide, 186 mm = 703 px), waits for charts to redraw, then prints;
     `#print` in the URL opens the same layout.

  Result: letter 1 page; model-quality and fairness reports 2 pages each, with
  readable charts. The button was verified in the browser (layout and filename
  applied during print, restored afterwards).

#### 6.3.7 Frontend tests
- Vitest + React Testing Library for components (labels, verdict rules,
  slider debounce, error mapping); Playwright smoke test against the built
  container: open each page, score each preset, check a decision renders, run
  at desktop and 375 px widths. Add to CI (2.1 `web` job).
- **Done when:** UI tests green in CI.
- **Result (2026-10-22):**
  - **Component tests** (Vitest 5.0.3 + Testing Library in jsdom,
    `app/dashboard/__tests__`, 21 tests, about 3 s): plain labels and
    formatters; the friendly API errors (404 hides the developer hint, 429 and
    422 keep readable text, 500 keeps the request id, network failure =
    offline, an aborted request is not "offline"); loan table sorting,
    filtering, chips, the empty state and the CSV containing exactly the
    filtered rows; theme toggle cycle and persistence; InfoTip ARIA wiring;
    ErrorState titles and retry; decision letter for a decline and an approval.
  - **End-to-end** (Playwright 1.64.0, `app/dashboard/e2e`, 24 tests = 12 ×
    desktop 1280 px and phone 375 px): every page loads with data, no error
    state, no page errors and no sideways scroll; sample applicants score
    live, and a what-if **Apply** turns the marginal decline into an approval;
    typing a credit score re-scores; a grade bar filters the loan table; the
    theme survives a reload; the tour starts on a first visit and closes with
    Esc. All 24 pass locally against the real API (about 30 s; installed Edge
    via `PW_CHANNEL=msedge`).
  - **CI:** the dashboard job runs `npm test`; a new **e2e** job trains the
    models, builds the cockpit, starts the server, waits for `/api/ready`,
    runs Playwright in Chromium, and uploads the report and server log on
    failure. The Docker job now waits for it.
  - **Toolchain:** npm 10 crashes resolving vitest's optional peer
    dependencies ("edgesOut", on both vitest 5 and 4), so CI and the Docker
    web stage moved from Node 20 to **Node 24 LTS** (npm 11, the same as local),
    and the lockfile was regenerated with npm 11. All new dev dependencies are
    pinned to releases at least two weeks old.

### 6.4 Glass visual refresh (added 2026-10-22 at the user's request)

Restyle to a reference design the user supplied: a graphite gradient, Apple-style
frosted glass, one mint accent, a floating pill navigation, a bold display
type with spaced mono labels, and smooth loading and scrolling animations.

- **Result (2026-10-22):**
  - **Tokens:** graphite gradient background (a lit corner fading to near-black)
    with a slow ambient light drift; glass surfaces (`backdrop-filter`, a solid
    fallback where blur isn't supported); a single mint accent with a soft glow;
    a separate `--series` blue for neutral chart data, so the BBB grade no
    longer shares the "good" green. Light theme: white frosted glass on soft
    grey. Fonts ship inside the app from pinned Fontsource packages via
    `next/font/local`, so neither the build nor visitors contact Google
    (fetching from Google at build time broke CI): Space Grotesk (display and numbers), Inter (body), JetBrains
    Mono (labels).
  - **Layout:** the sidebar is replaced by a floating top bar: the
    `CREDITCAST●` brand, a glass pill nav, a live status pill
    ("● models live · v0001" from `/api/health`), tour and compact theme
    buttons. On phones: brand · theme · ☰ Menu opening a glass dropdown.
  - **Hero headings:** a mono eyebrow pill per page, a big display title ending
    in the mint dot (decorative, outside the heading's accessible name), and a
    mint rule before the subtitle. Cards have mono uppercase section labels
    with a mint lead line, and display-font stat values. Primary buttons are
    outlined mint pills with a glow on hover; chips are glass pills.
  - **Motion:** the top bar drops in; each page's heading rises in on
    navigation (`app/template.jsx`); cards fade and rise into place as they
    scroll into view, staggered (`components/ScrollReveal.jsx`, with a safety
    net that shows everything if the observer never fires); the status and
    brand dots pulse; smooth scrolling. Everything is off under
    `prefers-reduced-motion`, and print always shows all content.
  - **Contrast:** every text colour was computed against the darkest and
    lightest background, with and without a glass panel. The first draft
    failed on the lit corner, so the gradient was capped and the muted, data
    and red colours brightened; all now pass AA (lowest 4.53:1).
  - **Verified:** the Score and Portfolio pages in dark and light;
    phone menu; no sideways scroll at 375 px; 21 component and 24 end-to-end
    tests pass (one e2e wait was lengthened: under 4 parallel browsers on a
    small machine, scoring plus the what-if search took several seconds);
    PDFs still print clean (letter 1 page, report 2 pages). Fixed: the letter
    tables lost their last row border to a general table rule.

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

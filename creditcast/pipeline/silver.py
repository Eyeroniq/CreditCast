"""Silver layer — cleaning + the leakage-safe point-in-time default flag.

This is the keystone of the whole platform. Disciplines enforced here:

1. **Point-in-time, forward-looking target.** The observation date is loan
   origination. The 12-month default flag looks at performance rows strictly
   inside the forward window (origination, origination + 12 months]. A loan
   defaults if it hits 90+ DPD (>= 3 months delinquent), is REO-acquired, or
   exits via a default-type zero-balance code in that window. Nothing after
   the window can influence the label, and no performance information enters
   the feature set at all.

2. **Right-censoring.** A label is only trusted when the loan's whole 12m
   window ends on or before the data cutoff (the last reporting month in the
   panel) — for defaulters *and* non-defaulters alike; keeping early defaults
   from recent vintages while dropping their non-defaulting peers would inflate
   recent default rates. Within complete windows, a "no default" label also
   needs the loan to have been watched all 12 months or to have left cleanly
   (prepaid). Censored loans are dropped (or kept with `label_complete = 0`).

3. **Resolved-loss LGD.** Realized loss is taken from the loan's terminal
   disposition within a longer *workout* window after default; a default that
   returns to current for `lgd.cure_months` (or prepays) is a cure with zero
   loss. Defaults that are not yet resolved get `resolved = 0` and no LGD
   (never a fake 0% loss).

4. **Data-quality gates.** Malformed/implausible origination rows are rejected
   before they can poison training (Part 10.6).
DuckDB does the heavy lifting straight off the Bronze parquet (no server).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from creditcast.config import Config, load_config

# Plausibility ranges for the Silver data-quality gate (reject outside these)
QUALITY_RANGES = {
    "fico": (300, 850),
    "dti": (0, 70),
    "ltv": (1, 125),
    "orig_interest_rate": (0, 25),
    "orig_upb": (1_000, 5_000_000),
    "orig_loan_term": (60, 480),
}


def build_silver(cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    bronze = cfg.path("bronze")
    silver = cfg.path("silver")
    silver.mkdir(parents=True, exist_ok=True)

    horizon = int(cfg.target.observation_horizon_months)
    dpd_months = int(cfg.target.default_dpd_threshold) // 30  # 90 days -> 3 months
    workout = int(cfg.lgd.workout_window_months)
    cure_months = int(cfg.lgd.cure_months)
    default_codes = _sql_list(cfg.target.default_zb_codes)
    prepay_codes = _sql_list(cfg.target.prepay_zb_codes)

    orig_glob = str(bronze / "origination" / "*.parquet")
    perf_glob = str(bronze / "performance" / "*.parquet")

    con = duckdb.connect()
    # Month index helper: year*12 + month, computed from 'YYYY-MM' strings.
    con.execute("""
        CREATE MACRO midx(s) AS
            CAST(SUBSTR(s, 1, 4) AS INT) * 12 + CAST(SUBSTR(s, 6, 2) AS INT);
    """)

    # ---- point-in-time forward join: default events strictly within window ----
    con.execute(f"""
        CREATE TEMP TABLE perf_events AS
        SELECT
            p.loan_id,
            p.monthly_reporting_period,
            midx(p.monthly_reporting_period)              AS rep_idx,
            TRY_CAST(p.current_loan_delinquency_status AS INT) AS dpd_months,
            (p.current_loan_delinquency_status = 'RA')    AS reo_acquired,
            p.zero_balance_code,
            p.current_upb,
            p.net_loss
        FROM read_parquet('{perf_glob}') p;
    """)

    # Data cutoff = last reporting month present in the performance panel.
    cutoff_idx = con.execute("SELECT MAX(rep_idx) FROM perf_events").fetchone()[0]

    con.execute(f"""
        CREATE TEMP TABLE orig AS
        SELECT *, midx(vintage) AS vint_idx
        FROM read_parquet('{orig_glob}');
    """)

    # The forward window (obs, obs+horizon]: default events and clean exits.
    con.execute(f"""
        CREATE TEMP TABLE win AS
        SELECT e.loan_id, e.rep_idx, e.zero_balance_code, e.current_upb,
               (e.dpd_months >= {dpd_months}
                OR e.reo_acquired
                OR e.zero_balance_code IN ({default_codes})) AS is_def_event,
               (e.zero_balance_code IN ({prepay_codes}))    AS is_clean_exit
        FROM perf_events e
        JOIN orig o ON e.loan_id = o.loan_id
        WHERE e.rep_idx > o.vint_idx
          AND e.rep_idx <= o.vint_idx + {horizon};
    """)
    # Per loan: months observed, clean exit?, first default month.
    con.execute("""
        CREATE TEMP TABLE obs AS
        SELECT loan_id,
               COUNT(DISTINCT rep_idx)                                AS months_observed,
               BOOL_OR(COALESCE(is_clean_exit, FALSE))                AS exited_clean,
               MIN(CASE WHEN COALESCE(is_def_event, FALSE) THEN rep_idx END) AS def_idx
        FROM win GROUP BY loan_id;
    """)
    # Exposure at default = current balance at the first default month.
    # Loss = net loss on the first terminal disposition inside the workout
    # window [def_idx, def_idx + workout]; a prepay after default is a cure (0).
    con.execute(f"""
        CREATE TEMP TABLE dflt AS
        WITH ead AS (
            SELECT w.loan_id, ANY_VALUE(w.current_upb) AS ead
            FROM win w JOIN obs b ON w.loan_id = b.loan_id AND w.rep_idx = b.def_idx
            GROUP BY w.loan_id
        ),
        terminal AS (
            SELECT e.loan_id,
                   ARG_MIN(CASE WHEN e.zero_balance_code IN ({prepay_codes})
                                THEN 0.0 ELSE COALESCE(e.net_loss, 0.0) END,
                           e.rep_idx) AS net_loss
            FROM perf_events e JOIN obs b ON e.loan_id = b.loan_id
            WHERE b.def_idx IS NOT NULL
              AND e.rep_idx >= b.def_idx
              AND e.rep_idx <= b.def_idx + {workout}
              AND (e.zero_balance_code IN ({default_codes})
                   OR e.zero_balance_code IN ({prepay_codes}))
            GROUP BY e.loan_id
        ),
        cure AS (
            SELECT e.loan_id
            FROM perf_events e JOIN obs b ON e.loan_id = b.loan_id
            WHERE b.def_idx IS NOT NULL
              AND e.rep_idx > b.def_idx
              AND e.rep_idx <= b.def_idx + {workout}
              AND e.dpd_months = 0
            GROUP BY e.loan_id
            HAVING COUNT(*) >= {cure_months}
        )
        -- a terminal disposition wins over an earlier cure (re-default -> loss)
        SELECT b.loan_id, b.def_idx, ead.ead,
               CASE WHEN t.loan_id IS NOT NULL THEN t.net_loss
                    WHEN c.loan_id IS NOT NULL THEN 0.0 END AS net_loss,
               (t.loan_id IS NOT NULL OR c.loan_id IS NOT NULL) AS resolved
        FROM obs b
        LEFT JOIN ead ON b.loan_id = ead.loan_id
        LEFT JOIN terminal t ON b.loan_id = t.loan_id
        LEFT JOIN cure c ON b.loan_id = c.loan_id
        WHERE b.def_idx IS NOT NULL;
    """)

    silver_df = con.execute(f"""
        SELECT
            o.* EXCLUDE (vint_idx),
            CASE WHEN d.loan_id IS NOT NULL THEN 1 ELSE 0 END AS default_12m,
            COALESCE(b.months_observed, 0)                    AS months_observed,
            CASE WHEN o.vint_idx + {horizon} <= {cutoff_idx}
                   AND (d.loan_id IS NOT NULL
                        OR COALESCE(b.months_observed, 0) >= {horizon}
                        OR COALESCE(b.exited_clean, FALSE))
                 THEN 1 ELSE 0 END                            AS label_complete,
            d.ead,
            d.net_loss,
            CASE WHEN d.resolved THEN 1 ELSE 0 END            AS resolved
        FROM orig o
        LEFT JOIN obs b  ON o.loan_id = b.loan_id
        LEFT JOIN dflt d ON o.loan_id = d.loan_id
        ORDER BY o.loan_id;
    """).df()
    con.close()

    # ---- right-censoring: only trust labels from a complete window -----------
    n_in = len(silver_df)
    n_censored = int((silver_df["label_complete"] == 0).sum())
    if str(cfg.target.censoring) == "drop":
        silver_df = silver_df[silver_df["label_complete"] == 1].reset_index(drop=True)

    # ---- data-quality gate: reject implausible rows before they poison training
    before = len(silver_df)
    mask = pd.Series(True, index=silver_df.index)
    for col, (lo, hi) in QUALITY_RANGES.items():
        mask &= silver_df[col].between(lo, hi)
    rejected = int((~mask).sum())
    silver_df = silver_df[mask].reset_index(drop=True)

    out = silver / "loans.parquet"
    silver_df.to_parquet(out, index=False)

    rate = silver_df["default_12m"].mean()
    n_def = int(silver_df["default_12m"].sum())
    n_res = int(silver_df["resolved"].sum())
    print(
        f"[silver] {n_in:,} loans in, {n_censored:,} censored (incomplete "
        f"{horizon}m window, policy={cfg.target.censoring}), {rejected:,} rejected "
        f"by quality gate, {len(silver_df):,} out | 12m default rate {rate:.2%}"
    )
    print(
        f"[silver] {n_res:,}/{n_def:,} defaults resolved within the "
        f"{workout}m workout window (LGD population)"
    )
    return out


def _sql_list(codes) -> str:
    """Render config codes as a SQL string list, e.g. '02', '09'."""
    return ", ".join(f"'{c}'" for c in codes)


if __name__ == "__main__":
    build_silver()

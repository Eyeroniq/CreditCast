"""Engineered features — ONE implementation shared by the Gold pipeline and serving.

Everything here uses only information known at origination, so the leakage
guarantee holds, and because the pipeline and the scoring API call the same
function, a feature can never mean one thing in training and another in
production (train/serve skew).

`rate_spread` compares the loan's note rate to a **point-in-time market
benchmark**: the average note rate of loans originated in the trailing
`window` months *strictly before* the loan's month. A lender knows that number
on the origination date; it never uses the loan's own month or anything later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BENCHMARK_WINDOW_MONTHS = 3


def rate_benchmark(df: pd.DataFrame, window: int = BENCHMARK_WINDOW_MONTHS) -> pd.DataFrame:
    """Trailing average note rate per origination month, from prior months only.

    Returns one row per month from the first observed vintage to one month past
    the last (so the next unseen month already has a benchmark), with columns
    `vintage` ('YYYY-MM') and `rate_benchmark`.
    """
    months = pd.PeriodIndex(df["vintage"].astype(str), freq="M")
    g = (
        pd.DataFrame({"m": months, "r": df["orig_interest_rate"].to_numpy(float)})
        .groupby("m")["r"]
        .agg(["sum", "count"])
    )
    full = pd.period_range(g.index.min(), g.index.max() + 1, freq="M")
    g = g.reindex(full, fill_value=0.0)
    # rolling over the previous `window` months, shifted so the current month
    # is excluded (strictly point-in-time)
    s = g["sum"].rolling(window, min_periods=1).sum().shift(1)
    n = g["count"].rolling(window, min_periods=1).sum().shift(1)
    bench = s / n.replace(0, np.nan)
    # The earliest month has no history; fall back to the first month that has
    # one (affects only the oldest training vintage, never the OOT test set).
    bench = bench.bfill().ffill()
    return pd.DataFrame({"vintage": full.astype(str), "rate_benchmark": bench.to_numpy()})


def lookup_benchmark(vintages: pd.Series, benchmark: pd.DataFrame) -> np.ndarray:
    """Benchmark for each vintage; unknown/missing/future months use the latest."""
    table = benchmark.set_index("vintage")["rate_benchmark"]
    latest = float(table.iloc[-1])
    return vintages.astype("object").map(table).astype(float).fillna(latest).to_numpy()


def engineer(df: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    """Add the engineered features. Used verbatim by Gold and by serving."""
    df = df.copy()
    # LTV x DTI interaction: thin-equity AND stretched borrower compound risk
    df["ltv_dti"] = (df["ltv"] * df["dti"] / 100.0).round(2)
    # Rate spread vs the point-in-time market benchmark: isolates idiosyncratic
    # pricing/risk without looking at the loan's own cohort or the future.
    vint = df["vintage"] if "vintage" in df else pd.Series([None] * len(df), index=df.index)
    df["rate_spread"] = (
        df["orig_interest_rate"].to_numpy(float) - lookup_benchmark(vint, benchmark)
    ).round(3)
    # High-LTV flag (regulatory PMI boundary at 80)
    df["high_ltv"] = (df["ltv"] > 80).astype(int)
    return df

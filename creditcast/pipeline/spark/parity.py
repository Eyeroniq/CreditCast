"""Parity: does the Spark engine write the same Gold as the DuckDB engine?

Compares the three Gold tables column by column after sorting on their keys:
same row count, same keys, and every value equal (numbers within `atol`,
NaN equal to NaN; text and categories exactly). `cli parity` runs both engines
on one dataset and prints this report; the Spark tests assert it is clean.
"""

from __future__ import annotations

import pandas as pd
from pyspark.sql import SparkSession

from creditcast.config import Config
from creditcast.pipeline.spark.run import published_frames

KEYS = {
    "feature_matrix": ["loan_id"],
    "rate_benchmark": ["vintage"],
    "macro_features": ["state", "vintage"],
}


def _as_text(s: pd.Series) -> pd.Series:
    """Values as plain strings, with every kind of missing value as "<NA>"."""
    return s.astype(object).where(s.notna(), "<NA>").astype(str)


def compare_frames(duck: pd.DataFrame, spark: pd.DataFrame, keys: list[str], atol: float) -> dict:
    """Differences between two versions of one table (empty lists/dicts = equal)."""
    report: dict = {
        "rows": [len(duck), len(spark)],
        "missing_columns": sorted(set(duck.columns) - set(spark.columns)),
        "extra_columns": sorted(set(spark.columns) - set(duck.columns)),
        "mismatched": {},
        "max_abs_diff": {},
    }
    a = duck.sort_values(keys).reset_index(drop=True)
    b = spark.sort_values(keys).reset_index(drop=True)
    if len(a) != len(b) or not a[keys].astype(str).equals(b[keys].astype(str)):
        report["keys_equal"] = False
        report["ok"] = False
        return report
    report["keys_equal"] = True

    for col in [c for c in a.columns if c in b.columns]:
        x, y = a[col], b[col]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            x, y = x.astype(float), y.astype(float)
            both_nan = x.isna() & y.isna()
            diff = (x - y).abs()
            bad = ~(both_nan | (diff <= atol))
            if diff.notna().any():
                report["max_abs_diff"][col] = float(diff.max())
        else:  # text / categories: compare as plain strings, missing == missing
            bad = _as_text(x) != _as_text(y)
        if bad.any():
            report["mismatched"][col] = int(bad.sum())
    report["ok"] = not (
        report["missing_columns"] or report["extra_columns"] or report["mismatched"]
    )
    return report


def compare(spark: SparkSession, cfg: Config, atol: float = 1e-9) -> dict:
    """Spark Gold (paths.spark) vs the DuckDB Gold files (paths.gold)."""
    spark_frames = published_frames(spark, cfg)
    out = {}
    for name, keys in KEYS.items():
        duck = pd.read_parquet(cfg.path("gold") / f"{name}.parquet")
        out[name] = compare_frames(duck, spark_frames[name], keys, atol)
    out["ok"] = all(r["ok"] for r in out.values() if isinstance(r, dict))
    return out

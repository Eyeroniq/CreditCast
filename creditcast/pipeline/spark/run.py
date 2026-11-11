"""Run the Spark pipeline and publish Gold for the rest of CreditCast.

Training, validation, the Copilot and the scoring API read four Gold files
(`feature_matrix.parquet`, `feature_manifest.json`, `rate_benchmark.parquet`,
`macro_features.parquet`). Publishing writes them with the same columns,
types, and row order as the DuckDB engine, so every later stage works
unchanged whichever engine built them.

The partitioned Spark tables stay in `paths.spark` for Spark consumers.
"""

from __future__ import annotations

import json
import time

import pandas as pd
from pyspark.sql import SparkSession

from creditcast import dataset
from creditcast.config import Config, load_config
from creditcast.pipeline.gold import gold_columns, gold_layout
from creditcast.pipeline.spark import bronze, gold, silver
from creditcast.pipeline.spark.session import get_spark


def published_frames(spark: SparkSession, cfg: Config) -> dict[str, pd.DataFrame]:
    """Spark Gold as the pandas frames the DuckDB engine writes."""
    manifest = gold_layout(cfg)
    feature_matrix = (
        spark.read.parquet(str(gold.gold_dir(cfg) / "feature_matrix"))
        .select(*gold_columns(manifest))
        # Same order as DuckDB Silver's ORDER BY loan_id: pipeline.split samples
        # calib/valid by position, so order changes which loans land where.
        .orderBy("loan_id")
        .toPandas()  # Arrow: columnar transfer from the JVM, not row by row
    )
    for c in manifest["categorical"]:  # LightGBM reads pandas categoricals
        feature_matrix[c] = feature_matrix[c].astype("category")
    benchmark = (
        silver.read_silver(spark, cfg, "rate_benchmark")
        .orderBy("idx")
        .select("vintage", "rate_benchmark")
        .toPandas()
    )
    macro = (
        silver.read_silver(spark, cfg, "macro_features")
        .orderBy("idx", "state")
        .select("state", "vintage", *cfg.macro.features)
        .toPandas()
    )
    return {
        "feature_matrix": feature_matrix,
        "rate_benchmark": benchmark,
        "macro_features": macro,
    }


def publish(spark: SparkSession, cfg: Config) -> None:
    out = cfg.path("gold")
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in published_frames(spark, cfg).items():
        frame.to_parquet(out / f"{name}.parquet", index=False)
    (out / "feature_manifest.json").write_text(json.dumps(gold_layout(cfg), indent=2))
    dataset.reload()  # the manifest just changed: drop the cached copy
    print(f"[spark publish] Gold contract files -> {out}")


def run_pipeline(
    cfg: Config | None = None, spark: SparkSession | None = None, publish_gold: bool = True
) -> dict[str, float]:
    """Bronze -> Silver -> Gold (-> publish). Returns seconds per stage."""
    cfg = cfg or load_config()
    spark = spark or get_spark(cfg)
    stages = [
        ("bronze", lambda: bronze.build_bronze(spark, cfg)),
        ("silver", lambda: silver.build_silver(spark, cfg)),
        ("gold", lambda: gold.build_gold(spark, cfg)),
    ]
    if publish_gold:
        stages.append(("publish", lambda: publish(spark, cfg)))
    timings = {}
    for name, step in stages:
        start = time.perf_counter()
        step()
        timings[name] = round(time.perf_counter() - start, 2)
    print("[spark] stage seconds: " + ", ".join(f"{k} {v}" for k, v in timings.items()))
    return timings

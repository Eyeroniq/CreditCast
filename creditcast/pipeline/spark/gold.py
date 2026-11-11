"""Gold layer (Spark): the model-ready feature table + the out-of-time split.

Projects Silver into exactly the columns the DuckDB Gold writes (one shared
definition: `pipeline.gold.gold_layout` / `gold_columns`), adds the realized
LGD, and tags every loan with its out-of-time slice:

    train: vintage <= target.oot.train_vintage_end   (2019-12)
    test:  vintage >= target.oot.test_vintage_start  (2020-01)

`assert_no_oot_overlap` is the same leakage tripwire as
`pipeline.split.assert_no_vintage_overlap`, computed on the cluster: no vintage
and no loan may sit on both sides of the boundary. (The calibration and
early-stopping slices are carved from `train` later, by `pipeline.split`, when
the models are trained; that step is identical for both engines.)
"""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

from creditcast.config import Config
from creditcast.pipeline.gold import gold_columns, gold_layout
from creditcast.pipeline.spark import silver


def gold_dir(cfg: Config) -> Path:
    return cfg.path("spark") / "gold"


def realized_lgd() -> Column:
    """Loss / exposure on *resolved* defaults only, bounded to [0, 1].
    Unresolved defaults stay NULL: never a fake 0% loss."""
    known = (F.col("default_12m") == 1) & (F.col("resolved") == 1) & (F.col("ead") > 0)
    # CASE WHEN only evaluates the division where `known` holds, so ead = 0
    # never reaches it (which would raise in ANSI mode).
    return F.when(
        known, F.least(F.greatest(F.col("net_loss") / F.col("ead"), F.lit(0.0)), F.lit(1.0))
    )


def oot_slice(cfg: Config) -> Column:
    """'train' / 'test' by origination vintage; NULL for a gap between them.
    'YYYY-MM' strings compare in date order, as in pipeline.split."""
    oot = cfg.target.oot
    vintage = F.col("vintage")
    return F.when(vintage <= F.lit(str(oot.train_vintage_end)), F.lit("train")).when(
        vintage >= F.lit(str(oot.test_vintage_start)), F.lit("test")
    )


def assert_no_oot_overlap(gold: DataFrame, cfg: Config) -> None:
    """Leakage tripwire: raise if a vintage or a loan is on both sides, or a
    slice reaches across the test boundary."""
    boundary = str(cfg.target.oot.test_vintage_start)
    tagged = gold.where(F.col("split").isNotNull())
    sides = tagged.groupBy("split").agg(F.min("vintage").alias("lo"), F.max("vintage").alias("hi"))
    bounds = {r["split"]: (r["lo"], r["hi"]) for r in sides.collect()}
    if "train" in bounds and bounds["train"][1] >= boundary:
        raise AssertionError(
            f"LEAKAGE: train contains vintage >= test boundary {boundary} (max={bounds['train'][1]})"
        )
    if "test" in bounds and bounds["test"][0] < boundary:
        raise AssertionError(
            f"LEAKAGE: test contains vintage < boundary {boundary} (min={bounds['test'][0]})"
        )
    for key in ("vintage", "loan_id"):
        both = (
            tagged.groupBy(key)
            .agg(F.count_distinct("split").alias("sides"))
            .where(F.col("sides") > 1)
        )
        hit = both.select(key).limit(1).collect()
        if hit:
            raise AssertionError(f"LEAKAGE: {key} {hit[0][key]} appears in both train and test")


def build_gold(spark: SparkSession, cfg: Config) -> DataFrame:
    manifest = gold_layout(cfg)
    loans = silver.read_silver(spark, cfg)
    gold = (
        loans.withColumn("lgd", realized_lgd())
        .select(*gold_columns(manifest))
        .withColumn("split", oot_slice(cfg))
    )
    assert_no_oot_overlap(gold, cfg)

    out = gold_dir(cfg)
    gold.repartition("vintage").write.mode("overwrite").partitionBy("vintage").parquet(
        str(out / "feature_matrix")
    )
    written = spark.read.parquet(str(out / "feature_matrix"))
    by_split = {r["split"]: r["count"] for r in written.groupBy("split").count().collect()}
    n_lgd = written.where(F.col("lgd").isNotNull()).count()
    print(
        f"[spark gold] {sum(by_split.values()):,} rows | {len(manifest['numeric'])} numeric + "
        f"{len(manifest['categorical'])} categorical features | {n_lgd:,} loans with realized LGD"
        f" | OOT split train {by_split.get('train', 0):,} / test {by_split.get('test', 0):,}"
    )
    return written

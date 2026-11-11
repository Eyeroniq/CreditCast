"""Silver layer (Spark): the point-in-time 12-month default label, plus features.

A line-for-line port of `creditcast.pipeline.silver` (DuckDB SQL) to the
DataFrame API, with the same rules; see that module's docstring for why each
one matters:

1. **Forward window.** A loan observed at origination month O defaults if, in
   (O, O + 12], it reaches 90+ days past due, is REO-acquired, or leaves with a
   default-type zero-balance code.
2. **Right-censoring.** A label counts only if the whole window ends on or
   before the data cutoff, and a "no default" also needs 12 observed months or
   a clean exit (prepaid). Censored loans are dropped (`target.censoring`).
3. **Resolved-loss LGD.** Loss comes from the first terminal disposition in the
   workout window after default; a cure (back to current for `lgd.cure_months`)
   is a zero loss; unresolved defaults get no LGD.
4. **Quality gate.** Rows outside `QUALITY_RANGES` are rejected.

Then `features.add_point_in_time_features` adds the origination-time features.
All logic is built from Column expressions with config values passed in as
values (`isin(codes)`, `between(lo, hi)`), never by formatting SQL strings.
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from creditcast.config import Config
from creditcast.pipeline.silver import QUALITY_RANGES
from creditcast.pipeline.spark import bronze, features, schemas


def silver_dir(cfg: Config) -> Path:
    return cfg.path("spark") / "silver"


def month_index(col: str) -> Column:
    """'YYYY-MM' -> year * 12 + month, so month arithmetic is integer arithmetic
    (same as the DuckDB `midx` macro)."""
    return F.substring(F.col(col), 1, 4).cast("int") * 12 + F.substring(F.col(col), 6, 2).cast(
        "int"
    )


def label_loans(orig: DataFrame, perf: DataFrame, cfg: Config) -> DataFrame:
    """One row per loan: origination columns + default_12m, months_observed,
    label_complete, ead, net_loss, resolved. Censoring and the quality gate are
    applied by the caller (`build_silver`)."""
    horizon = int(cfg.target.observation_horizon_months)
    dpd_months = int(cfg.target.default_dpd_threshold) // 30  # 90 days -> 3 months
    workout = int(cfg.lgd.workout_window_months)
    cure_months = int(cfg.lgd.cure_months)
    default_codes = [str(c) for c in cfg.target.default_zb_codes]
    prepay_codes = [str(c) for c in cfg.target.prepay_zb_codes]

    # Every step below works per loan, so put each loan's months in the same
    # partition once; the joins and windows on loan_id then reuse this layout.
    perf = perf.repartition(int(cfg.spark.shuffle_partitions), "loan_id")
    events = perf.select(
        "loan_id",
        month_index("monthly_reporting_period").alias("rep_idx"),
        # 'RA' (REO acquired) isn't a number: try_cast gives NULL instead of
        # failing (plain cast raises in ANSI mode). Constant SQL, no inputs.
        F.expr("try_cast(current_loan_delinquency_status AS INT)").alias("dpd_months"),
        (F.col("current_loan_delinquency_status") == F.lit("RA")).alias("reo_acquired"),
        "zero_balance_code",
        "current_upb",
        "net_loss",
    ).cache()  # read four times below; cache instead of re-reading Parquet

    # Data cutoff = the last reporting month in the panel (one small action).
    cutoff_idx = events.agg(F.max("rep_idx")).first()[0]

    orig = orig.select(*schemas.ORIGINATION.fieldNames()).withColumn(
        "vint_idx", month_index("vintage")
    )

    # ---- the forward window (O, O + horizon]: default events and clean exits
    zb = F.col("zero_balance_code")
    window_rows = (
        events.join(orig.select("loan_id", "vint_idx"), on="loan_id")
        .where(
            (F.col("rep_idx") > F.col("vint_idx"))
            & (F.col("rep_idx") <= F.col("vint_idx") + F.lit(horizon))
        )
        .select(
            "loan_id",
            "rep_idx",
            "current_upb",
            # SQL three-valued logic, as in DuckDB: NULL OR TRUE is TRUE.
            (
                (F.col("dpd_months") >= F.lit(dpd_months))
                | F.col("reo_acquired")
                | zb.isin(default_codes)
            ).alias("is_def_event"),
            zb.isin(prepay_codes).alias("is_clean_exit"),
        )
    )

    obs = window_rows.groupBy("loan_id").agg(
        F.count_distinct("rep_idx").alias("months_observed"),
        F.bool_or(F.coalesce(F.col("is_clean_exit"), F.lit(False))).alias("exited_clean"),
    )

    # First default month per loan: row_number over the loan's default events,
    # earliest first. Its balance that month is the exposure at default (EAD).
    by_month = Window.partitionBy("loan_id").orderBy("rep_idx")
    first_default = (
        window_rows.where(F.coalesce(F.col("is_def_event"), F.lit(False)))
        .withColumn("rn", F.row_number().over(by_month))
        .where(F.col("rn") == 1)
        .select("loan_id", F.col("rep_idx").alias("def_idx"), F.col("current_upb").alias("ead"))
    )

    # Rows of defaulted loans inside the workout window after default.
    after_default = events.join(first_default.select("loan_id", "def_idx"), on="loan_id").where(
        F.col("rep_idx") <= F.col("def_idx") + F.lit(workout)
    )

    # Loss = net loss on the first terminal disposition from the default month
    # on; a prepayment after default is a cure, i.e. zero loss.
    terminal = (
        after_default.where(
            (F.col("rep_idx") >= F.col("def_idx"))
            & (zb.isin(default_codes) | zb.isin(prepay_codes))
        )
        .withColumn("rn", F.row_number().over(by_month))
        .where(F.col("rn") == 1)
        .select(
            "loan_id",
            F.when(zb.isin(prepay_codes), F.lit(0.0))
            .otherwise(F.coalesce(F.col("net_loss"), F.lit(0.0)))
            .alias("terminal_loss"),
            F.lit(True).alias("has_terminal"),
        )
    )

    # Cure: at least `cure_months` months back at current after default.
    cured = (
        after_default.where((F.col("rep_idx") > F.col("def_idx")) & (F.col("dpd_months") == 0))
        .groupBy("loan_id")
        .count()
        .where(F.col("count") >= F.lit(cure_months))
        .select("loan_id", F.lit(True).alias("cured"))
    )

    # A terminal disposition wins over an earlier cure (re-default -> loss).
    defaults = (
        first_default.join(terminal, on="loan_id", how="left")
        .join(cured, on="loan_id", how="left")
        .select(
            "loan_id",
            "def_idx",
            "ead",
            F.when(F.col("has_terminal"), F.col("terminal_loss"))
            .when(F.col("cured"), F.lit(0.0))
            .alias("net_loss"),
            (
                F.coalesce(F.col("has_terminal"), F.lit(False))
                | F.coalesce(F.col("cured"), F.lit(False))
            ).alias("is_resolved"),
        )
    )

    months_observed = F.coalesce(F.col("months_observed"), F.lit(0))
    defaulted = F.col("def_idx").isNotNull()
    window_complete = F.col("vint_idx") + F.lit(horizon) <= F.lit(cutoff_idx)
    return (
        orig.join(obs, on="loan_id", how="left")
        .join(defaults, on="loan_id", how="left")
        .select(
            *schemas.ORIGINATION.fieldNames(),
            F.when(defaulted, 1).otherwise(0).alias("default_12m"),
            months_observed.alias("months_observed"),
            F.when(
                window_complete
                & (
                    defaulted
                    | (months_observed >= F.lit(horizon))
                    | F.coalesce(F.col("exited_clean"), F.lit(False))
                ),
                1,
            )
            .otherwise(0)
            .alias("label_complete"),
            "ead",
            "net_loss",
            F.when(F.col("is_resolved"), 1).otherwise(0).alias("resolved"),
        )
    )


def quality_mask(ranges: dict[str, tuple[float, float]] = QUALITY_RANGES) -> Column:
    """TRUE when every checked column is inside its plausible range. A NULL
    value counts as out of range (as pandas `between` does)."""
    inside = [F.coalesce(F.col(c).between(lo, hi), F.lit(False)) for c, (lo, hi) in ranges.items()]
    return reduce(lambda a, b: a & b, inside)


def build_silver(spark: SparkSession, cfg: Config) -> dict:
    orig = bronze.read_bronze(spark, cfg, "origination")
    perf = bronze.read_bronze(spark, cfg, "performance")
    labelled = label_loans(orig, perf, cfg).cache()

    # One pass for the counts the DuckDB layer prints.
    horizon = int(cfg.target.observation_horizon_months)
    counts = labelled.agg(
        F.count(F.lit(1)).alias("n_in"),
        F.sum(1 - F.col("label_complete")).alias("n_censored"),
    ).first()

    # ---- right-censoring: only trust labels from a complete window ----------
    kept = labelled
    if str(cfg.target.censoring) == "drop":
        kept = kept.where(F.col("label_complete") == 1)

    # ---- data-quality gate --------------------------------------------------
    ok = quality_mask()
    gated = kept.withColumn("_ok", ok)
    rejected = gated.where(~F.col("_ok")).count()
    loans = gated.where(F.col("_ok")).drop("_ok")

    # ---- point-in-time features (origination-time information only) --------
    unemployment, hpi = features.read_macro_series(spark, cfg)
    loans, benchmark, macro_tbl = features.add_point_in_time_features(loans, unemployment, hpi, cfg)

    out = silver_dir(cfg)
    loans.repartition("vintage").write.mode("overwrite").partitionBy("vintage").parquet(
        str(out / "loans")
    )
    # The two lookup tables are tiny: one file each.
    benchmark.coalesce(1).write.mode("overwrite").parquet(str(out / "rate_benchmark"))
    macro_tbl.coalesce(1).write.mode("overwrite").parquet(str(out / "macro_features"))

    written = spark.read.parquet(str(out / "loans"))
    stats = written.agg(
        F.count(F.lit(1)).alias("n"),
        F.avg("default_12m").alias("rate"),
        F.sum("default_12m").alias("n_def"),
        F.sum("resolved").alias("n_res"),
    ).first()
    spark.catalog.clearCache()  # the table is on disk: release the cached inputs

    print(
        f"[spark silver] {counts['n_in']:,} loans in, {counts['n_censored']:,} censored "
        f"(incomplete {horizon}m window, policy={cfg.target.censoring}), {rejected:,} rejected "
        f"by quality gate, {stats['n']:,} out | 12m default rate {stats['rate']:.2%}"
    )
    print(
        f"[spark silver] {stats['n_res']:,}/{stats['n_def']:,} defaults resolved within the "
        f"{int(cfg.lgd.workout_window_months)}m workout window (LGD population)"
    )
    return {
        "loans_in": int(counts["n_in"]),
        "censored": int(counts["n_censored"]),
        "rejected": int(rejected),
        "loans_out": int(stats["n"]),
    }


def read_silver(spark: SparkSession, cfg: Config, table: str = "loans") -> DataFrame:
    return spark.read.parquet(str(silver_dir(cfg) / table))

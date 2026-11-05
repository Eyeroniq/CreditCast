"""Point-in-time features (Spark): only what a lender knows on the origination date.

The Spark version of `creditcast.features.engineer` + `pipeline.macro.macro_table`,
written with Window functions. "Point in time" means a loan originated in month
M may only use data from months before M:

- **rate_spread**: the loan's note rate minus the average note rate of loans
  originated in the 3 months *strictly before* M (a rolling aggregate whose
  frame is `rowsBetween(-3, -1)`: the current month is excluded).
- **macro features**: state unemployment and house prices at M - lag (`lag()`
  over each state's monthly series), and their 12-month changes.
- **ltv_dti, high_ltv**: the loan's own origination fields.

Two exceptions are inherited on purpose from the DuckDB/pandas pipeline, so the
engines agree exactly: the first month in the data has no earlier months, so
its benchmark is taken from the next month (built from the first month's own
loans; always a training vintage, never in the out-of-time test); and a month
missing from a lookup table falls back to the latest month (what a lender would
use for a brand-new application).

`round_half_even` reproduces pandas' `.round()` bit for bit (numpy multiplies,
rounds half to even with rint, then divides), which is what lets the parity
test demand equal values rather than "close enough".
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from creditcast.config import Config
from creditcast.features import BENCHMARK_WINDOW_MONTHS
from creditcast.pipeline.macro import NATIONAL
from creditcast.pipeline.spark import schemas


def month_index(col: Column) -> Column:
    """'YYYY-MM' -> year * 12 + month."""
    return F.substring(col, 1, 4).cast("int") * 12 + F.substring(col, 6, 2).cast("int")


def month_label(idx: Column) -> Column:
    """Inverse of month_index: year * 12 + month -> 'YYYY-MM'."""
    year = F.floor((idx - 1) / 12)
    return F.format_string("%04d-%02d", year, idx - year * 12)


def round_half_even(col: Column, digits: int) -> Column:
    """pandas/numpy `.round(digits)`: scale, round half to even, unscale.
    (Spark's round() rounds half up and bround() works on exact decimals; both
    can differ from pandas in the last digit.)"""
    scale = float(10**digits)
    return F.rint(col * F.lit(scale)) / F.lit(scale)


# ---- rate benchmark --------------------------------------------------------------
def rate_benchmark(loans: DataFrame, window: int = BENCHMARK_WINDOW_MONTHS) -> DataFrame:
    """One row per month (first vintage .. last vintage + 1): `vintage`,
    `rate_benchmark` = average note rate of loans from the `window` prior months."""
    spark = loans.sparkSession
    totals = loans.groupBy(month_index(F.col("vintage")).alias("idx")).agg(
        F.sum("orig_interest_rate").alias("rate_sum"),
        F.count("orig_interest_rate").alias("rate_n"),
    )
    lo, hi = totals.agg(F.min("idx"), F.max("idx")).first()
    # Dense calendar so "the previous 3 rows" means "the previous 3 months" even
    # if a month had no loans; +1 month so tomorrow's application has a value.
    calendar = spark.range(lo, hi + 2).withColumnRenamed("id", "idx")
    dense = calendar.join(F.broadcast(totals), on="idx", how="left").fillna(
        0, subset=["rate_sum", "rate_n"]
    )

    # No partitionBy: the whole calendar (~100 rows) is one ordered series, so
    # Spark moves it to one partition. Fine at this size, never for a big table.
    in_order = Window.orderBy("idx")
    prior = in_order.rowsBetween(-window, -1)  # the `window` months before, not this one
    raw = F.when(
        F.sum("rate_n").over(prior) > 0, F.sum("rate_sum").over(prior) / F.sum("rate_n").over(prior)
    )
    filled = dense.withColumn("raw", raw).withColumn(
        # back-fill: the first month takes the next value (see module docstring)
        "bfill",
        F.first("raw", ignorenulls=True).over(in_order.rowsBetween(0, Window.unboundedFollowing)),
    )
    return filled.select(
        "idx",
        month_label(F.col("idx")).alias("vintage"),
        # forward-fill: carry the last known value to the end
        F.last("bfill", ignorenulls=True)
        .over(in_order.rowsBetween(Window.unboundedPreceding, 0))
        .alias("rate_benchmark"),
    )


# ---- macro features ---------------------------------------------------------------
def read_macro_series(spark: SparkSession, cfg: Config) -> tuple[DataFrame, DataFrame]:
    """The monthly state series written by the generator (or real CSVs)."""
    d = cfg.path("macro")

    def read(name: str) -> DataFrame:
        return (
            spark.read.schema(schemas.MACRO_SERIES)
            .option("header", True)
            .csv(str(d / f"{name}.csv"))
        )

    return read("unemployment"), read("hpi")


def macro_table(unemployment: DataFrame, hpi: DataFrame, lag: int) -> DataFrame:
    """(state, vintage) -> unemp_rate, unemp_chg_12m, hpi_chg_12m, where the row
    for month M uses the series at M - lag (published by then) and the 12-month
    changes compare M - lag with M - lag - 12. A national row (state "US", the
    average of the states) covers loans from states with no series."""
    if lag < 1:
        raise ValueError("macro lag must be >= 1 month (values known at origination)")

    def with_national(series: DataFrame) -> DataFrame:
        series = series.withColumn("idx", month_index(F.col("month")))
        national = (
            series.groupBy("idx")
            .agg(F.avg("value").alias("value"))
            .withColumn("state", F.lit(NATIONAL))
        )
        return series.select("state", "idx", "value").unionByName(
            national.select("state", "idx", "value")
        )

    u, h = with_national(unemployment), with_national(hpi)
    lo, hi = u.agg(F.min("idx"), F.max("idx")).first()
    spark = unemployment.sparkSession
    # Every (state, month) pair, so lag(n) means "n months earlier" even if a
    # state skipped a month; `lag` extra months so the next month has values.
    grid = (
        u.select("state")
        .distinct()
        .crossJoin(spark.range(lo, hi + lag + 1).withColumnRenamed("id", "idx"))
    )
    series = grid.join(u.withColumnRenamed("value", "u"), on=["state", "idx"], how="left").join(
        h.withColumnRenamed("value", "h"), on=["state", "idx"], how="left"
    )

    by_state = Window.partitionBy("state").orderBy("idx")
    u_now, u_year_ago = F.lag("u", lag).over(by_state), F.lag("u", lag + 12).over(by_state)
    h_now, h_year_ago = F.lag("h", lag).over(by_state), F.lag("h", lag + 12).over(by_state)
    table = series.select(
        "state",
        "idx",
        month_label(F.col("idx")).alias("vintage"),
        round_half_even(u_now, 3).alias("unemp_rate"),
        round_half_even(u_now - u_year_ago, 3).alias("unemp_chg_12m"),
        round_half_even((h_now / h_year_ago - 1) * 100, 3).alias("hpi_chg_12m"),
    )
    # Months without 12 months of history have no 12m change: drop them.
    return table.dropna(subset=["unemp_rate", "unemp_chg_12m", "hpi_chg_12m"])


def lookup_macro(loans: DataFrame, table: DataFrame, columns: list[str]) -> DataFrame:
    """Add the macro columns for each loan's (property_state, vintage).
    Unknown state -> the national row; a month missing from the table -> the
    latest month for that state."""
    states = [r["state"] for r in table.select("state").distinct().collect()]
    loans = loans.withColumn(
        "_state",
        F.when(F.col("property_state").isin(states), F.col("property_state")).otherwise(
            F.lit(NATIONAL)
        ),
    )
    # row_number picks each state's latest month for the fallback.
    newest_first = Window.partitionBy("state").orderBy(F.desc("idx"))
    latest = (
        table.withColumn("rn", F.row_number().over(newest_first))
        .where(F.col("rn") == 1)
        .select(F.col("state").alias("_state"), *[F.col(c).alias(f"_latest_{c}") for c in columns])
    )
    exact = table.select(F.col("state").alias("_state"), "vintage", *columns)
    # Both lookup tables are a few thousand rows: broadcast them to every
    # executor instead of shuffling the loan table to meet them.
    joined = loans.join(F.broadcast(exact), on=["_state", "vintage"], how="left").join(
        F.broadcast(latest), on="_state", how="left"
    )
    for c in columns:
        joined = joined.withColumn(c, F.coalesce(F.col(c), F.col(f"_latest_{c}")))
    return joined.drop("_state", *[f"_latest_{c}" for c in columns])


# ---- all features ---------------------------------------------------------------
def add_point_in_time_features(
    loans: DataFrame, unemployment: DataFrame, hpi: DataFrame, cfg: Config
) -> tuple[DataFrame, DataFrame, DataFrame]:
    """Loans + ltv_dti, rate_spread, high_ltv and the macro features. Also
    returns the benchmark and macro tables, which serving needs to compute the
    same features for a new application."""
    # Both lookup tables are used several times (lookup, fallback, writing):
    # cache them so their window functions run once.
    benchmark = rate_benchmark(loans).cache()
    latest_benchmark = benchmark.orderBy(F.desc("idx")).first()["rate_benchmark"]
    bench = F.broadcast(benchmark.select("vintage", "rate_benchmark"))

    macro_cols = list(cfg.macro.features)
    table = macro_table(unemployment, hpi, int(cfg.macro.lag_months)).cache()

    out = (
        loans.join(bench, on="vintage", how="left")
        .withColumn(
            "rate_spread",
            round_half_even(
                F.col("orig_interest_rate")
                - F.coalesce(F.col("rate_benchmark"), F.lit(latest_benchmark)),
                3,
            ),
        )
        .drop("rate_benchmark")
        # thin equity AND a stretched borrower compound the risk
        .withColumn("ltv_dti", round_half_even(F.col("ltv") * F.col("dti") / F.lit(100.0), 2))
        .withColumn("high_ltv", (F.col("ltv") > F.lit(80)).cast("long"))  # PMI boundary
    )
    out = lookup_macro(out, table, macro_cols)
    return out, benchmark, table.select("state", "vintage", "idx", *macro_cols)

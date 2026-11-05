"""Bronze layer (Spark): raw landing files -> typed, partitioned Parquet.

Bronze keeps the data as it arrived (no cleaning, no business rules) but makes
it safe to build on:

1. **Contract check.** Every landing file's declared columns and types are
   compared with `schemas.py` before any data is read; drift fails the run.
2. **Explicit schema read.** Spark reads with the StructType, never inferring.
3. **Key checks.** Null or duplicate keys (loan_id; loan_id + month) would
   double-count loans downstream, so they stop the run here.
4. **Lineage.** `_source_file` and `_ingested_at` say where each row came from.
5. **Partitioned by origination vintage.** Both tables are written as
   `vintage=YYYY-MM/` folders, so a query for some vintages (the out-of-time
   test, a monthly refresh) only opens those folders (partition pruning).

The landing zone is `paths.bronze`: the generator writes there, and real
Freddie Mac files would land there too. Spark Bronze goes to `paths.spark`.
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

from creditcast.config import Config
from creditcast.pipeline.spark import schemas

LINEAGE = [
    StructField("_source_file", StringType()),
    StructField("_ingested_at", TimestampType()),
]


class ContractError(ValueError):
    """A landing file doesn't match its schema contract, or has bad keys."""


def bronze_dir(cfg: Config) -> Path:
    return cfg.path("spark") / "bronze"


def bronze_schema(contract: StructType) -> StructType:
    """The Bronze table schema: contract + vintage (partition column) + lineage."""
    fields = list(contract.fields)
    if "vintage" not in contract.fieldNames():
        fields.append(StructField("vintage", StringType(), nullable=False))
    return StructType(fields + LINEAGE)


def check_contract(spark: SparkSession, path: str, contract: StructType) -> None:
    """Compare the files' own Parquet schema (from their footers: metadata, not
    a scan of the data) with the contract. Extra columns are allowed and dropped;
    a missing or retyped column is an error, because reading it with the
    explicit schema would silently produce NULLs."""
    declared = {f.name: f.dataType for f in spark.read.parquet(path).schema.fields}
    problems = []
    for field in contract.fields:
        if field.name not in declared:
            problems.append(f"missing column {field.name!r}")
        elif declared[field.name] != field.dataType:
            problems.append(
                f"{field.name!r} is {declared[field.name].simpleString()}, "
                f"contract says {field.dataType.simpleString()}"
            )
    if problems:
        raise ContractError(f"{path}: " + "; ".join(problems))


def _check_keys(df: DataFrame, keys: list[str], table: str) -> None:
    """No NULL keys and no duplicate keys, in one pass over the data."""
    any_null = reduce(lambda a, b: a | b, [F.col(k).isNull() for k in keys])
    row = df.agg(
        F.count(F.lit(1)).alias("rows"),
        # count_distinct over the key ignores rows where any key is NULL
        F.count_distinct(*[F.col(k) for k in keys]).alias("distinct_keys"),
        F.sum(F.when(any_null, 1).otherwise(0)).alias("null_keys"),
    ).first()
    if row["null_keys"]:
        raise ContractError(f"{table}: {row['null_keys']:,} rows with a NULL key {keys}")
    if row["distinct_keys"] != row["rows"]:
        dupes = row["rows"] - row["distinct_keys"]
        raise ContractError(f"{table}: {dupes:,} duplicate rows on key {keys}")


def _with_lineage(df: DataFrame) -> DataFrame:
    # `_metadata` is a hidden column Spark exposes for file sources.
    return df.withColumn("_source_file", F.col("_metadata.file_path")).withColumn(
        "_ingested_at", F.current_timestamp()
    )


def build_bronze(spark: SparkSession, cfg: Config) -> dict[str, int]:
    landing = cfg.path("bronze")
    out = bronze_dir(cfg)
    orig_src = str(landing / "origination")
    perf_src = str(landing / "performance")

    check_contract(spark, orig_src, schemas.ORIGINATION)
    check_contract(spark, perf_src, schemas.PERFORMANCE)

    orig = _with_lineage(spark.read.schema(schemas.ORIGINATION).parquet(orig_src))
    perf = _with_lineage(spark.read.schema(schemas.PERFORMANCE).parquet(perf_src))
    _check_keys(orig, ["loan_id"], "origination")
    _check_keys(perf, ["loan_id", "monthly_reporting_period"], "performance")

    # Performance rows don't carry the vintage; take it from origination so
    # both tables share one partition layout. (No broadcast hint: on real
    # Freddie data origination has tens of millions of rows. Spark still
    # broadcasts it automatically when it is under autoBroadcastJoinThreshold.)
    perf = perf.join(orig.select("loan_id", "vintage"), on="loan_id", how="inner")

    # repartition("vintage") sends each vintage to one task, so partitionBy
    # writes one file per vintage folder instead of one per task per folder
    # (the classic "small files" problem).
    for name, df in (("origination", orig), ("performance", perf)):
        (
            df.repartition("vintage")
            .write.mode("overwrite")
            .partitionBy("vintage")
            .parquet(str(out / name))
        )

    counts = {
        "origination": spark.read.parquet(str(out / "origination")).count(),
        "performance": spark.read.parquet(str(out / "performance")).count(),
    }
    print(
        f"[spark bronze] {counts['origination']:,} loans, "
        f"{counts['performance']:,} loan-months -> {out} (partitioned by vintage)"
    )
    return counts


def read_bronze(spark: SparkSession, cfg: Config, table: str) -> DataFrame:
    """Read a Bronze table back with its explicit schema (incl. the partition
    column, so Spark doesn't guess the type of 'vintage=2015-01' either)."""
    contract = {"origination": schemas.ORIGINATION, "performance": schemas.PERFORMANCE}[table]
    return spark.read.schema(bronze_schema(contract)).parquet(str(bronze_dir(cfg) / table))

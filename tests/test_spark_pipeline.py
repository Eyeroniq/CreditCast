"""Spark engine (ROADMAP 7.0): parity with DuckDB, point-in-time features, the
out-of-time split and the Bronze data contract.

Builds one small synthetic book in a temp folder, runs the DuckDB pipeline and
the Spark pipeline on it (Spark on local[2]), and compares. Needs PySpark and
Java 17+ (CI's spark job, Dockerfile.spark); skipped cleanly anywhere else.
"""

import json
import os
import shutil

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from creditcast import config as config_mod
from creditcast import dataset
from creditcast.config import DEFAULT_CONFIG_PATH, load_config
from creditcast.pipeline.spark.session import SparkUnavailableError, check_spark_available

try:
    check_spark_available()
except SparkUnavailableError as exc:
    pytest.skip(f"Spark engine unavailable: {exc}", allow_module_level=True)

from pyspark.sql import functions as F  # noqa: E402  (only importable past the skip)

from creditcast.pipeline.spark import bronze, features, gold, parity, silver  # noqa: E402
from creditcast.pipeline.spark.run import run_pipeline  # noqa: E402
from creditcast.pipeline.spark.session import get_spark  # noqa: E402

N_LOANS = 3000
FEATURES = ["rate_spread", "ltv_dti", "high_ltv", "unemp_rate", "unemp_chg_12m", "hpi_chg_12m"]


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    """Generate a book, run DuckDB (publishing Gold) and Spark (not publishing)."""
    tmp = tmp_path_factory.mktemp("spark_book")
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    dirs = ("bronze", "silver", "gold", "macro", "spark", "artifacts", "reports")
    raw["paths"] = {**{d: str(tmp / d) for d in dirs}, "model_card": str(tmp / "model_card.md")}
    raw["generator"]["n_loans"] = N_LOANS
    raw["tracking"] = {"enabled": False}
    raw["spark"]["shuffle_partitions"] = 4
    cfg_file = tmp / "config.yaml"
    cfg_file.write_text(yaml.safe_dump(raw), encoding="utf-8")

    previous = os.environ.get("CREDITCAST_CONFIG")
    os.environ["CREDITCAST_CONFIG"] = str(cfg_file)
    config_mod.reload()
    dataset.reload()
    try:
        from creditcast.pipeline.generate import generate
        from creditcast.pipeline.gold import build_gold
        from creditcast.pipeline.silver import build_silver

        cfg = load_config()
        generate(cfg)
        build_silver(cfg)
        build_gold(cfg)
        spark = get_spark(cfg, master="local[2]")
        timings = run_pipeline(cfg, spark, publish_gold=False)
        yield {"cfg": cfg, "spark": spark, "tmp": tmp, "timings": timings}
    finally:
        if previous is None:
            os.environ.pop("CREDITCAST_CONFIG", None)
        else:
            os.environ["CREDITCAST_CONFIG"] = previous
        config_mod.reload()
        dataset.reload()


# ---- parity -----------------------------------------------------------------------
def test_gold_is_identical_to_duckdb(book):
    report = parity.compare(book["spark"], book["cfg"])
    assert report["ok"], json.dumps(report, indent=2)
    fm = report["feature_matrix"]
    assert fm["rows"][0] == fm["rows"][1] > 2000  # most of the 3,000 loans survive censoring
    assert fm["keys_equal"]
    # labels, LGD and every engineered feature agree exactly, not just closely
    for col in ["default_12m", "resolved", "ead", "net_loss", "lgd", *FEATURES]:
        assert fm["max_abs_diff"][col] == 0.0, col


def test_silver_label_counts_match_duckdb(book):
    duck = pd.read_parquet(book["cfg"].path("silver") / "loans.parquet")
    spk = silver.read_silver(book["spark"], book["cfg"]).toPandas()
    assert len(spk) == len(duck)
    assert spk["default_12m"].sum() == duck["default_12m"].sum()
    assert spk["resolved"].sum() == duck["resolved"].sum()
    assert spk["months_observed"].sum() == duck["months_observed"].sum()


def test_round_half_even_matches_pandas(book):
    values = [0.0005, 0.0015, 0.0025, 1.0005, 2.675, -0.0015, 0.1234567, 12.3445]
    df = book["spark"].createDataFrame([(v,) for v in values], ["x"])
    got = [r["r"] for r in df.select(features.round_half_even(F.col("x"), 3).alias("r")).collect()]
    assert got == pd.Series(values).round(3).tolist()


# ---- point-in-time (no lookahead) ----------------------------------------------------
def _features_at(loans, unemployment, hpi, cfg):
    out, _, _ = features.add_point_in_time_features(loans, unemployment, hpi, cfg)
    return out.select("loan_id", "vintage", *FEATURES).toPandas().sort_values("loan_id")


def test_point_in_time_features_ignore_later_data(book):
    """Changing everything after month t must not move any feature of a loan
    originated in month t or earlier."""
    spark, cfg = book["spark"], book["cfg"]
    t = "2018-06"
    loans = silver.read_silver(spark, cfg).drop(*FEATURES)
    unemployment, hpi = features.read_macro_series(spark, cfg)
    before = _features_at(loans, unemployment, hpi, cfg)

    later = F.col("vintage") > F.lit(t)
    loans_changed = loans.withColumn(
        "orig_interest_rate",
        F.when(later, F.col("orig_interest_rate") + 3.0).otherwise(F.col("orig_interest_rate")),
    ).withColumn("ltv", F.when(later, F.col("ltv") + 7).otherwise(F.col("ltv")))
    # a loan from month t sees macro data up to t - 1, so change month t onward
    from_t = F.col("month") >= F.lit(t)
    unemp_changed = unemployment.withColumn(
        "value", F.when(from_t, F.col("value") * 1.5).otherwise(F.col("value"))
    )
    hpi_changed = hpi.withColumn(
        "value", F.when(from_t, F.col("value") * 0.8).otherwise(F.col("value"))
    )
    after = _features_at(loans_changed, unemp_changed, hpi_changed, cfg)

    early_b = before[before["vintage"] <= t].reset_index(drop=True)
    early_a = after[after["vintage"] <= t].reset_index(drop=True)
    assert len(early_b) > 500
    pd.testing.assert_frame_equal(early_b, early_a)
    # ...and the change did reach the later loans, so the test can fail
    late_b, late_a = before[before["vintage"] > t], after[after["vintage"] > t]
    for col in ["rate_spread", "ltv_dti", "unemp_rate", "hpi_chg_12m"]:
        assert (late_b[col].to_numpy() != late_a[col].to_numpy()).any(), col


# ---- out-of-time split ----------------------------------------------------------------
def _spark_gold(book):
    return book["spark"].read.parquet(str(gold.gold_dir(book["cfg"]) / "feature_matrix"))


def test_oot_split_has_no_loan_or_vintage_on_both_sides(book):
    g = _spark_gold(book).toPandas()
    oot = book["cfg"].target.oot
    assert set(g["split"]) == {"train", "test"}  # the boundary leaves no gap
    assert g.loc[g["split"] == "train", "vintage"].max() <= oot.train_vintage_end
    assert g.loc[g["split"] == "test", "vintage"].min() >= oot.test_vintage_start
    assert g.groupby("vintage")["split"].nunique().max() == 1
    assert g.groupby("loan_id")["split"].nunique().max() == 1
    assert not set(g.loc[g["split"] == "train", "loan_id"]) & set(
        g.loc[g["split"] == "test", "loan_id"]
    )


def test_oot_tripwire_catches_a_vintage_across_the_boundary(book):
    g = _spark_gold(book)
    bad = g.withColumn(
        "split", F.when(F.col("vintage") == "2020-01", "train").otherwise(F.col("split"))
    )
    with pytest.raises(AssertionError, match="LEAKAGE: train contains vintage"):
        gold.assert_no_oot_overlap(bad, book["cfg"])


def test_oot_tripwire_catches_a_loan_on_both_sides(book):
    g = _spark_gold(book)
    one = g.where(F.col("split") == "train").limit(1)
    twin = one.withColumn("split", F.lit("test")).withColumn("vintage", F.lit("2020-06"))
    with pytest.raises(AssertionError, match="LEAKAGE: loan_id"):
        gold.assert_no_oot_overlap(g.unionByName(twin), book["cfg"])


# ---- Bronze: partitions, lineage, contract ---------------------------------------------
def test_bronze_is_partitioned_by_vintage_with_lineage(book):
    cfg = book["cfg"]
    folders = sorted(
        p.name for p in (bronze.bronze_dir(cfg) / "origination").iterdir() if p.is_dir()
    )
    vintages = pd.read_parquet(cfg.path("bronze") / "origination")["vintage"].unique()
    assert folders == sorted(f"vintage={v}" for v in vintages)
    perf = bronze.read_bronze(book["spark"], cfg, "performance")
    assert perf.where(F.col("_source_file").isNull() | F.col("_ingested_at").isNull()).count() == 0
    assert perf.where(~F.col("_source_file").endswith(".parquet")).count() == 0
    assert perf.count() == pd.read_parquet(cfg.path("bronze") / "performance").shape[0]


def test_contract_rejects_a_retyped_column(book, tmp_path):
    src = pd.read_parquet(book["cfg"].path("bronze") / "origination").head(50)
    src["fico"] = src["fico"].astype(str)  # e.g. a vendor file with quoted numbers
    src.to_parquet(tmp_path / "orig.parquet", index=False)
    with pytest.raises(bronze.ContractError, match="'fico' is string, contract says bigint"):
        bronze.check_contract(book["spark"], str(tmp_path), bronze.schemas.ORIGINATION)


def test_contract_rejects_a_missing_column(book, tmp_path):
    src = pd.read_parquet(book["cfg"].path("bronze") / "origination").head(50).drop(columns="dti")
    src.to_parquet(tmp_path / "orig.parquet", index=False)
    with pytest.raises(bronze.ContractError, match="missing column 'dti'"):
        bronze.check_contract(book["spark"], str(tmp_path), bronze.schemas.ORIGINATION)


def test_duplicate_keys_are_rejected(book):
    rows = book["spark"].createDataFrame(
        [(1, "2020-01"), (1, "2020-01"), (2, "2020-01")], ["loan_id", "m"]
    )
    with pytest.raises(bronze.ContractError, match="1 duplicate rows"):
        bronze._check_keys(rows, ["loan_id", "m"], "performance")


# ---- the engine switch publishes interchangeable Gold -------------------------------
def test_cli_spark_engine_publishes_the_same_gold_files(book):
    cfg = book["cfg"]
    gold_dir = cfg.path("gold")
    duck_copy = book["tmp"] / "gold_duckdb"
    shutil.copytree(gold_dir, duck_copy)
    from creditcast import cli

    result = CliRunner().invoke(cli.app, ["pipeline", "--engine", "spark"])
    assert result.exit_code == 0, result.output
    assert json.loads((gold_dir / "feature_manifest.json").read_text()) == json.loads(
        (duck_copy / "feature_manifest.json").read_text()
    )
    for name in ("feature_matrix", "rate_benchmark", "macro_features"):
        duck = pd.read_parquet(duck_copy / f"{name}.parquet")
        spk = pd.read_parquet(gold_dir / f"{name}.parquet")
        # same columns, dtypes (incl. categoricals) and row order
        pd.testing.assert_frame_equal(duck, spk, check_exact=False, rtol=0, atol=1e-9)

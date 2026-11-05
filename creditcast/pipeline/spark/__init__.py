"""PySpark engine for the Bronze -> Silver -> Gold pipeline (ROADMAP 7.0).

The same pipeline as `creditcast.pipeline.silver` / `gold` (DuckDB + pandas),
written for Spark so it can run on a cluster when the loan book outgrows one
machine. `python -m creditcast.cli pipeline --engine spark` runs it; the default
engine stays DuckDB. `parity.compare` proves both engines write the same Gold.

    session.py   SparkSession factory + the Java 17 check
    schemas.py   explicit StructType contracts for every raw input
    bronze.py    landing files -> Bronze Parquet, partitioned by vintage
    silver.py    point-in-time 12m default label, censoring, LGD fields
    features.py  point-in-time features with Window functions (no lookahead)
    gold.py      model-ready feature table + out-of-time split tripwire
    run.py       runs the stages and publishes Gold for training / serving
    parity.py    Spark Gold vs DuckDB Gold, column by column

Needs `pip install -r requirements-spark.txt` and Java 17+ (see docs/pyspark.md).
"""

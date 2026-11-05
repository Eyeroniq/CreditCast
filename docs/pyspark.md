# PySpark engine (ROADMAP 7.0)

A Spark version of Bronze -> Silver -> Gold (`creditcast/pipeline/spark/`), next to
the DuckDB engine, which stays the default. Both write the same Gold files.

## Run it
Needs Java 17+ and `pip install -r requirements-spark.txt`; easiest in the container:

    docker build -f Dockerfile.spark -t creditcast-spark .
    docker run --rm -v "$PWD:/app" creditcast-spark python -m creditcast.cli pipeline --engine spark
    docker run --rm -v "$PWD:/app" creditcast-spark python -m creditcast.cli parity
    docker run --rm -v "$PWD:/app" creditcast-spark python -m pytest -q tests/test_spark_*.py

Without Java 17 / PySpark, `--engine spark` exits 2 with a one-line fix.

## Benchmark (preliminary)
`scripts/benchmark_engines.py --rows 1000000 10000000` writes `docs/benchmarks/`.
Only a smoke run has been done so far (12 CPUs, 7.6 GB Docker VM):

| Performance rows | DuckDB | Spark local[*] |
|---:|---:|---:|
| ~200,000 | 1.9 s, 225 MB | 93.6 s, 4,031 MB |

The 1M / 10M runs are still to do. Spark's time at this size is mostly JVM
start-up and per-stage job overhead; it has not been profiled yet.

## When I'd pick which
- **DuckDB**: anything that fits on one machine (this project today, and books up to
  hundreds of millions of rows on a big box). Faster, far less memory, simpler.
- **Spark**: data that doesn't fit one machine, or that already lives in a
  Spark/Databricks lake (e.g. the full Freddie Mac history at loan-month grain), where
  the cluster, partitioned Parquet and shared Gold tables matter more than latency.

## Known limits
- PySpark 4.2.1 warns it doesn't fully support pandas 3; we only use `toPandas()`
  over Arrow, and the parity tests check its output values and dtypes.
- Two documented exceptions carried over from the DuckDB engine: the first month's
  rate benchmark is back-filled, and missing months fall back to the latest month.

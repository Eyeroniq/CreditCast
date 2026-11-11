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

## Benchmark
`scripts/benchmark_engines.py` (results in [benchmarks/engines.md](benchmarks/engines.md)):
each engine runs `cli pipeline --engine <engine>` in its own process, from the same
Bronze files to the same published Gold, after one unmeasured warm-up run. Peak memory
covers the whole process tree, Spark's JVM included. One machine: 12 CPUs, 7.6 GB
(Docker on WSL2), Spark `local[*]` with a 4 GB driver.

| Performance rows | Loans | DuckDB | Spark | DuckDB peak | Spark peak |
|---:|---:|---:|---:|---:|---:|
| 200,545 | 10,050 | 1.2 s | 26.5 s | 223 MB | 2,365 MB |
| 1,001,630 | 50,251 | 1.4 s | 26.7 s | 380 MB | 2,089 MB |
| 10,028,583 | 502,513 | 5.6 s | 51.1 s | 1,916 MB | 4,851 MB |

What it shows:
- **Spark's time is mostly fixed cost.** 200k and 1M rows take the same ~26.5 s:
  JVM start-up plus Spark's per-job overhead (every write, `count()` and `first()` is
  a separate job; the pipeline runs about 20). Going from 1M to 10M rows adds ~24 s.
- **DuckDB wins at every size on one machine**: 9x faster and 2.5x less memory at
  10M rows. It's a vectorised, in-process engine with no JVM, no task scheduling and
  no shuffles between processes.
- **Spark's memory is mostly JVM heap**: with a 4 GB driver it takes ~2 GB before
  the data gets big. It's a sizing choice, not what the data needs.
- An early 94 s run at 200k rows was a cold start (the first JVM in a fresh container
  loads PySpark's jars from disk); hence the warm-up.

## When I'd pick which
- **DuckDB**: anything that fits on one machine: this project today, and well past
  the 10M rows measured here (DuckDB can also spill to disk). Faster, far less memory,
  simpler to run and debug.
- **Spark**: data that doesn't fit one machine, or that already lives in a
  Spark/Databricks lake (e.g. the full Freddie Mac history at loan-month grain), where
  the cluster, partitioned Parquet and shared Gold tables matter more than latency.

## Known limits
- PySpark 4.2.1 warns it doesn't fully support pandas 3; we only use `toPandas()`
  over Arrow, and the parity tests check its output values and dtypes.
- Two documented exceptions carried over from the DuckDB engine: the first month's
  rate benchmark is back-filled, and missing months fall back to the latest month.

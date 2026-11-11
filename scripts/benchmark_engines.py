"""Benchmark the two pipeline engines: DuckDB vs Spark (local mode).

For each size, generates a synthetic book with about that many performance
rows (loan-months), then times `python -m creditcast.cli pipeline --engine X`
for each engine in its own process. Both runs end at the same point: the Gold
files training reads. Reports wall time and peak memory of the whole process
tree (Spark's JVM is a child process, so it's included).

Runs where both engines can, i.e. in the Spark container:

    docker build -f Dockerfile.spark -t creditcast-spark .
    docker run --rm -v "$PWD:/app" creditcast-spark \\
        python scripts/benchmark_engines.py --rows 1000000 10000000

Writes docs/benchmarks/engines.json and engines.md.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from creditcast.config import DEFAULT_CONFIG_PATH  # noqa: E402

ROWS_PER_LOAN = 19.9  # performance rows per loan in the default generator config


def write_config(workdir: Path, n_loans: int, driver_memory: str) -> Path:
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    dirs = ("bronze", "silver", "gold", "macro", "spark", "artifacts", "reports")
    raw["paths"] = {**{d: str(workdir / d) for d in dirs}, "model_card": str(workdir / "card.md")}
    raw["generator"]["n_loans"] = n_loans
    raw["tracking"] = {"enabled": False}
    raw["spark"]["driver_memory"] = driver_memory
    path = workdir / "config.yaml"
    workdir.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def run_measured(args: list[str], env: dict, log: Path) -> dict:
    """Run a command; return wall seconds, peak RSS of the process tree, output."""
    with open(log, "w", encoding="utf-8") as fh:
        start = time.perf_counter()
        proc = subprocess.Popen(args, cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT)
        root = psutil.Process(proc.pid)
        peak = 0
        # Sample the memory of the process and all its children (the JVM) 20x/s.
        while proc.poll() is None:
            try:
                tree = [root, *root.children(recursive=True)]
                peak = max(peak, sum(p.memory_info().rss for p in tree))
            except psutil.Error:  # a child exited between listing and reading it
                pass
            time.sleep(0.05)
        wall = time.perf_counter() - start
    out = log.read_text(encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed:\n{out[-3000:]}")
    return {"seconds": round(wall, 1), "peak_mb": round(peak / 2**20), "stdout": out}


def java_version() -> str:
    out = subprocess.run(["java", "-version"], capture_output=True, text=True)
    return (out.stderr.splitlines() or ["?"])[0]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rows", type=int, nargs="+", default=[1_000_000, 10_000_000])
    ap.add_argument("--workdir", type=Path, default=Path("/tmp/creditcast-bench"))
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "benchmarks")
    ap.add_argument("--driver-memory", default="4g")
    opts = ap.parse_args()

    import duckdb
    import pyspark

    results = []
    for rows in opts.rows:
        n_loans = round(rows / ROWS_PER_LOAN)
        workdir = opts.workdir / f"rows_{rows}"
        cfg = write_config(workdir, n_loans, opts.driver_memory)
        env = {**os.environ, "CREDITCAST_CONFIG": str(cfg), "PYTHONUTF8": "1"}
        cli = [sys.executable, "-m", "creditcast.cli"]

        print(f"== {rows:,} rows target: generating {n_loans:,} loans", flush=True)
        gen = run_measured([*cli, "generate"], env, workdir / "generate.log")
        actual = int(
            re.search(r"([\d,]+) performance rows", gen["stdout"]).group(1).replace(",", "")
        )
        entry = {
            "target_rows": rows,
            "loans": n_loans,
            "perf_rows": actual,
            "generate_s": gen["seconds"],
        }
        if not results:
            # One unmeasured run of each engine first: the first JVM start in a
            # fresh container also loads PySpark's jars from disk, which made a
            # 200k-row run take 94 s instead of ~30 s. Measure warm runs only.
            for engine in ("duckdb", "spark"):
                run_measured([*cli, "pipeline", "--engine", engine], env, workdir / "warmup.log")
        for engine in ("duckdb", "spark"):
            print(f"   {engine} ...", flush=True)
            r = run_measured([*cli, "pipeline", "--engine", engine], env, workdir / f"{engine}.log")
            entry[engine] = {"seconds": r["seconds"], "peak_mb": r["peak_mb"]}
            stages = re.search(r"\[spark\] stage seconds: (.+)", r["stdout"])
            if stages:
                entry[engine]["stages"] = dict(
                    (k, float(v)) for k, v in (s.split() for s in stages.group(1).split(", "))
                )
            print(f"   {engine}: {r['seconds']} s, peak {r['peak_mb']:,} MB", flush=True)
        results.append(entry)

    machine = {
        "cpus": os.cpu_count(),
        "memory_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "duckdb": duckdb.__version__,
        "pyspark": pyspark.__version__,
        "java": java_version(),
        "spark_master": "local[*]",
        "spark_driver_memory": opts.driver_memory,
    }
    opts.out.mkdir(parents=True, exist_ok=True)
    (opts.out / "engines.json").write_text(
        json.dumps({"machine": machine, "results": results}, indent=2) + "\n"
    )
    (opts.out / "engines.md").write_text(render_markdown(machine, results))
    print(f"wrote {opts.out / 'engines.md'}")


def render_markdown(machine: dict, results: list[dict]) -> str:
    rows = [
        "| Performance rows | Loans | DuckDB time | Spark time | DuckDB peak memory | Spark peak memory |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        d, s = r["duckdb"], r["spark"]
        rows.append(
            f"| {r['perf_rows']:,} | {r['loans']:,} | {d['seconds']} s | {s['seconds']} s "
            f"| {d['peak_mb']:,} MB | {s['peak_mb']:,} MB |"
        )
    stage_rows = [
        "| Performance rows | Bronze | Silver | Gold | Publish |",
        "|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        st = r["spark"].get("stages", {})
        stage_rows.append(
            f"| {r['perf_rows']:,} | "
            + " | ".join(f"{st.get(k, '-')} s" for k in ("bronze", "silver", "gold", "publish"))
            + " |"
        )
    m = machine
    return (
        "# Engine benchmark: DuckDB vs Spark (local mode)\n\n"
        "Generated by `scripts/benchmark_engines.py`. Each engine runs "
        "`python -m creditcast.cli pipeline --engine <engine>` in its own process, from "
        "the same Bronze files to the same published Gold files. Peak memory covers the "
        "whole process tree (Spark's JVM included). One run per cell.\n\n"
        + "\n".join(rows)
        + "\n\nSpark time by stage (seconds, inside the run above; the rest is JVM start-up):\n\n"
        + "\n".join(stage_rows)
        + f"\n\nMachine: {m['cpus']} CPUs, {m['memory_gb']} GB RAM, {m['os']}, Python {m['python']}, "
        f"DuckDB {m['duckdb']}, PySpark {m['pyspark']} ({m['spark_master']}, driver memory "
        f"{m['spark_driver_memory']}), {m['java']}.\n"
    )


if __name__ == "__main__":
    main()

"""SparkSession factory, with a clear error when Spark can't run here.

PySpark is a Python front end to a JVM: every DataFrame operation is executed
by Java. Spark 4 needs Java 17 or newer, so we check before starting, instead
of letting the user read a py4j stack trace.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING

from creditcast.config import Config, load_config

if TYPE_CHECKING:  # pyspark is optional: only import it for type hints here
    from pyspark.sql import SparkSession

MIN_JAVA = 17

INSTALL_HINT = (
    "Install a Java 17+ runtime (e.g. Temurin 17) and set JAVA_HOME, or run the "
    "Spark engine in its container: see docs/pyspark.md."
)


class SparkUnavailableError(RuntimeError):
    """PySpark or a suitable Java runtime is missing."""


def java_version() -> int | None:
    """Major version of the Java that Spark would launch, or None if absent."""
    home = os.environ.get("JAVA_HOME")
    java = os.path.join(home, "bin", "java") if home else shutil.which("java")
    if not java:
        return None
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=20)
    except OSError:
        return None
    return parse_java_version(out.stderr + out.stdout)  # it prints to stderr


def parse_java_version(text: str) -> int | None:
    """'openjdk version "17.0.12" ...' -> 17; 'java version "1.8.0_401"' -> 8
    (Java 8 and older reported themselves as 1.x)."""
    m = re.search(r'version "(\d+)(?:\.(\d+))?', text)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major


def check_spark_available() -> None:
    """Raise SparkUnavailableError with a fix-it message if Spark can't start."""
    try:
        import pyspark  # noqa: F401
    except ImportError as exc:
        raise SparkUnavailableError(
            "The Spark engine needs PySpark: pip install -r requirements-spark.txt"
        ) from exc
    found = java_version()
    if found is None:
        raise SparkUnavailableError(
            f"The Spark engine needs Java {MIN_JAVA}+, none found. {INSTALL_HINT}"
        )
    if found < MIN_JAVA:
        raise SparkUnavailableError(
            f"The Spark engine needs Java {MIN_JAVA}+, found Java {found}. {INSTALL_HINT}"
        )


def get_spark(cfg: Config | None = None, master: str | None = None) -> SparkSession:
    """A SparkSession configured from `config.yaml` (`spark:` section).

    getOrCreate() returns the running session if there is one, so the stages
    can each ask for it without starting Spark more than once.
    """
    check_spark_available()
    from pyspark.sql import SparkSession

    cfg = cfg or load_config()
    s = cfg.spark
    return (
        SparkSession.builder.appName("creditcast")
        .master(master or str(s.master))
        # Spark's default of 200 shuffle partitions suits a cluster; on a laptop
        # it means 200 tiny tasks per join. Configurable per deployment.
        .config("spark.sql.shuffle.partitions", str(s.shuffle_partitions))
        .config("spark.driver.memory", str(s.driver_memory))
        # Month strings and timestamps must not shift with the machine's zone.
        .config("spark.sql.session.timeZone", "UTC")
        # ANSI mode: bad casts and overflow raise instead of silently becoming
        # NULL (Spark 4's default; set explicitly so 3.5 behaves the same).
        .config("spark.sql.ansi.enabled", "true")
        # Folder names like vintage=2015-01 stay strings; never guess a type.
        .config("spark.sql.sources.partitionColumnTypeInference.enabled", "false")
        # Arrow makes toPandas() (used to publish Gold) columnar and fast.
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )

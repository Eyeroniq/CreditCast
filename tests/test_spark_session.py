"""Spark engine setup (ROADMAP 7.0): the Java check and the CLI engine switch.

These need neither PySpark nor Java, so they run in every environment; the
pipeline itself is tested in test_spark_pipeline.py where Spark can run.
"""

import pytest
from typer.testing import CliRunner

from creditcast import cli
from creditcast.pipeline.spark import session
from creditcast.pipeline.spark.session import SparkUnavailableError, parse_java_version


@pytest.mark.parametrize(
    ("text", "major"),
    [
        ('java version "1.8.0_401"\nJava(TM) SE Runtime Environment', 8),
        ('openjdk version "17.0.21" 2026-10-20', 17),
        ('openjdk version "21" 2023-09-19 LTS', 21),
        ("no java here", None),
    ],
)
def test_parse_java_version(text, major):
    assert parse_java_version(text) == major


def test_old_java_gives_a_clear_message(monkeypatch):
    monkeypatch.setattr(session, "java_version", lambda: 8)
    with pytest.raises(SparkUnavailableError) as err:
        session.check_spark_available()
    msg = str(err.value)
    # without PySpark installed the first problem reported is the missing package
    assert "requirements-spark.txt" in msg or ("Java 17+" in msg and "found Java 8" in msg)


def test_missing_java_gives_a_clear_message(monkeypatch):
    pytest.importorskip("pyspark")
    monkeypatch.setattr(session, "java_version", lambda: None)
    with pytest.raises(SparkUnavailableError, match="Java 17\\+, none found"):
        session.check_spark_available()


def test_cli_spark_engine_exits_cleanly_when_unavailable(monkeypatch):
    def unavailable(*_a, **_k):
        raise SparkUnavailableError("The Spark engine needs Java 17+, found Java 8.")

    monkeypatch.setattr(session, "get_spark", unavailable)
    result = CliRunner().invoke(cli.app, ["pipeline", "--engine", "spark"])
    assert result.exit_code == 2
    assert "needs Java 17+" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_duckdb_stays_the_default_engine():
    help_text = CliRunner().invoke(cli.app, ["pipeline", "--help"]).output
    assert "duckdb" in help_text and "spark" in help_text
    assert cli.ENGINE_OPTION.default is cli.Engine.duckdb


def test_rejects_an_unknown_engine():
    result = CliRunner().invoke(cli.app, ["pipeline", "--engine", "polars"])
    assert result.exit_code != 0

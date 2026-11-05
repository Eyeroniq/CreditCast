"""Explicit schemas (data contracts) for every raw input the Spark engine reads.

We never let Spark infer a schema: inference reads data to guess types, is slow
on big inputs, and silently changes a column's type when a file changes (an
integer column with one bad value becomes a string). With an explicit
StructType, Spark reads exactly these columns as exactly these types, and
`bronze.check_contract` fails loudly when a landing file disagrees.

The columns mirror the generator's `ORIG_SCHEMA` / `PERF_SCHEMA` (a subset of
the Freddie Mac Single-Family data dictionary) and the macro CSVs.
"""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampNTZType,
)

from creditcast.pipeline.generate import ORIG_SCHEMA, PERF_SCHEMA

# One row per loan: attributes known on the origination date.
ORIGINATION = StructType(
    [
        StructField("loan_id", LongType(), nullable=False),
        StructField("vintage", StringType(), nullable=False),  # origination month 'YYYY-MM'
        # pandas writes timezone-naive timestamps, which Parquet marks "not
        # adjusted to UTC"; Spark's type for that is TIMESTAMP_NTZ.
        StructField("orig_date", TimestampNTZType()),
        StructField("fico", LongType()),
        StructField("dti", DoubleType()),
        StructField("ltv", LongType()),
        StructField("orig_interest_rate", DoubleType()),
        StructField("orig_upb", LongType()),
        StructField("orig_loan_term", LongType()),
        StructField("occupancy_status", StringType()),
        StructField("loan_purpose", StringType()),
        StructField("property_type", StringType()),
        StructField("first_time_homebuyer", StringType()),
        StructField("property_state", StringType()),
        StructField("borrower_race", StringType()),  # protected: fairness only, never a model input
    ]
)

# One row per loan per reporting month.
PERFORMANCE = StructType(
    [
        StructField("loan_id", LongType(), nullable=False),
        StructField("monthly_reporting_period", StringType(), nullable=False),  # 'YYYY-MM'
        StructField("loan_age", LongType()),
        StructField("current_upb", DoubleType()),
        # Months delinquent as text: '0'..'6'+, or 'RA' (REO acquired).
        StructField("current_loan_delinquency_status", StringType()),
        StructField("zero_balance_code", StringType()),  # '01' prepaid, '09' REO disposition, ...
        StructField("net_loss", DoubleType()),
    ]
)

# Macro CSVs (5.1): one row per state per month.
MACRO_SERIES = StructType(
    [
        StructField("state", StringType(), nullable=False),
        StructField("month", StringType(), nullable=False),
        StructField("value", DoubleType()),
    ]
)

# Guard against the two definitions drifting apart.
assert ORIGINATION.fieldNames() == ORIG_SCHEMA, "origination contract != generator schema"
assert PERFORMANCE.fieldNames() == PERF_SCHEMA, "performance contract != generator schema"

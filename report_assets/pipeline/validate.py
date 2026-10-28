"""Data-quality validation for retail transaction datasets.

Documented exclusion policy
---------------------------
* Exact duplicates  - rows identical in every mapped source column are
                      collapsed to a single record (first kept, rest counted
                      as removed duplicates).
* Missing CustomerID- rows with a blank customer identifier are excluded from
                      customer-level segmentation but reported, never dropped
                      silently.
* Invalid dates     - rows whose InvoiceDate cannot be parsed with the
                      configured format are excluded and counted.
* Non-positive qty  - lines with Quantity <= 0 are excluded from customer
                      metrics. Cancellation invoices (InvoiceNo starting with
                      'C') are counted separately.
* Non-positive price- lines with UnitPrice <= 0 are excluded from monetary
                      metrics (promotional zero-price adjustments).
"""

from dataclasses import dataclass, field

from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import DoubleType, IntegerType

DATE_FORMAT = "dd/MM/yyyy HH:mm"

REQUIRED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
]


@dataclass
class ValidationReport:
    total_rows: int = 0
    duplicates_removed: int = 0
    invalid_dates: int = 0
    missing_customer_id: int = 0
    cancellation_lines: int = 0
    nonpositive_quantity: int = 0
    nonpositive_price: int = 0
    valid_transactions: int = 0
    distinct_customers: int = 0
    first_purchase: str = ""
    last_purchase: str = ""
    warnings: list = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "Data-quality report",
            "-------------------",
            f"  Total rows read            : {self.total_rows:>8,}",
            f"  Exact duplicates removed   : {self.duplicates_removed:>8,}",
            f"  Invalid invoice dates      : {self.invalid_dates:>8,}",
            f"  Missing customer ID        : {self.missing_customer_id:>8,}",
            f"  Cancellation/return lines : {self.cancellation_lines:>8,}",
            f"  Non-positive quantity      : {self.nonpositive_quantity:>8,}",
            f"  Non-positive unit price    : {self.nonpositive_price:>8,}",
            f"  Valid transaction lines    : {self.valid_transactions:>8,}",
            f"  Distinct segmentable cust. : {self.distinct_customers:>8,}",
            f"  Transaction window         : {self.first_purchase} .. {self.last_purchase}",
        ]
        if self.warnings:
            lines.append("  Warnings:")
            lines.extend(f"    - {w}" for w in self.warnings)
        return "\n".join(lines)


def read_transactions(spark: SparkSession, csv_path: str, column_map: dict = None) -> DataFrame:
    """Read a CSV with every column kept as string, then rename via column_map."""
    column_map = column_map or {}
    df = spark.read.option("header", True).option("mode", "PERMISSIVE").csv(csv_path)
    for canonical, actual in column_map.items():
        if actual in df.columns:
            df = df.withColumnRenamed(actual, canonical)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def validate_transactions(raw: DataFrame) -> tuple[DataFrame, ValidationReport]:
    """Apply the documented validation policy; return cleaned data + report."""
    report = ValidationReport()
    report.total_rows = raw.count()

    all_cols = raw.columns
    deduped = raw.dropDuplicates(all_cols)
    report.duplicates_removed = report.total_rows - deduped.count()

    df = (
        deduped
        .withColumn("InvoiceNo", F.trim(F.col("InvoiceNo")))
        .withColumn("CustomerID", F.trim(F.col("CustomerID")))
        .withColumn("Quantity", F.col("Quantity").cast(IntegerType()))
        .withColumn("UnitPrice", F.col("UnitPrice").cast(DoubleType()))
        .withColumn("InvoiceDateParsed", F.try_to_timestamp(F.col("InvoiceDate"), F.lit(DATE_FORMAT)))
        .withColumn("IsCancellation", F.upper(F.col("InvoiceNo")).startswith(F.lit("C")))
    )

    report.invalid_dates = df.filter(F.col("InvoiceDateParsed").isNull()).count()
    report.missing_customer_id = df.filter(
        F.col("CustomerID").isNull() | (F.col("CustomerID") == "")
    ).count()
    report.cancellation_lines = df.filter(F.col("IsCancellation")).count()
    report.nonpositive_quantity = df.filter(
        (~F.col("IsCancellation")) & (F.col("Quantity") <= 0)
    ).count()
    report.nonpositive_price = df.filter(F.col("UnitPrice") <= 0).count()

    valid = df.filter(
        F.col("InvoiceDateParsed").isNotNull()
        & F.col("CustomerID").isNotNull()
        & (F.col("CustomerID") != "")
        & (~F.col("IsCancellation"))
        & (F.col("Quantity") > 0)
        & (F.col("UnitPrice") > 0)
    ).withColumn("LineRevenue", F.round(F.col("Quantity") * F.col("UnitPrice"), 2))

    report.valid_transactions = valid.count()
    report.distinct_customers = valid.select("CustomerID").distinct().count()

    bounds = valid.agg(
        F.min("InvoiceDateParsed").alias("lo"),
        F.max("InvoiceDateParsed").alias("hi"),
    ).collect()[0]
    if bounds["lo"] is not None:
        report.first_purchase = bounds["lo"].strftime("%Y-%m-%d")
        report.last_purchase = bounds["hi"].strftime("%Y-%m-%d")

    if report.valid_transactions == 0:
        report.warnings.append("No valid transactions remain after validation.")

    return valid, report

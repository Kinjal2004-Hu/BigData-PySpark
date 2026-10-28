"""RFM metric computation on Spark DataFrames.

Recency   - days between the analysis reference date and the customer's most
            recent valid purchase.
Frequency - number of distinct valid invoices in the analysis window.
Monetary  - total valid line revenue (Quantity x UnitPrice) in the window.

The reference date defaults to one day after the latest valid transaction so
runs are reproducible; it can be overridden for cohort analyses.
"""

from datetime import datetime, timedelta

from pyspark.sql import DataFrame, functions as F


def default_reference_date(transactions: DataFrame) -> datetime:
    row = transactions.agg(F.max("InvoiceDateParsed").alias("hi")).collect()[0]
    if row["hi"] is None:
        raise ValueError("Cannot derive a reference date from an empty dataset.")
    return row["hi"] + timedelta(days=1)


def compute_rfm(transactions: DataFrame, reference_date: datetime | None = None) -> DataFrame:
    """Return one row per customer with RFM metrics and purchase bookkeeping."""
    if reference_date is None:
        reference_date = default_reference_date(transactions)

    return (
        transactions.groupBy("CustomerID")
        .agg(
            F.datediff(F.lit(reference_date), F.max("InvoiceDateParsed")).alias("Recency"),
            F.countDistinct("InvoiceNo").alias("Frequency"),
            F.round(F.sum("LineRevenue"), 2).alias("Monetary"),
            F.min("InvoiceDateParsed").alias("FirstPurchase"),
            F.max("InvoiceDateParsed").alias("LastPurchase"),
            F.first("Country", ignorenulls=True).alias("Country"),
        )
        .withColumn("AvgOrderValue", F.round(F.col("Monetary") / F.col("Frequency"), 2))
        .withColumn("ReferenceDate", F.lit(reference_date.strftime("%Y-%m-%d")))
    )

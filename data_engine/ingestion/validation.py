from dataclasses import asdict, dataclass

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

DATE_FORMATS = [
    "M/d/yyyy H:mm",
    "M/d/yyyy H:mm:ss",
    "d-M-yy HH:mm",
    "yyyy-MM-dd HH:mm:ss",
    "yyyy-MM-dd'T'HH:mm:ss",
    "dd/MM/yyyy HH:mm",
]


@dataclass
class QualityStats:
    total_rows: int = 0
    valid_rows: int = 0
    excluded_rows: int = 0
    duplicate_rows: int = 0
    invalid_date_rows: int = 0
    missing_customer_rows: int = 0
    negative_quantity_rows: int = 0
    invalid_price_rows: int = 0
    return_rows: int = 0
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["warnings"] = list(self.warnings)
        return d


def _parse_date(col: F.Column) -> F.Column:
    parsed = F.lit(None).cast("timestamp")
    for fmt in DATE_FORMATS:
        parsed = F.coalesce(parsed, F.to_timestamp(col, fmt))
    return parsed


def validate_and_clean(raw: DataFrame) -> tuple[DataFrame, QualityStats]:
    """Apply the documented validation policy and flag every row.

    Policy:
      * duplicates (identical mapped field values): keep first, exclude rest
      * invoice_date must parse with one of the supported formats
      * quantity must be > 0
      * unit_price must be >= 0
      * customer_id required for customer-level analysis
      * cancellations/returns (invoice starts with 'C' or negative quantity)
        are marked and excluded from valid purchase rows but counted
    """
    df = raw
    df = df.withColumn("quantity_d", F.col("quantity").cast("double"))
    df = df.withColumn("price_d", F.col("unit_price").cast("double"))
    df = df.withColumn("ts", _parse_date(F.col("invoice_date")))
    df = df.withColumn(
        "cust",
        F.when(
            F.trim(F.regexp_replace(F.coalesce(F.col("customer_id"), F.lit("")), r"\.0$", "")) == "",
            F.lit(None),
        ).otherwise(
            F.trim(F.regexp_replace(F.col("customer_id"), r"\.0$", ""))
        ),
    )
    df = df.withColumn("inv", F.trim(F.coalesce(F.col("invoice_no"), F.lit(""))))

    dup_cols = ["invoice_no", "stock_code", "quantity", "invoice_date", "unit_price", "customer_id"]
    dup_win = Window.partitionBy(*dup_cols).orderBy(F.monotonically_increasing_id())
    df = df.withColumn("_dup_rank", F.row_number().over(dup_win))
    is_dup = F.col("_dup_rank") > 1

    missing_customer = F.col("cust").isNull()
    bad_date = F.col("ts").isNull()
    bad_qty = F.col("quantity_d").isNull() | (F.col("quantity_d") <= 0)
    bad_price = F.col("price_d").isNull() | (F.col("price_d") < 0)
    is_return = F.col("inv").startswith("C") | (F.col("quantity_d") < 0)

    df = df.withColumn("is_duplicate", is_dup.cast("int"))
    df = df.withColumn("is_return", is_return.cast("int"))
    df = df.withColumn("invoice_date_clean", F.col("ts"))
    df = df.withColumn(
        "is_valid",
        (~is_dup & ~missing_customer & ~bad_date & ~bad_qty & ~bad_price & ~is_return).cast("int"),
    )
    df = df.withColumn(
        "revenue",
        F.when(F.col("is_valid") == 1, F.col("quantity_d") * F.col("price_d")).otherwise(0.0),
    )
    df = df.withColumn("country_clean", F.trim(F.col("country")))
    df = df.drop("_dup_rank")

    non_dup = F.col("is_duplicate") == 0
    agg = df.agg(
        F.count(F.lit(1)).alias("total"),
        F.sum("is_valid").alias("valid"),
        F.sum("is_duplicate").alias("dups"),
        F.sum((non_dup & F.col("ts").isNull()).cast("long")).alias("bad_dates"),
        F.sum((non_dup & F.col("cust").isNull()).cast("long")).alias("missing_cust"),
        F.sum((non_dup & ~bad_date & missing_customer).cast("long")).alias("missing_cust_parseable"),
        F.sum((non_dup & ~bad_date & ~missing_customer & bad_qty).cast("long")).alias("bad_qty"),
        F.sum(
            (non_dup & ~bad_date & ~missing_customer & ~bad_qty & ~is_return & bad_price).cast("long")
        ).alias("bad_price"),
        F.sum((non_dup & is_return).cast("long")).alias("returns"),
    ).collect()[0]

    total = int(agg["total"] or 0)
    valid = int(agg["valid"] or 0)
    missing_cust = int(agg["missing_cust_parseable"] or 0)
    dups = int(agg["dups"] or 0)
    bad_dates = int(agg["bad_dates"] or 0)
    bad_qty = int(agg["bad_qty"] or 0)
    bad_price = int(agg["bad_price"] or 0)
    returns = int(agg["returns"] or 0)

    warnings: list[str] = []
    if dups:
        warnings.append(f"{dups} exact duplicate rows excluded (keep-first policy)")
    if missing_cust:
        warnings.append(f"{missing_cust} rows missing customer id excluded from customer analysis")
    if bad_dates:
        warnings.append(f"{bad_dates} rows with unparseable dates excluded")
    if bad_qty:
        warnings.append(f"{bad_qty} rows with non-positive quantity excluded")
    if bad_price:
        warnings.append(f"{bad_price} rows with negative unit price excluded")
    if returns:
        warnings.append(f"{returns} cancellation/return rows excluded from RFM metrics")
    if valid == 0:
        warnings.append("No valid purchase rows found - check column mapping and source data")

    stats = QualityStats(
        total_rows=total,
        valid_rows=valid,
        excluded_rows=total - valid,
        duplicate_rows=dups,
        invalid_date_rows=bad_dates,
        missing_customer_rows=missing_cust,
        negative_quantity_rows=bad_qty,
        invalid_price_rows=bad_price,
        return_rows=returns,
        warnings=tuple(warnings),
    )
    return df, stats

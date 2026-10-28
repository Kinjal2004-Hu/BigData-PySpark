from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def compute_rfm(
    clean: DataFrame,
    reference_date,
) -> DataFrame:
    """Compute customer-level RFM metrics from validated purchase rows.

    Recency  = days between analysis reference date and last purchase
    Frequency = distinct valid invoices (orders)
    Monetary  = sum of Quantity x UnitPrice for valid rows

    Reference date policy: by default one day after the latest valid
    transaction (passed in pre-computed by the caller for reproducibility).
    Only rows with is_valid = 1 and a customer id are included.
    """
    valid = clean.filter((F.col("is_valid") == 1) & F.col("cust").isNotNull())

    rfm = valid.groupBy("cust").agg(
        F.datediff(F.lit(reference_date), F.max("invoice_date_clean")).alias("recency"),
        F.countDistinct("inv").alias("frequency"),
        F.sum("revenue").alias("monetary"),
        F.max("invoice_date_clean").alias("last_purchase"),
        F.min("invoice_date_clean").alias("first_purchase"),
        F.countDistinct(F.col("invoice_date_clean").cast("date")).alias("active_days"),
        F.first("country_clean", ignorenulls=True).alias("country"),
    )
    rfm = rfm.withColumn("recency", F.greatest(F.col("recency"), F.lit(0)))
    rfm = rfm.withColumn("monetary", F.round(F.col("monetary"), 2))
    return rfm


def latest_valid_date(clean: DataFrame):
    row = (
        clean.filter((F.col("is_valid") == 1) & F.col("cust").isNotNull())
        .agg(F.max("invoice_date_clean").alias("mx"))
        .collect()[0]
    )
    return row["mx"]


def add_rfm_scores(rfm: DataFrame) -> DataFrame:
    """Quintile RFM scores (1-5 each) via NTILE over the customer population.

    Score 5 = best (recent buyers, frequent, high spend). rfm_score is the
    sum (3-15).
    """
    from pyspark.sql import Window

    rfm = rfm.withColumn("_r", F.ntile(5).over(Window.orderBy(F.col("recency").asc())))
    rfm = rfm.withColumn("_f", F.ntile(5).over(Window.orderBy(F.col("frequency").asc())))
    rfm = rfm.withColumn("_m", F.ntile(5).over(Window.orderBy(F.col("monetary").asc())))
    rfm = rfm.withColumn("rfm_score", (F.lit(6) - F.col("_r")) + F.col("_f") + F.col("_m"))
    return rfm.drop("_r", "_f", "_m")

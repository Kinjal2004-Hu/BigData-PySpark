"""CustomerIQ report pipeline runner (isolated from the main data_engine).

Executes the same staged flow as the production data engine:
    load -> validate -> RFM (Spark) -> scale -> K-Means (MLlib)
         -> silhouette evaluation -> segment labeling -> persist

Run (from the repository root):
    python report_assets/pipeline/run.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pyspark.sql import functions as F

from kmeans import RANDOM_SEED, cluster_profile, evaluate_ks, fit_kmeans
from labeling import label_clusters
from rfm import compute_rfm, default_reference_date
from spark_session import get_spark
from validate import read_transactions, validate_transactions

ASSETS = Path(__file__).resolve().parents[1]
RAW_CSV = ASSETS / "data" / "raw" / "demo_online_retail.csv"
PROCESSED_DIR = ASSETS / "data" / "processed"
MODEL_DIR = ASSETS / "data" / "models" / "kmeans_model"


def _print_table(rows: list[dict], columns: list[tuple[str, tuple[str, int]]]) -> None:
    header = " | ".join(label.ljust(width) for label, (key, width) in columns)
    print(header)
    print("-+-".join("-" * w for _, (_, w) in columns))
    for row in rows:
        cells = []
        for _, (key, width) in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                text = f"{value:,.2f}"
            elif isinstance(value, int):
                text = f"{value:,}"
            else:
                text = str(value)
            cells.append(text.ljust(width))
        print(" | ".join(cells))


def main() -> int:
    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")

    print("=" * 78)
    print("CustomerIQ data-engine pipeline - demo dataset")
    print(f"Spark {spark.version} | deterministic seed = {RANDOM_SEED}")
    print("=" * 78)

    # ---- 1. ingest + validate -------------------------------------------
    print(f"\n[1/5] Reading dataset: {RAW_CSV.name}")
    raw = read_transactions(spark, str(RAW_CSV))
    transactions, report = validate_transactions(raw)
    print(report.render())

    if report.valid_transactions == 0:
        print("Pipeline aborted: no valid transactions.")
        return 1

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    transactions.write.mode("overwrite").parquet(str(PROCESSED_DIR / "demo_transactions.parquet"))

    # ---- 2. RFM ----------------------------------------------------------
    reference_date = default_reference_date(transactions)
    print(f"\n[2/5] RFM computation (analysis reference date = {reference_date:%Y-%m-%d})")
    rfm = compute_rfm(transactions, reference_date)
    rfm.cache()
    print(f"  Customers scored: {rfm.count():,}")
    sample = (
        rfm.select("CustomerID", "Recency", "Frequency", "Monetary", "AvgOrderValue")
        .orderBy("CustomerID")
        .limit(8)
        .collect()
    )
    print("  RFM sample (first 8 customers by ID):")
    _print_table(
        [r.asDict() for r in sample],
        [
            ("CustomerID", ("CustomerID", 12)),
            ("Recency (days)", ("Recency", 14)),
            ("Frequency", ("Frequency", 10)),
            ("Monetary", ("Monetary", 12)),
            ("Avg order value", ("AvgOrderValue", 15)),
        ],
    )

    # ---- 3. clustering ---------------------------------------------------
    print("\n[3/5] K-Means clustering (Spark MLlib)")
    print("  Feature pipeline: log1p(Frequency), log1p(Monetary), StandardScaler(withMean, withStd)")
    k_scores = evaluate_ks(rfm, k_range=range(3, 9))
    print("  Silhouette score by k:")
    for k, s in sorted(k_scores.items()):
        print(f"    k={k}: {s:.4f}")
    best_k = max(k_scores, key=k_scores.get)
    print(f"  Selected k = {best_k} (highest silhouette = {k_scores[best_k]:.4f})")

    result = fit_kmeans(rfm, k=best_k)
    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    result.model.write().overwrite().save(str(MODEL_DIR))

    # ---- 4. labeling -----------------------------------------------------
    print("\n[4/5] Cluster profiling and segment labeling")
    profiles = cluster_profile(result.assignments)
    print("  Cluster profiles (original RFM scale):")
    _print_table(
        [
            {
                **p,
                "prediction": int(p["prediction"]),
                "avg_recency": round(p["avg_recency"], 1),
                "avg_frequency": round(p["avg_frequency"], 2),
                "avg_monetary": round(p["avg_monetary"], 2),
            }
            for p in profiles
        ],
        [
            ("Cluster", ("prediction", 8)),
            ("Customers", ("customers", 10)),
            ("Avg recency (d)", ("avg_recency", 15)),
            ("Avg frequency", ("avg_frequency", 13)),
            ("Avg monetary", ("avg_monetary", 13)),
        ],
    )

    mapping = label_clusters(profiles, best_k)
    print("  Label mapping (ranked by z(Frequency) + z(Monetary) - z(Recency)):")
    for cluster_id, label in sorted(mapping.items()):
        print(f"    cluster {cluster_id} -> {label}")

    segment_col = F.lit(None).cast("string")
    for cluster_id, label in mapping.items():
        segment_col = F.when(F.col("prediction") == cluster_id, F.lit(label)).otherwise(segment_col)
    labeled = result.assignments.withColumn("Segment", segment_col)

    # ---- 5. segment summaries + persistence ------------------------------
    print(f"\n[5/5] Segment summaries (silhouette = {result.silhouette:.4f})")
    total_customers = labeled.count()
    total_revenue = labeled.agg(F.sum("Monetary")).collect()[0][0]
    summary = (
        labeled.groupBy("Segment")
        .agg(
            F.count("*").alias("customers"),
            F.round(F.sum("Monetary"), 2).alias("revenue"),
            F.round(F.avg("Monetary"), 2).alias("avg_spend"),
            F.round(F.avg("Frequency"), 2).alias("avg_frequency"),
            F.round(F.avg("Recency"), 1).alias("avg_recency"),
        )
        .withColumn("pct_customers", F.round(F.col("customers") / F.lit(total_customers) * 100, 1))
        .withColumn("pct_revenue", F.round(F.col("revenue") / F.lit(total_revenue) * 100, 1))
        .orderBy(F.col("revenue").desc())
        .collect()
    )
    _print_table(
        [r.asDict() for r in summary],
        [
            ("Segment", ("Segment", 20)),
            ("Customers", ("customers", 10)),
            ("% cust.", ("pct_customers", 8)),
            ("Revenue", ("revenue", 12)),
            ("% rev.", ("pct_revenue", 7)),
            ("Avg spend", ("avg_spend", 10)),
            ("Avg freq", ("avg_frequency", 9)),
            ("Avg rec. d", ("avg_recency", 10)),
        ],
    )

    out_cols = [
        "CustomerID", "Recency", "Frequency", "Monetary", "AvgOrderValue",
        "FirstPurchase", "LastPurchase", "Country", "prediction", "Segment",
    ]
    labeled.select(*out_cols).write.mode("overwrite").parquet(str(PROCESSED_DIR / "customer_rfm.parquet"))
    labeled.select(*out_cols).toPandas().to_csv(PROCESSED_DIR / "customer_rfm.csv", index=False)
    print(f"\n  Persisted: {PROCESSED_DIR / 'demo_transactions.parquet'}")
    print(f"  Persisted: {PROCESSED_DIR / 'customer_rfm.parquet'} (+ .csv export)")
    print(f"  Persisted: {MODEL_DIR} (Spark ML KMeans model)")
    print("\nPipeline completed successfully.")

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

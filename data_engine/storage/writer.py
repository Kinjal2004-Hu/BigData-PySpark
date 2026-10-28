"""Persist Spark outputs: Parquet analytical artifacts + SQLite application rows.

Large intermediates stay in Parquet; PostgreSQL/SQLite only receives
application-facing records (transactions, RFM, segments, reports).
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from pyspark.sql import DataFrame, SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402


def write_valid_parquet(clean: DataFrame, out_dir: str) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (
        clean.repartition(4)
        .write.mode("overwrite")
        .option("compression", "snappy")
        .parquet(out_dir)
    )


def read_valid_parquet(out_dir: str, spark: SparkSession) -> DataFrame:
    return spark.read.parquet(out_dir)


def write_transactions(clean: DataFrame, dataset_id: str, batch_size: int = 5000) -> int:
    """Stream cleaned rows into SQLite in bounded batches (no full collect)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Dataset, Transaction
    from app.core.config import get_settings

    url = get_settings().database_url
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    db = Session()
    written = 0
    try:
        ds = db.get(Dataset, dataset_id)
        if ds is None:
            raise ValueError(f"dataset {dataset_id} not found")
        existing = (
            db.query(Transaction).filter(Transaction.dataset_id == dataset_id).limit(1).count()
        )
        if existing:
            db.query(Transaction).filter(Transaction.dataset_id == dataset_id).delete()
            db.commit()

        cols = [
            "invoice_no", "stock_code", "description", "quantity_d",
            "invoice_date_clean", "price_d", "revenue", "cust",
            "country_clean", "is_return", "is_valid",
        ]
        batch: list[dict] = []
        for row in clean.select(*cols).toLocalIterator():
            batch.append(
                dict(
                    dataset_id=dataset_id,
                    invoice_no=row["invoice_no"],
                    stock_code=row["stock_code"],
                    description=row["description"],
                    quantity=int(row["quantity_d"] or 0),
                    invoice_date=row["invoice_date_clean"],
                    unit_price=float(row["price_d"] or 0.0),
                    revenue=float(row["revenue"] or 0.0),
                    customer_id=row["cust"],
                    country=row["country_clean"],
                    is_return=int(row["is_return"] or 0),
                    is_valid=int(row["is_valid"] or 0),
                )
            )
            if len(batch) >= batch_size:
                db.bulk_insert_mappings(Transaction, batch)
                db.commit()
                written += len(batch)
                batch = []
        if batch:
            db.bulk_insert_mappings(Transaction, batch)
            db.commit()
            written += len(batch)

        ds.total_rows = written
        ds.valid_rows = (
            db.query(Transaction)
            .filter(Transaction.dataset_id == dataset_id, Transaction.is_valid == 1)
            .count()
        )
        ds.status = "ready"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        engine.dispose()
    return written


def save_quality_report(dataset_id: str, job_id: str, stats) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings
    from app.models import DataQualityReport

    engine = create_engine(get_settings().database_url)
    db = sessionmaker(bind=engine)()
    try:
        import json

        report = DataQualityReport(
            dataset_id=dataset_id,
            job_id=job_id,
            total_rows=stats.total_rows,
            valid_rows=stats.valid_rows,
            excluded_rows=stats.excluded_rows,
            duplicate_rows=stats.duplicate_rows,
            invalid_date_rows=stats.invalid_date_rows,
            missing_customer_rows=stats.missing_customer_rows,
            negative_quantity_rows=stats.negative_quantity_rows,
            invalid_price_rows=stats.invalid_price_rows,
            return_rows=stats.return_rows,
            warnings_json=json.dumps(list(stats.warnings)),
        )
        db.add(report)
        db.commit()
    finally:
        db.close()
        engine.dispose()


def save_segment_results(
    *,
    dataset_id: str,
    labeled: DataFrame,
    label_meta: dict,
    run_id: str,
    silhouette: float,
    k: int,
    seed: int,
    ref_date,
    centroids: list,
) -> None:
    """Replace current customer RFM / segment rows for the dataset."""
    import json

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings
    from app.models import (
        ActivityLog,
        Customer,
        CustomerRfm,
        Segment,
        SegmentAssignment,
    )
    from data_engine.features.rfm import latest_valid_date  # noqa: F401

    engine = create_engine(get_settings().database_url)
    db = sessionmaker(bind=engine)()
    try:
        # wipe previous analysis for this dataset (idempotent re-run)
        for model in (CustomerRfm, SegmentAssignment, Segment):
            db.query(model).filter(model.dataset_id == dataset_id).delete()
        db.commit()

        # customers aggregate table (first/last purchase, order counts)
        cust_rows = (
            labeled.groupBy("cust")
            .agg(
                F.max("last_purchase").alias("last_purchase"),
                F.min("first_purchase").alias("first_purchase"),
                F.sum("frequency").alias("order_count"),
                F.max("monetary").alias("total_spend"),
                F.max("country").alias("country"),
            )
            .collect()
        )
        for r in cust_rows:
            total = float(r["total_spend"] or 0.0)
            orders = int(r["order_count"] or 0)
            existing = (
                db.query(Customer)
                .filter(Customer.dataset_id == dataset_id, Customer.customer_id == r["cust"])
                .first()
            )
            if existing is None:
                existing = Customer(dataset_id=dataset_id, customer_id=r["cust"])
                db.add(existing)
            existing.first_purchase = r["first_purchase"]
            existing.last_purchase = r["last_purchase"]
            existing.order_count = orders
            existing.total_spend = total
            existing.avg_order_value = round(total / orders, 2) if orders else 0.0
            existing.country = r["country"]
        db.commit()

        # segments
        total_customers = sum(v["customers"] for v in label_meta.values()) or 1
        seg_revenue: dict[int, float] = {}
        rev_rows = labeled.groupBy("cluster").agg(F.sum("monetary").alias("rev")).collect()
        for r in rev_rows:
            seg_revenue[int(r["cluster"])] = float(r["rev"] or 0.0)
        total_revenue = sum(seg_revenue.values()) or 1.0

        centroid_by_cluster = {c["cluster"]: c for c in centroids}
        for cid, meta in label_meta.items():
            slug = _slug(meta["label"])
            seg = Segment(
                id=f"{dataset_id}:{slug}",
                dataset_id=dataset_id,
                cluster_id=cid,
                name=meta["label"],
                description=_describe(meta["label"]),
                customer_count=meta["customers"],
                pct_of_customers=round(100.0 * meta["customers"] / total_customers, 2),
                revenue=round(seg_revenue.get(cid, 0.0), 2),
                pct_of_revenue=round(100.0 * seg_revenue.get(cid, 0.0) / total_revenue, 2),
                avg_spend=meta["avg_monetary"],
                avg_frequency=meta["avg_frequency"],
                avg_recency=meta["avg_recency"],
                centroid_recency=centroid_by_cluster.get(cid, {}).get("recency", 0.0),
                centroid_frequency=centroid_by_cluster.get(cid, {}).get("frequency_est", 0.0),
                centroid_monetary=centroid_by_cluster.get(cid, {}).get("monetary_est", 0.0),
                analysis_run_id=run_id,
            )
            db.add(seg)
        db.commit()

        # customer RFM + assignments (bounded batches)
        rows = labeled.select(
            "cust", "recency", "frequency", "monetary", "rfm_score", "cluster", "segment_name"
        ).toLocalIterator()
        batch_rfm, batch_assign = [], []
        meta_by_label = {v["label"]: (cid, v) for cid, v in label_meta.items()}
        for r in rows:
            label = r["segment_name"]
            cid, _ = meta_by_label.get(label, (int(r["cluster"]), {}))
            slug = _slug(label)
            batch_rfm.append(
                dict(
                    dataset_id=dataset_id,
                    customer_id=r["cust"],
                    recency_days=int(r["recency"] or 0),
                    frequency=int(r["frequency"] or 0),
                    monetary=float(r["monetary"] or 0.0),
                    rfm_score=int(r["rfm_score"]) if r["rfm_score"] is not None else None,
                    cluster_id=int(r["cluster"]),
                    segment_id=f"{dataset_id}:{slug}",
                    analysis_run_id=run_id,
                )
            )
            batch_assign.append(
                dict(
                    dataset_id=dataset_id,
                    customer_id=r["cust"],
                    segment_id=f"{dataset_id}:{slug}",
                    analysis_run_id=run_id,
                )
            )
            if len(batch_rfm) >= 5000:
                db.bulk_insert_mappings(CustomerRfm, batch_rfm)
                db.bulk_insert_mappings(SegmentAssignment, batch_assign)
                db.commit()
                batch_rfm, batch_assign = [], []
        if batch_rfm:
            db.bulk_insert_mappings(CustomerRfm, batch_rfm)
            db.bulk_insert_mappings(SegmentAssignment, batch_assign)
            db.commit()

        db.add(
            ActivityLog(
                event="Segmentation completed",
                target=f"k={k}, silhouette={silhouette:.4f}",
                status="success",
                detail=f"run={run_id} seed={seed} reference_date={ref_date.date()}",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        engine.dispose()


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


SEGMENT_DESCRIPTIONS = {
    "Champions": "Bought recently, buy often and spend the most.",
    "Loyal Customers": "Consistent repeat buyers with above-average spend.",
    "Potential Loyalists": "Recent customers with growing engagement.",
    "New Customers": "First purchases in the analysis window; low frequency so far.",
    "At Risk": "Historically valuable customers whose recency has degraded.",
    "Hibernating": "Long inactive with low historical frequency and spend.",
}


def _describe(label: str) -> str:
    if label in SEGMENT_DESCRIPTIONS:
        return SEGMENT_DESCRIPTIONS[label]
    return f"Cluster profile '{label}' produced by K-Means; no canonical rule matched."

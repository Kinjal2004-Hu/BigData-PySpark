from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Customer, CustomerRfm, Dataset, Segment, Transaction
from app.schemas import (
    RevenuePoint,
    SegmentDistributionItem,
    SegmentRevenueItem,
    SegmentOut,
)
from app.services.common import active_dataset

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_dataset(db: Session, dataset_id: str | None) -> Dataset:
    ds = active_dataset(db, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="No processed dataset available")
    return ds


@router.get("/revenue-trend", response_model=list[RevenuePoint])
def revenue_trend(
    dataset_id: str | None = None,
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[RevenuePoint]:
    ds = _require_dataset(db, dataset_id)
    q = (
        db.query(
            Transaction.invoice_date,
            Transaction.revenue,
            Transaction.invoice_no,
            Transaction.customer_id,
        )
        .filter(Transaction.dataset_id == ds.id, Transaction.is_valid == 1,
                Transaction.invoice_date.isnot(None))
    )
    if start:
        q = q.filter(Transaction.invoice_date >= start)
    if end:
        q = q.filter(Transaction.invoice_date <= end)
    rows = q.all()
    if not rows:
        return []

    buckets: dict[str, dict] = {}
    for dt, rev, inv, cust in rows:
        if granularity == "day":
            key = dt.strftime("%Y-%m-%d")
        elif granularity == "week":
            iso = dt.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        else:
            key = dt.strftime("%Y-%m")
        b = buckets.setdefault(key, {"revenue": 0.0, "orders": set(), "customers": set()})
        b["revenue"] += float(rev or 0.0)
        if inv:
            b["orders"].add(inv)
        if cust:
            b["customers"].add(cust)

    return [
        RevenuePoint(
            period=k,
            revenue=round(v["revenue"], 2),
            orders=len(v["orders"]),
            customers=len(v["customers"]),
        )
        for k, v in sorted(buckets.items())
    ]


@router.get("/segment-distribution", response_model=list[SegmentDistributionItem])
def segment_distribution(
    dataset_id: str | None = None, db: Session = Depends(get_db)
) -> list[SegmentDistributionItem]:
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(Segment)
        .filter(Segment.dataset_id == ds.id)
        .order_by(Segment.customer_count.desc())
        .all()
    )
    return [
        SegmentDistributionItem(
            segment_id=r.id, name=r.name, customers=r.customer_count, pct=r.pct_of_customers
        )
        for r in rows
    ]


@router.get("/segment-revenue", response_model=list[SegmentRevenueItem])
def segment_revenue(
    dataset_id: str | None = None, db: Session = Depends(get_db)
) -> list[SegmentRevenueItem]:
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(Segment)
        .filter(Segment.dataset_id == ds.id)
        .order_by(Segment.revenue.desc())
        .all()
    )
    return [
        SegmentRevenueItem(segment_id=r.id, name=r.name, revenue=r.revenue, pct=r.pct_of_revenue)
        for r in rows
    ]


@router.get("/segments-overview", response_model=list[SegmentOut])
def segments_overview(
    dataset_id: str | None = None, db: Session = Depends(get_db)
) -> list[SegmentOut]:
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(Segment)
        .filter(Segment.dataset_id == ds.id)
        .order_by(Segment.revenue.desc())
        .all()
    )
    return [
        SegmentOut(
            id=r.id,
            cluster_id=r.cluster_id,
            name=r.name,
            description=r.description,
            customer_count=r.customer_count,
            pct_of_customers=r.pct_of_customers,
            revenue=r.revenue,
            pct_of_revenue=r.pct_of_revenue,
            avg_spend=r.avg_spend,
            avg_frequency=r.avg_frequency,
            avg_recency=r.avg_recency,
            centroid_recency=r.centroid_recency,
            centroid_frequency=r.centroid_frequency,
            centroid_monetary=r.centroid_monetary,
        )
        for r in rows
    ]


@router.get("/purchase-frequency")
def purchase_frequency(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    """Histogram of order counts per customer."""
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(Customer.order_count, func.count(Customer.id))
        .filter(Customer.dataset_id == ds.id)
        .group_by(Customer.order_count)
        .all()
    )
    if not rows:
        return []
    buckets: dict[str, int] = {}
    for orders, count in rows:
        if orders <= 1:
            key = "1"
        elif orders <= 2:
            key = "2"
        elif orders <= 5:
            key = "3-5"
        elif orders <= 10:
            key = "6-10"
        elif orders <= 20:
            key = "11-20"
        else:
            key = "21+"
        buckets[key] = buckets.get(key, 0) + count
    order = ["1", "2", "3-5", "6-10", "11-20", "21+"]
    return [
        {"bucket": b, "customers": buckets[b]} for b in order if b in buckets
    ]


@router.get("/rfm-overview")
def rfm_overview(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    """Average recency / frequency / monetary by segment for the RFM overview chart."""
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(
            Segment.name,
            Segment.avg_recency,
            Segment.avg_frequency,
            Segment.avg_spend,
            Segment.customer_count,
        )
        .filter(Segment.dataset_id == ds.id)
        .order_by(Segment.customer_count.desc())
        .all()
    )
    return [
        {
            "segment": r[0],
            "avg_recency": r[1],
            "avg_frequency": r[2],
            "avg_monetary": r[3],
            "customers": r[4],
        }
        for r in rows
    ]


@router.get("/rfm-score-distribution")
def rfm_score_distribution(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(CustomerRfm.rfm_score, func.count(CustomerRfm.id))
        .filter(CustomerRfm.dataset_id == ds.id, CustomerRfm.rfm_score.isnot(None))
        .group_by(CustomerRfm.rfm_score)
        .order_by(CustomerRfm.rfm_score)
        .all()
    )
    return [{"score": s, "customers": c} for s, c in rows]


@router.get("/recency-distribution")
def recency_distribution(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    """Customer inactivity analysis: customers bucketed by days since last purchase."""
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(CustomerRfm.recency_days)
        .filter(CustomerRfm.dataset_id == ds.id)
        .all()
    )
    if not rows:
        return []
    buckets = {
        "0-30": 0, "31-60": 0, "61-90": 0, "91-180": 0, "181-365": 0, "365+": 0
    }
    for (r,) in rows:
        if r <= 30:
            buckets["0-30"] += 1
        elif r <= 60:
            buckets["31-60"] += 1
        elif r <= 90:
            buckets["61-90"] += 1
        elif r <= 180:
            buckets["91-180"] += 1
        elif r <= 365:
            buckets["181-365"] += 1
        else:
            buckets["365+"] += 1
    return [{"bucket": k, "customers": v} for k, v in buckets.items() if v > 0]


@router.get("/monetary-distribution")
def monetary_distribution(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    ds = _require_dataset(db, dataset_id)
    rows = [
        r[0]
        for r in db.query(CustomerRfm.monetary)
        .filter(CustomerRfm.dataset_id == ds.id, CustomerRfm.monetary >= 0)
        .all()
    ]
    if not rows:
        return []
    rows.sort()
    buckets = {
        "0-50": 0, "50-200": 0, "200-500": 0, "500-1K": 0, "1K-5K": 0, "5K+": 0
    }
    for v in rows:
        if v < 50:
            buckets["0-50"] += 1
        elif v < 200:
            buckets["50-200"] += 1
        elif v < 500:
            buckets["200-500"] += 1
        elif v < 1000:
            buckets["500-1K"] += 1
        elif v < 5000:
            buckets["1K-5K"] += 1
        else:
            buckets["5K+"] += 1
    return [{"bucket": k, "customers": v} for k, v in buckets.items() if v > 0]


@router.get("/repeat-vs-onetime")
def repeat_vs_onetime(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    ds = _require_dataset(db, dataset_id)
    total = db.query(func.count(Customer.id)).filter(Customer.dataset_id == ds.id).scalar() or 0
    repeat = (
        db.query(func.count(Customer.id))
        .filter(Customer.dataset_id == ds.id, Customer.order_count > 1)
        .scalar()
        or 0
    )
    one_time = total - repeat
    repeat_revenue = (
        db.query(func.coalesce(func.sum(Customer.total_spend), 0.0))
        .filter(Customer.dataset_id == ds.id, Customer.order_count > 1)
        .scalar()
        or 0.0
    )
    total_revenue = (
        db.query(func.coalesce(func.sum(Customer.total_spend), 0.0))
        .filter(Customer.dataset_id == ds.id)
        .scalar()
        or 0.0
    )
    return {
        "repeat_customers": repeat,
        "one_time_customers": one_time,
        "repeat_revenue": round(repeat_revenue, 2),
        "one_time_revenue": round(total_revenue - repeat_revenue, 2),
        "repeat_pct": round(100.0 * repeat / total, 1) if total else 0.0,
    }


@router.get("/country-analysis")
def country_analysis(
    dataset_id: str | None = None, limit: int = 12, db: Session = Depends(get_db)
):
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(
            Transaction.country,
            func.count(func.distinct(Transaction.customer_id)),
            func.coalesce(func.sum(Transaction.revenue), 0.0),
        )
        .filter(
            Transaction.dataset_id == ds.id,
            Transaction.is_valid == 1,
            Transaction.country.isnot(None),
            Transaction.country != "",
        )
        .group_by(Transaction.country)
        .order_by(func.sum(Transaction.revenue).desc())
        .limit(limit)
        .all()
    )
    return [
        {"country": r[0], "customers": int(r[1]), "revenue": round(float(r[2]), 2)}
        for r in rows
    ]


@router.get("/acquisition")
def acquisition(
    dataset_id: str | None = None, db: Session = Depends(get_db)
):
    """New customer acquisition by first-purchase month."""
    ds = _require_dataset(db, dataset_id)
    rows = (
        db.query(Customer.first_purchase)
        .filter(Customer.dataset_id == ds.id, Customer.first_purchase.isnot(None))
        .all()
    )
    buckets: dict[str, int] = {}
    for (dt,) in rows:
        key = dt.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0) + 1
    return [{"month": k, "new_customers": v} for k, v in sorted(buckets.items())]

"""Dashboard summary queries (SQL over persisted analytics, not Spark-at-request)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    ActivityLog,
    Customer,
    CustomerRfm,
    Dataset,
    ProcessingJob,
    Segment,
    Transaction,
)
from app.schemas import ActivityOut, DashboardSummary, KpiCard
from app.services.common import active_dataset

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _fmt_money(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:,.2f}"


@router.get("/summary", response_model=DashboardSummary)
def summary(dataset_id: str | None = None, db: Session = Depends(get_db)) -> DashboardSummary:
    ds = active_dataset(db, dataset_id)
    if ds is None:
        return DashboardSummary(
            active_dataset=None,
            total_customers=0,
            total_revenue=0.0,
            avg_customer_value=0.0,
            repeat_purchase_rate=None,
            at_risk_customers=None,
            last_processing_status=None,
            last_processed_at=None,
            kpis=[
                KpiCard(label="Total Customers", value=0, formatted="0"),
                KpiCard(label="Total Revenue", value=0, formatted="$0"),
                KpiCard(label="Average Customer Value", value=0, formatted="$0"),
                KpiCard(label="Repeat Purchase Rate", value=None, formatted="—"),
                KpiCard(label="At-Risk Customers", value=None, formatted="—"),
                KpiCard(label="Last Data Processing Status", value="none", formatted="No data"),
            ],
        )

    did = ds.id
    total_customers = db.query(func.count(Customer.id)).filter(Customer.dataset_id == did).scalar() or 0
    total_revenue = (
        db.query(func.coalesce(func.sum(Transaction.revenue), 0.0))
        .filter(Transaction.dataset_id == did, Transaction.is_valid == 1)
        .scalar()
        or 0.0
    )
    avg_value = round(total_revenue / total_customers, 2) if total_customers else 0.0

    repeat = (
        db.query(func.count(Customer.id))
        .filter(Customer.dataset_id == did, Customer.order_count > 1)
        .scalar()
        or 0
    )
    repeat_rate = round(100.0 * repeat / total_customers, 1) if total_customers else None

    at_risk = (
        db.query(func.count(CustomerRfm.id))
        .filter(CustomerRfm.dataset_id == did, CustomerRfm.segment_id.like("%%:at-risk%%"))
        .scalar()
    )
    if not at_risk:
        # fall back to hibernating-style staleness if that label was produced
        stale = (
            db.query(func.count(CustomerRfm.id))
            .filter(CustomerRfm.dataset_id == did, CustomerRfm.recency_days > 180)
            .scalar()
            or 0
        )
        at_risk = stale if stale else None

    last_job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.dataset_id == did)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    last_status = last_job.status if last_job else None
    last_at = last_job.finished_at if last_job and last_job.finished_at else None

    # Previous-period comparison ONLY when historical data spans a prior period.
    delta_revenue = None
    delta_label = None
    dates = (
        db.query(func.min(Transaction.invoice_date), func.max(Transaction.invoice_date))
        .filter(Transaction.dataset_id == did, Transaction.is_valid == 1)
        .one()
    )
    dmin, dmax = dates
    if dmin and dmax:
        span = dmax - dmin
        if span >= timedelta(days=4):  # at least 2 windows of >= 2 days
            half = span / 2
            first_rev = (
                db.query(func.coalesce(func.sum(Transaction.revenue), 0.0))
                .filter(
                    Transaction.dataset_id == did,
                    Transaction.is_valid == 1,
                    Transaction.invoice_date < dmin + half,
                )
                .scalar()
                or 0.0
            )
            second_rev = (
                db.query(func.coalesce(func.sum(Transaction.revenue), 0.0))
                .filter(
                    Transaction.dataset_id == did,
                    Transaction.is_valid == 1,
                    Transaction.invoice_date >= dmin + half,
                )
                .scalar()
                or 0.0
            )
            if first_rev > 0:
                delta_revenue = round(100.0 * (second_rev - first_rev) / first_rev, 1)
                delta_label = "vs first half of period"

    kpis = [
        KpiCard(label="Total Customers", value=total_customers, formatted=f"{total_customers:,}"),
        KpiCard(
            label="Total Revenue",
            value=round(total_revenue, 2),
            formatted=f"${_fmt_money(total_revenue)}",
            delta=delta_revenue,
            delta_label=delta_label,
        ),
        KpiCard(
            label="Average Customer Value",
            value=avg_value,
            formatted=f"${avg_value:,.2f}",
        ),
        KpiCard(
            label="Repeat Purchase Rate",
            value=repeat_rate,
            formatted=f"{repeat_rate}%" if repeat_rate is not None else "—",
        ),
        KpiCard(
            label="At-Risk Customers",
            value=at_risk,
            formatted=f"{at_risk:,}" if at_risk is not None else "—",
        ),
        KpiCard(
            label="Last Data Processing Status",
            value=last_status,
            formatted=(last_status or "no runs").capitalize(),
        ),
    ]

    return DashboardSummary(
        active_dataset=did,
        total_customers=total_customers,
        total_revenue=round(total_revenue, 2),
        avg_customer_value=avg_value,
        repeat_purchase_rate=repeat_rate,
        at_risk_customers=at_risk,
        last_processing_status=last_status,
        last_processed_at=last_at,
        kpis=kpis,
    )


@router.get("/activity", response_model=list[ActivityOut])
def activity(limit: int = 8, db: Session = Depends(get_db)) -> list[ActivityOut]:
    rows = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .limit(min(limit, 50))
        .all()
    )
    return [
        ActivityOut(
            id=r.id, event=r.event, target=r.target, status=r.status, created_at=r.created_at
        )
        for r in rows
    ]

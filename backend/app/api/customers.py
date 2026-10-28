import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Customer, CustomerRfm, Dataset, Segment, Transaction
from app.schemas import CustomerDetail, CustomerRow, Page, TransactionOut
from app.services.common import active_dataset

router = APIRouter(prefix="/customers", tags=["customers"])

SORTABLE = {
    "monetary": CustomerRfm.monetary,
    "frequency": CustomerRfm.frequency,
    "recency": CustomerRfm.recency_days,
    "last_purchase": Customer.last_purchase,
    "customer_id": Customer.customer_id,
}


def _base_query(db: Session, ds: Dataset):
    return (
        db.query(Customer, CustomerRfm, Segment)
        .join(CustomerRfm, (CustomerRfm.dataset_id == Customer.dataset_id)
              & (CustomerRfm.customer_id == Customer.customer_id), isouter=True)
        .join(Segment, (Segment.id == CustomerRfm.segment_id), isouter=True)
        .filter(Customer.dataset_id == ds.id)
    )


@router.get("", response_model=Page[CustomerRow])
def list_customers(
    dataset_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: str | None = None,
    segment: str | None = None,
    rfm_score: int | None = Query(None, ge=3, le=15),
    sort: str = Query("monetary", pattern="^(monetary|frequency|recency|last_purchase|customer_id)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
) -> Page[CustomerRow]:
    ds = active_dataset(db, dataset_id)
    if ds is None:
        return Page(items=[], total=0, page=page, page_size=page_size)

    q = _base_query(db, ds)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(Customer.customer_id.ilike(like))
    if segment:
        q = q.filter(CustomerRfm.segment_id == segment)
    if rfm_score is not None:
        q = q.filter(CustomerRfm.rfm_score == rfm_score)
    if start:
        q = q.filter(Customer.last_purchase >= start)
    if end:
        q = q.filter(Customer.last_purchase <= end)

    total = q.count()

    sort_col = SORTABLE[sort]
    sort_ref = sort_col if sort_col in (Customer.last_purchase, Customer.customer_id) else sort_col
    direction = sort_ref.desc() if order == "desc" else sort_col.asc()
    q = q.order_by(direction, Customer.customer_id.asc())

    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        CustomerRow(
            customer_id=c.customer_id,
            country=c.country,
            last_purchase=c.last_purchase,
            recency_days=r.recency_days if r else None,
            frequency=r.frequency if r else (c.order_count or None),
            monetary=round(r.monetary, 2) if r else round(c.total_spend or 0.0, 2),
            segment_id=r.segment_id if r else None,
            segment_name=s.name if s else None,
            rfm_score=r.rfm_score if r else None,
        )
        for c, r, s in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
def export_customers(
    dataset_id: str | None = None,
    search: str | None = None,
    segment: str | None = None,
    rfm_score: int | None = None,
    db: Session = Depends(get_db),
) -> Response:
    """Export the currently filtered customer set as CSV."""
    ds = active_dataset(db, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="No processed dataset available")
    q = _base_query(db, ds)
    if search:
        q = q.filter(Customer.customer_id.ilike(f"%{search.strip()}%"))
    if segment:
        q = q.filter(CustomerRfm.segment_id == segment)
    if rfm_score is not None:
        q = q.filter(CustomerRfm.rfm_score == rfm_score)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "customer_id", "segment", "recency_days", "frequency", "monetary",
        "rfm_score", "first_purchase", "last_purchase", "country",
    ])
    for c, r, s in q.order_by(CustomerRfm.monetary.desc().nullslast()).limit(100000).all():
        writer.writerow([
            c.customer_id,
            s.name if s else "",
            r.recency_days if r else "",
            r.frequency if r else c.order_count,
            round(r.monetary, 2) if r else round(c.total_spend or 0.0, 2),
            r.rfm_score if r else "",
            c.first_purchase.isoformat(sep=" ") if c.first_purchase else "",
            c.last_purchase.isoformat(sep=" ") if c.last_purchase else "",
            c.country or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customeriq_customers.csv"},
    )


@router.get("/{customer_id}", response_model=CustomerDetail)
def customer_detail(customer_id: str, dataset_id: str | None = None,
                    db: Session = Depends(get_db)) -> CustomerDetail:
    ds = active_dataset(db, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="No processed dataset available")
    row = _base_query(db, ds).filter(Customer.customer_id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    c, r, s = row
    return CustomerDetail(
        customer_id=c.customer_id,
        country=c.country,
        last_purchase=c.last_purchase,
        first_purchase=c.first_purchase,
        order_count=c.order_count,
        total_spend=round(c.total_spend, 2),
        avg_order_value=round(c.avg_order_value, 2),
        recency_days=r.recency_days if r else None,
        frequency=r.frequency if r else c.order_count,
        monetary=round(r.monetary, 2) if r else round(c.total_spend, 2),
        rfm_score=r.rfm_score if r else None,
        cluster_id=r.cluster_id if r else None,
        segment_id=r.segment_id if r else None,
        segment_name=s.name if s else None,
    )


@router.get("/{customer_id}/transactions", response_model=list[TransactionOut])
def customer_transactions(
    customer_id: str,
    dataset_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[TransactionOut]:
    ds = active_dataset(db, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="No processed dataset available")
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.dataset_id == ds.id,
            Transaction.customer_id == customer_id,
            Transaction.is_valid == 1,
        )
        .order_by(Transaction.invoice_date.desc())
        .limit(limit)
        .all()
    )
    return [
        TransactionOut(
            invoice_no=t.invoice_no,
            invoice_date=t.invoice_date,
            stock_code=t.stock_code,
            description=t.description,
            quantity=t.quantity,
            unit_price=t.unit_price,
            revenue=round(t.revenue, 2),
            country=t.country,
        )
        for t in rows
    ]


@router.get("/{customer_id}/spending-trend")
def spending_trend(
    customer_id: str,
    dataset_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Monthly spending series for one customer (only when history supports it)."""
    ds = active_dataset(db, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="No processed dataset available")
    rows = (
        db.query(Transaction.invoice_date, Transaction.revenue)
        .filter(
            Transaction.dataset_id == ds.id,
            Transaction.customer_id == customer_id,
            Transaction.is_valid == 1,
            Transaction.invoice_date.isnot(None),
        )
        .all()
    )
    if not rows:
        return []
    buckets: dict[str, float] = {}
    for dt, rev in rows:
        key = dt.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0.0) + float(rev or 0.0)
    series = [{"month": k, "spend": round(v, 2)} for k, v in sorted(buckets.items())]
    return series

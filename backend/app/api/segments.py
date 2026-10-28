from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CustomerRfm, Dataset, Segment
from app.schemas import Page, SegmentOut
from app.services.common import active_dataset

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("", response_model=list[SegmentOut])
def list_segments(dataset_id: str | None = None, db: Session = Depends(get_db)) -> list[SegmentOut]:
    ds = active_dataset(db, dataset_id)
    if ds is None:
        return []
    rows = (
        db.query(Segment)
        .filter(Segment.dataset_id == ds.id)
        .order_by(Segment.revenue.desc())
        .all()
    )
    return [_out(r) for r in rows]


@router.get("/{segment_id}", response_model=SegmentOut)
def segment_detail(segment_id: str, db: Session = Depends(get_db)) -> SegmentOut:
    seg = db.get(Segment, segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return _out(seg)


@router.get("/{segment_id}/rfm-distribution")
def segment_rfm_distribution(segment_id: str, db: Session = Depends(get_db)):
    """Score composition of a segment: how its customers spread across RFM scores."""
    seg = db.get(Segment, segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    rows = (
        db.query(CustomerRfm.rfm_score, func.count(CustomerRfm.id))
        .filter(CustomerRfm.dataset_id == seg.dataset_id, CustomerRfm.segment_id == segment_id,
                CustomerRfm.rfm_score.isnot(None))
        .group_by(CustomerRfm.rfm_score)
        .order_by(CustomerRfm.rfm_score)
        .all()
    )
    return [{"score": s, "customers": c} for s, c in rows]


def _out(r: Segment) -> SegmentOut:
    return SegmentOut(
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
